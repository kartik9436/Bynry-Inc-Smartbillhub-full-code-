# ── Trace ──────────────────────────────────────────────
# Change:   `CR-138-BRC07` `P4.15` — *"a tone selects the right letter, day
#           numbers come from tenant config and never from constants, and the
#           tones still render when the settings cannot be read."*
# Rules:    BR-NOT-008 (a regulated ladder step ALWAYS renders the
#           disconnect-notice template class, whatever tone was picked) ·
#           BR-NOT-014 (each tier has its OWN class) · BR-PAY-035 (three tones,
#           no fourth) · BR-REP-016 (*"day numbers are always tenant config,
#           never constants"*) · BR-CUS-039 (certified mail on the final tier)
# Ruling:   `OQ-PAY-12607` (2026-09-23, CLOSED — no fourth tone)
# Screens:  7·3d Notice (S35 · PAY-B) · S8 Notifications config
# Database: BOTH — the default suite (in-memory SQLite) **and** real
#           PostgreSQL 16 (`sbh_p4tests_pg`), and the second run is not a
#           formality: two cases here PASSED on SQLite and FAILED on PostgreSQL
#           with `new row violates row-level security policy for table
#           "tenant_settings"`, which is hard-won law 14 exactly. See
#           `_store_collections` and `DEF-GOV-6298`.
# ───────────────────────────────────────────────────────
"""THE DAY NUMBERS ARE THE TENANT'S, AND A CONSTANT WOULD SATISFY THE OLD TEST.

⚠ **WHAT WAS ALREADY COVERED, SO THIS FILE DOES NOT RE-PROVE IT.**
`tests/test_us_not_004_settings_api.py` already holds
`test_us_not_010__firm_selects_the_regulated_disconnect_notice`, which asserts
the tone→class table over the SERVER's own `TONE_TO_STEP` — *Firm* →
`disconnect_notice_10_day`, *Final* → `disconnect_notice_48_hour` + certified,
*friendly* → `dunning`, three tones and no fourth. **That half of `P4.15` is
done and is not duplicated here.**

⚠ **WHAT WAS NOT, AND IT IS THE HALF THE TASK NAMES FIRST.**
`test_us_not_010_tc3__the_day_numbers_are_the_tenants_own_or_are_absent` asserts
only an **exclusive or** — either `stage_days` or `stage_days_unavailable`,
never both — and then, when the days ARE present, asserts nothing about what
they are. **A hardcoded `return (7, 14, 30)` passes it**, which is precisely the
defect `BR-REP-016` exists to prevent: *"day numbers are always tenant config,
never constants"*. Neither did anything force the refusal branch, so
*"the tones still render when the settings cannot be read"* — `P4.15`'s own
third clause and the whole reason `notice_tones` splits the two fields — ran on
no deployment and was asserted on none.

So this file does two things the existing one cannot:

  1. **A tenant whose ladder intervals are NOT the seeds.** `7 · 21 · 14 · 4`
     is written into the tenant's own `collections` document and the response
     must carry exactly that. The seeds `3 · 10 · 5` and `BR-REP-016`'s cadence
     seeds `7 · 14 · 30` are asserted ABSENT by value, so a constant of either
     shape goes red.
  2. **A tenant whose ladder intervals cannot be read at all**, which is a real
     stored state and not a patch: `merge` honours an explicitly stored `None`
     and `[]`, `notices.stage_days` then refuses rather than falling back, and
     the three tones and their classes must still be served — because which
     CLASS a tone selects is a RULE and does not depend on any day number.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY, ANSWERED RATHER THAN ASSUMED:**

  * *The endpoint could echo whatever it was given and never read the tenant.*
    Answered by case 1 asserting an EXACT list a seed cannot produce, and by
    case 3 reading a SECOND tenant in the same test and getting a DIFFERENT
    answer. One tenant proves a value; two prove a lookup.
  * *The refusal branch could be reached by the tones failing too*, which would
    make clause 3 vacuous. Answered by asserting the three tones AND their
    classes AND `free_text_tones_exist` in the very response whose
    `stage_days` is None.
  * *A day list could be right by accident because the seeds happen to match.*
    Answered by choosing `[21, 14, 4]`, which is not the seed list, not the
    cadence seeds, and not a prefix or permutation of either.

PROVED RED (the harness that will actually run it — `pytest`, not a REPL):

    stage_days() patched to `return (7, 14, 30)`:
      FAILED …::test_the_day_numbers_are_THIS_TENANTS_and_a_constant_is_red
      assert [7, 14, 30] == [7, 21, 14, 4]

    the refusal branch made to return `[]` instead of raising:
      FAILED …::test_when_the_intervals_cannot_be_read_the_TONES_STILL_RENDER
      assert None is not None  — `stage_days_unavailable` carried no reason
"""

from __future__ import annotations

import pytest

from apps.notifications import notices, settings_api as api, tenancy_seam
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: NOT the seeded ladder (`reminder_days_after_due` 3 + `notice_tier_days`
#: [10, 5] → 3 · 10 · 5) and NOT BR-REP-016's cadence seeds (7 · 14 · 30).
#: A constant of either shape fails every assertion below.
THEIR_REMINDER = 7
THEIR_TIERS = [21, 14, 4]
THEIR_LADDER = [7, 21, 14, 4]

SEEDED_LADDER = [3, 10, 5]
CADENCE_SEEDS = [7, 14, 30]


def _get(view, tenant, actor, role="system_admin"):
    return api_call(view, "get", user=getattr(actor, "user", None), role=role, tenant=tenant)


def _store_collections(tenant, document: dict) -> None:
    """Write ONE tenant's `collections` rule page, as S70's save does.

    `settings_families.merge` reads `stored[key] if key in stored`, so a key
    stored explicitly as `None` or `[]` is honoured rather than re-defaulted —
    which is what lets case 2 below reach the refusal with REAL DATA instead of
    a patched seam. A patched seam would prove the branch and not the state.

    ⚠⚠ **IT ENTERS ITS OWN `tenant_ctx`, AND THAT IS `DEF-GOV-6298`, NOT
    BELT-AND-BRACES.** `core.tenancy.tenant_context` clears `app.tenant_id` in
    its `finally` **unconditionally** — it does not restore the value it
    replaced — and `api_call` opens one of its own around every view it calls.
    So the moment a test makes a request, the enclosing `with tenant_ctx(...)`
    is *still open in Python and no longer set in the database*, and every ORM
    statement after it runs UNSCOPED.

    **On SQLite that is invisible and this helper worked.** On real PostgreSQL
    16 with RLS FORCE it is not: the `get` inside `update_or_create` matched
    zero rows, so it fell through to an INSERT, and the insert was refused —
    `psycopg.errors.InsufficientPrivilege: new row violates row-level security
    policy for table "tenant_settings"`. Two cases in this file failed on
    PostgreSQL and passed on SQLite, which is hard-won law 14's exact shape.

    ⚠ **AND THE READ DIRECTION IS WORSE THAN THE WRITE**, which is why this is
    written out here rather than silently fixed: an unscoped *write* raises, an
    unscoped *read* returns **zero rows and nothing raises** — so a case
    asserting an absence after a request passes for the wrong reason, on
    PostgreSQL, for ever.
    """
    with tenant_ctx(tenant):
        tenancy_models.TenantSettings.objects.update_or_create(
            tenant=tenant, defaults={"collections": document}
        )


# ── 1 · the days are the tenant's own ──────────────────────────────────────
def test_the_day_numbers_are_THIS_TENANTS_and_a_constant_is_red(brazos, dana):
    """`BR-REP-016`: *"day numbers are always tenant config, never constants"*.

    Brazos Bend chases on **7 · 21 · 14 · 4** — a reminder a week after the due
    date, then a 21-day notice, then 14, then 4. Nothing in the product may
    print `3 · 10 · 5` or `7 · 14 · 30` over that tenant, because a letter
    printing the wrong day number tells a customer the wrong date to pay by.
    """
    _store_collections(
        brazos, {"reminder_days_after_due": THEIR_REMINDER, "notice_tier_days": THEIR_TIERS}
    )
    response = _get(api.notice_tones, brazos, dana)

    assert response.status_code == 200, response.data
    assert response.data["stage_days"] == THEIR_LADDER
    assert response.data["stage_days_unavailable"] is None
    # A seed would satisfy the exclusive-or the old case asserts. It does not
    # satisfy these two, which is the whole point of this file.
    assert response.data["stage_days"] != SEEDED_LADDER
    assert response.data["stage_days"] != CADENCE_SEEDS


def test_the_reminder_day_LEADS_the_tier_days_and_is_not_dropped(brazos, dana):
    """The list is `reminder_days_after_due` FOLLOWED BY `notice_tier_days`.

    Order matters on screen: the wizard prints them as *"7 · 21 · 14 · 4"* and
    a reader takes that as the sequence a customer will experience. A build
    that served the tiers alone would print a ladder starting at 21 days, which
    is a different product.
    """
    _store_collections(
        brazos, {"reminder_days_after_due": THEIR_REMINDER, "notice_tier_days": THEIR_TIERS}
    )
    response = _get(api.notice_tones, brazos, dana)

    assert response.data["stage_days"][0] == THEIR_REMINDER
    assert response.data["stage_days"][1:] == THEIR_TIERS


def test_two_tenants_two_ladders_so_this_is_a_LOOKUP_and_not_an_echo(
    brazos, dana, lonestar, erin
):
    """One tenant proves a value; TWO prove a lookup.

    A read that returned its argument, or a module-level constant seeded once,
    would answer both tenants identically and pass every single-tenant
    assertion above. Lone Star chases on a different ladder and must be told so.
    """
    _store_collections(
        brazos, {"reminder_days_after_due": THEIR_REMINDER, "notice_tier_days": THEIR_TIERS}
    )
    ours = _get(api.notice_tones, brazos, dana).data["stage_days"]

    _store_collections(lonestar, {"reminder_days_after_due": 2, "notice_tier_days": [30]})
    theirs = _get(api.notice_tones, lonestar, erin).data["stage_days"]

    assert ours == THEIR_LADDER
    assert theirs == [2, 30]
    assert ours != theirs


# ── 2 · and when they cannot be read, the tones still render ───────────────
def test_when_the_intervals_cannot_be_read_the_TONES_STILL_RENDER(brazos, dana):
    """`P4.15`'s third clause, and the reason `notice_tones` has two fields.

    A tenant whose ladder intervals are stored empty is a real state — S70 has
    a save that can write one — and `notices.stage_days` REFUSES rather than
    reaching for `BR-REP-016`'s seeds. The screen must then print **no day
    number at all**, and must still tell a clerk which LETTER each tone selects,
    because that is a rule and does not depend on a day number.
    """
    _store_collections(brazos, {"reminder_days_after_due": None, "notice_tier_days": []})
    # The refusal is the seam's own, reached through real stored data.
    # ⚠ **ITS OWN `tenant_ctx`, FOR `DEF-GOV-6298`'s READ DIRECTION.** Left
    # inside a context an earlier helper had already cleared, `stage_days()`
    # would read an UNSCOPED `collections_config()`, get `{}` back and raise —
    # and this case would pass without ever exercising the stored state it is
    # about. That is a green for the wrong reason, which is worse than a red.
    with tenant_ctx(brazos):
        with pytest.raises(tenancy_seam.CollectionsConfigUnavailable):
            notices.stage_days()
    response = _get(api.notice_tones, brazos, dana)

    assert response.status_code == 200, response.data
    assert response.data["stage_days"] is None
    reason = response.data["stage_days_unavailable"]
    assert reason is not None and reason.strip(), "a refusal with no reason is a silence"
    # `BR-REP-016`'s seeds are named in the refusal as SEEDS, never offered as
    # a fallback — so the sentence a clerk's screen renders says why there is
    # no number rather than printing a wrong one.
    assert "seed" in reason.lower()

    # …and the three tones are all still there, with their classes.
    by_tone = {row["tone"]: row for row in response.data["tones"]}
    assert len(by_tone) == 3
    assert by_tone["friendly"]["template_class"] == notices.CLASS_DUNNING
    assert by_tone["firm"]["template_class"] == notices.TIER_TO_CLASS[notices.TIER_FIRST_10_DAY]
    assert by_tone["final"]["template_class"] == notices.TIER_TO_CLASS[notices.TIER_FINAL_48_HOUR]
    assert by_tone["final"]["certified_mail"] is True
    assert response.data["free_text_tones_exist"] is False


def test_the_two_day_fields_are_never_BOTH_absent_and_never_BOTH_present(brazos, dana):
    """A third state would be a screen with nothing to render and no reason.

    `notice_tones` reports exactly one of `stage_days` and
    `stage_days_unavailable`, in both directions. Asserted over BOTH stored
    states in one case, because an exclusive-or checked on one branch only is
    an exclusive-or nobody checked.
    """
    _store_collections(
        brazos, {"reminder_days_after_due": THEIR_REMINDER, "notice_tier_days": THEIR_TIERS}
    )
    present = _get(api.notice_tones, brazos, dana).data
    _store_collections(brazos, {"reminder_days_after_due": None, "notice_tier_days": []})
    absent = _get(api.notice_tones, brazos, dana).data

    for body in (present, absent):
        assert (body["stage_days"] is None) != (body["stage_days_unavailable"] is None)
    assert present["stage_days"] is not None
    assert absent["stage_days"] is None


# ── 3 · the letter a tone selects is resolved, never typed ─────────────────
def test_the_class_a_tone_selects_does_not_move_when_the_days_do(brazos, dana):
    """`BR-NOT-008` — the sentence the wizard exists to show before pressing.

    ⚠ **THIS IS NOT A SECOND COPY OF `test_us_not_010__firm_selects_…`.** That
    case asserts the table. This one asserts the table is INDEPENDENT of the
    tenant's day numbers: the same three classes come back over a `7 · 21 · 14
    · 4` ladder, a `2 · 30` ladder and no ladder at all. A build that derived
    the class from a day number — *"the 10-day notice"* is, after all, named
    after one — would send a firmer REMINDER where the regulated disconnect
    notice is owed.
    """
    seen = []
    for document in (
        {"reminder_days_after_due": THEIR_REMINDER, "notice_tier_days": THEIR_TIERS},
        {"reminder_days_after_due": 2, "notice_tier_days": [30]},
        {"reminder_days_after_due": None, "notice_tier_days": []},
    ):
        _store_collections(brazos, document)
        body = _get(api.notice_tones, brazos, dana).data
        seen.append({row["tone"]: row["template_class"] for row in body["tones"]})

    assert seen[0] == seen[1] == seen[2]
    assert seen[0]["firm"].startswith("disconnect_notice")
    assert seen[0]["friendly"] == notices.CLASS_DUNNING


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-138-BRC07 `P4.15` · blueprint `05-prototype/06 Payments Page
#         Blueprint.pdf` p022 (the task row) · p087–p089 (screen 7·3d) ·
#         BR-REP-016 · BR-NOT-008 · BR-NOT-014 · BR-PAY-035
# generated: 2026-09-23 by LANE P4-TESTS
# checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
# gates: RED PROVED FIRST, through `pytest` itself — `stage_days()` stubbed to
#         `return (7, 14, 30)` failed the tenant-config case with
#         `assert [7, 14, 30] == [7, 21, 14, 4]`, and the refusal branch made
#         to return `[]` instead of raising failed the still-render case on
#         `stage_days_unavailable` being None. Transcripts in the lane report.
# exceptions: (0) `DEF-GOV-6298` — `_store_collections` opens its OWN tenant
#         context because `core.tenancy.tenant_context` clears rather than
#         restores, so an `api_call` leaves the enclosing `with tenant_ctx(...)`
#         set in Python and unset in the database. Found by running this file on
#         real PostgreSQL after it was green on SQLite.
#         (1) THE TONE→CLASS TABLE ITSELF IS NOT RE-ASSERTED HERE. It is
#         covered by `test_us_not_004_settings_api.py::test_us_not_010__firm_
#         selects_the_regulated_disconnect_notice` and duplicating it would
#         give two files one figure to disagree about. What IS asserted here is
#         the property that file cannot see: the table does not move when the
#         tenant's day numbers do.
#         (2) SQLITE IS NOT SUFFICIENT AND THE FIRST DRAFT OF THIS LINE SAID IT
#         WAS. It was written before the PostgreSQL run and it was wrong: two
#         cases passed on SQLite and failed on PostgreSQL. The claim is
#         corrected rather than deleted, because the wrong version is the more
#         instructive half (hard-won law 1).
# status: VERIFIED-UNRATIFIED

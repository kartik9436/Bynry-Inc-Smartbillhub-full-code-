# ── Trace ──────────────────────────────────────────────
# Change:  Settings → Security redesign, APPROVED by the PO 2026-09-29
#          (05-prototype/security-redesign-2026-09-29/). Job 1 — the four
#          typed numbers become choice lists. PO verbatim: *"(a) Short
#          dropdown, list chosen from real use - Dropdown"*.
# Rules:   BR-IDN-025 / BR-IDN-026 (what the settings are) · BR-IDN-019
#          (SysAdmin edits, Executive views) · B14 rule 31 (no database id is
#          ever the visible value of a field) · CLAUDE.md hard-won law 5 (one
#          source, derive views on demand) · law 7 habit 2 (ask what would
#          make this check pass wrongly)
# Tests:   this file. The audit card is test_security_redesign_audit_card.py;
#          the RLS half is test_security_redesign_audit_card_pg.py.
# ───────────────────────────────────────────────────────
"""THE EIGHT SETTINGS ARE ALL CHOICE LISTS, AND THE SERVER REFUSES BY NAME.

⚠ **WHY A REFUSAL TEST IS THE WHOLE POINT OF THIS JOB.** The screen is about
to offer only the listed values. If the server went on accepting anything in
the old range, the screen and the validator would disagree — a control that
lies, which is the mirror of hard-won law 2 and costs more than dead UI
because nothing goes red over it.

⚠ **AND WHY A *STILL READABLE* TEST IS THE OTHER HALF.** Two of the four
lists are narrower than the range they replace, so a utility can hold a value
the screen no longer offers. It must still be able to open the tab and save
it. `test_a_retained_value_*` is that clause as an assertion, and the value
it plants is planted ON PURPOSE rather than borrowed from the demo estate:
the census of 2026-09-29 found every utility on this container sitting on the
seeded default, so leaning on the fixtures would test nothing.
"""

import json

import pytest

from apps.identity import selectors, services
from apps.identity.models import SecurityPolicy
from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    api_get,
    api_path,
    api_put,
    body_without_trace,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db

JSON = "application/json"

#: The four that moved on 2026-09-29, with the list each one now offers.
THE_FOUR = {
    "absolute_session_hours": services.ABSOLUTE_SESSION_HOURS_CHOICES,
    "lockout_max_failed": services.LOCKOUT_MAX_FAILED_CHOICES,
    "lockout_minutes": services.LOCKOUT_MINUTES_CHOICES,
    "keep_signed_in_days": services.KEEP_SIGNED_IN_DAYS_CHOICES,
}

#: One value per field that is INSIDE the old range and OFF the new list —
#: which is the only interesting kind of refusal here. A value outside the
#: old range was already refused before this change and proves nothing about
#: it (`test_cr145_session_settings.py` owns those).
OFF_LIST_INSIDE_THE_OLD_RANGE = {
    "absolute_session_hours": None,  # 4..12 is offered whole — nothing to withdraw
    "lockout_max_failed": None,  # 3..10 is offered whole — nothing to withdraw
    "lockout_minutes": 23,  # was legal (5..60), not on 5/10/15/30/45/60
    "keep_signed_in_days": 11,  # was legal (1..30), not on 1/7/14/30
}


def _admin(idn_env):
    users = idn_env.seed_silvercreek()
    return signed_in_client(users.alex.email, "Canyon2026rapids")


# ═══════════════════════════════════════════════════════════════════════════
# The shape: eight entries, every one of them a list
# ═══════════════════════════════════════════════════════════════════════════
def test_every_setting_is_a_choice_list_and_none_is_a_range(idn):
    """The redesign's Q1 in one assertion: no `min`/`max` entry is left."""
    client = _admin(idn)
    limits = json.loads(api_get(client, "/settings/security-policy").content)["limits"]

    # NINE since 2026-10-21: the field app's capture life (PO, *"this should
    # come from settings"*), a choice list like the other eight.
    # TEN since 2026-10-22 (`CR-188-BRC10`, PO *"don't do any hardcoding"*):
    # how long an emailed sign-in link lasts, 1/2/3/7/14 days — a choice list.
    assert len(limits) == 10, sorted(limits)
    for field, entry in limits.items():
        assert ("choices" in entry) or entry.get("boolean"), (field, entry)
        assert "min" not in entry and "max" not in entry, (field, entry)


def test_the_two_final_lists_are_their_whole_old_range(idn):
    """`absolute_session_hours` and `lockout_max_failed` withdraw NOTHING.

    That is the argument that let these two be settled without waiting for
    the production count, so it is asserted rather than left in a comment.
    """
    assert services.ABSOLUTE_SESSION_HOURS_CHOICES == tuple(range(4, 13))
    assert services.LOCKOUT_MAX_FAILED_CHOICES == tuple(range(3, 11))


def test_the_two_provisional_lists_are_the_drawn_ones(idn):
    """Pinned so that replacing them with the production count is a VISIBLE
    edit here as well as in `services.py` — a list that can be widened with
    no test moving is a list nobody is watching."""
    assert services.LOCKOUT_MINUTES_CHOICES == (5, 10, 15, 30, 45, 60)
    assert services.KEEP_SIGNED_IN_DAYS_CHOICES == (1, 7, 14, 30)


def test_the_read_publishes_numbers_and_no_words(idn):
    """DEF-IDN-7501 one step on, and the REVERSAL of 2026-09-29 with it.

    The defect was a screen typing `[8, 10, 12]` by hand, so the numbers
    travel. For one afternoon the WORDS travelled too (`"12 hours"`, under an
    `options` key) — and the Security tab labels its own options through
    `securityValueLabel` and the eleven catalogues, so that key was read by
    nothing and could only ever have disagreed with the screen in ten
    languages out of eleven. **The numbers are the server's, the words are
    the catalogue's**, and this case is what keeps it that way.
    """
    client = _admin(idn)
    limits = json.loads(api_get(client, "/settings/security-policy").content)["limits"]

    assert limits["lockout_minutes"] == {"choices": [5, 10, 15, 30, 45, 60], "default": 15}
    for field, entry in limits.items():
        assert set(entry) <= {"choices", "default", "boolean", "retained"}, (field, entry)


def test_a_tick_box_publishes_no_options(idn):
    """Q3 — the tick boxes stay tick boxes (*"(a) Keep them as checkboxes"*)."""
    client = _admin(idn)
    limits = json.loads(api_get(client, "/settings/security-policy").content)["limits"]
    assert limits["keep_signed_in_offered"] == {"boolean": True, "default": True}


# ═══════════════════════════════════════════════════════════════════════════
# The refusals — by NAME, and only for what is genuinely withdrawn
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "field,value",
    [(field, value) for field, value in OFF_LIST_INSIDE_THE_OLD_RANGE.items() if value],
)
def test_a_value_the_screen_no_longer_offers_is_refused_by_name(idn, field, value):
    client = _admin(idn)
    response = api_put(client, "/settings/security-policy", {field: value})

    assert response.status_code == 422, response.content
    named = [fe for fe in body_without_trace(response)["field_errors"] if fe["field"] == field]
    assert len(named) == 1, named  # one refusal per field — never two validators
    assert named[0]["message_key"] == "errors.identity.option_not_allowed"
    assert named[0]["params"]["allowed"] == list(THE_FOUR[field])
    assert not SecurityPolicy.objects.filter(tenant=idn.silvercreek).exists()


@pytest.mark.parametrize(
    "field,value",
    [(field, choice) for field, choices in THE_FOUR.items() for choice in choices],
)
def test_every_offered_value_is_accepted(idn, field, value):
    """The other half, and it is not decoration — a validator that refused an
    endpoint of its own list would pass every case above (law 7, habit 2)."""
    client = _admin(idn)
    response = api_put(client, "/settings/security-policy", {field: value})
    assert response.status_code == 200, response.content
    assert getattr(SecurityPolicy.objects.get(tenant=idn.silvercreek), field) == value


def test_a_boolean_is_still_not_a_number(idn):
    """`isinstance(True, int)` is True, and `1 in (1, 7, 14, 30)` is True — so
    the choice branch has to refuse a bool by TYPE, not by membership."""
    client = _admin(idn)
    response = client.put(
        api_path("/settings/security-policy"),
        data=json.dumps({"keep_signed_in_days": True}),
        content_type=JSON,
    )
    assert response.status_code == 422, response.content


# ═══════════════════════════════════════════════════════════════════════════
# A utility already sitting on a value the list does not carry
# ═══════════════════════════════════════════════════════════════════════════
def _plant_off_list(idn_env, **values):
    """Write the off-list value straight onto the row.

    ⚠ It cannot be written through the API — the API is what refuses it, and
    that is the whole point. This is a utility that held the value BEFORE the
    list existed, which is the only way such a row can exist.
    """
    policy, _created = SecurityPolicy.objects.get_or_create(tenant=idn_env.silvercreek)
    for field, value in values.items():
        setattr(policy, field, value)
    policy.save()
    return policy


def test_a_retained_value_reads_AND_is_in_that_utilitys_own_dropdown(idn):
    """⚠ **THE SECOND HALF IS THE REVERSAL OF 2026-09-29 AND IT IS THE HALF
    THAT MATTERS.**

    The first version of this served the platform list untouched and put the
    held value beside it under `retained`, reasoning that the product must
    not offer a value it has withdrawn. True of the PLATFORM and false of the
    `<select>`: the Security tab builds its dropdown from `choices` alone
    (`optionsFromLimit`), so an option that is missing means the browser
    shows the FIRST one — this utility would have read *5 minutes* over a
    stored 23, and the next save of any other field would have written 5.
    A screen that silently misreports a setting and then changes it is worse
    than a list with one extra entry, and it is the live-screen-telling-a-lie
    shape of `DEF-CWP-3925`.

    The entry is served to THIS utility only, in order, and the validator's
    `current` exemption accepts exactly it — dropdown and server agree row
    for row.
    """
    _plant_off_list(idn, lockout_minutes=23)
    client = _admin(idn)
    body = json.loads(api_get(client, "/settings/security-policy").content)

    assert body["lockout_minutes"] == 23
    entry = body["limits"]["lockout_minutes"]
    assert entry["retained"] == 23
    assert entry["choices"] == [5, 10, 15, 23, 30, 45, 60], "in order, not appended"


def test_no_other_utility_is_offered_the_retained_value(idn):
    """The other half of the reversal, and the thing that keeps it honest: an
    extra option for ONE utility is not a change to what the product offers.

    What would make the case above pass wrongly is a `retained` key, and an
    extra choice, on every field of every utility — which a screen would then
    draw for everybody.
    """
    _plant_off_list(idn, lockout_minutes=23)
    client = _admin(idn)
    limits = json.loads(api_get(client, "/settings/security-policy").content)["limits"]
    # Only the field that holds it, and only on this utility's read.
    assert [field for field, entry in limits.items() if "retained" in entry] == ["lockout_minutes"]
    # The platform's own answer is untouched — no row, no exception.
    platform = selectors.security_policy_limits()
    assert platform["lockout_minutes"] == {"choices": [5, 10, 15, 30, 45, 60], "default": 15}
    assert all("retained" not in entry for entry in platform.values())
    # And `SETTING_LIMITS` itself never learned the number.
    assert 23 not in services.SETTING_LIMITS["lockout_minutes"]["choices"]


def test_a_retained_value_can_be_saved_back_untouched(idn):
    """The browser sends the whole policy, so refusing the untouched field
    would refuse EVERY save this utility ever makes."""
    _plant_off_list(idn, lockout_minutes=23)
    client = _admin(idn)
    whole = json.loads(api_get(client, "/settings/security-policy").content)
    payload = {field: whole[field] for field in services.SETTING_LIMITS}
    payload["lockout_max_failed"] = 8  # they came to change something else

    response = api_put(client, "/settings/security-policy", payload)
    assert response.status_code == 200, response.content
    policy = SecurityPolicy.objects.get(tenant=idn.silvercreek)
    assert policy.lockout_minutes == 23  # nobody was moved
    assert policy.lockout_max_failed == 8


def test_the_exemption_is_only_for_the_value_actually_held(idn):
    """A one-way door: holding 23 does not open 24."""
    _plant_off_list(idn, lockout_minutes=23)
    client = _admin(idn)
    response = api_put(client, "/settings/security-policy", {"lockout_minutes": 24})
    assert response.status_code == 422, response.content
    assert SecurityPolicy.objects.get(tenant=idn.silvercreek).lockout_minutes == 23


def test_moving_off_a_retained_value_cannot_be_undone(idn):
    """Retained, not restored — once they pick an offered value the old one is
    gone from the choices for good."""
    _plant_off_list(idn, lockout_minutes=23)
    client = _admin(idn)
    assert api_put(client, "/settings/security-policy", {"lockout_minutes": 30}).status_code == 200
    assert api_put(client, "/settings/security-policy", {"lockout_minutes": 23}).status_code == 422


def test_a_rowless_utility_gets_no_exemption_and_needs_none(idn):
    """Every column default is an offered value, so a utility with no policy
    row is refused an unoffered value exactly like anybody else."""
    client = _admin(idn)
    assert not SecurityPolicy.objects.filter(tenant=idn.silvercreek).exists()
    assert api_put(client, "/settings/security-policy", {"lockout_minutes": 23}).status_code == 422
    for field, choices in THE_FOUR.items():
        assert services.SETTING_LIMITS[field]["default"] in choices, field


def test_the_engine_reads_a_retained_value_unchanged(idn):
    """`security_policy_values` is the SIGN-IN's read as well as the screen's —
    a retained value must go on being the number the engine obeys."""
    _plant_off_list(idn, lockout_minutes=23)
    assert selectors.security_policy_values(idn.silvercreek.id)["lockout_minutes"] == 23

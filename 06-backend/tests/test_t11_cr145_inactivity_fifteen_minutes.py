# ── Trace ──────────────────────────────────────────────
# Change:   CR-145-BRC08 task T11 — an admin sets inactivity to 15 minutes and
#           the user is signed out after 15 minutes idle.
# Rules:    BR-IDN-026 as amended (PO ruling 2026-09-28, "Im okay with these
#           limit") — the idle choices become 15/30/45/60, default 60, and the
#           prototype's 240 and 480 are WITHDRAWN.
# Stories:  US-IDN-010 §3 (the admin saves it) · US-IDN-003 §3 (the session
#           enforces it) — T11 is the pair, end to end, which is why it is one
#           test and not two.
# ───────────────────────────────────────────────────────
"""T11 — the END TO END of `CR-145-BRC08`, in one test on purpose.

⚠ **PROVED RED BEFORE THE CHANGE, AND THE RED IS AT THE FIRST STEP RATHER THAN
THE LAST.** Against the unchanged build this file fails on the SAVE, not on the
sign-out: `SESSION_TIMEOUT_OPTIONS = (30, 60, 240, 480)` in
`apps/identity/services.py` has no 15 in it, so `PUT /settings/security-policy`
answers 422 `VAL_RANGE` with `params.allowed == [30, 60, 240, 480]` and no
utility can be put on a fifteen-minute timeout at all.

⚠ **CORRECTED 2026-09-28 (backend lane, on the first run this file ever had).**
This paragraph used to quote a "measured failure" of `assert 400 == 200`. It was
never measured — the file had not been run — and it could not have been: this
repo maps `VAL_RANGE` to **422**, not 400 (`core/errors.py`). The first real run
went red on all three cases, and three faults were this file's own rather than
the product's: it expected 400 for the refusal; it measured idle time from
sign-in instead of from the last request (a `/me` call slides `last_seen_at`);
and it let the ADMIN's own session idle out under the 15 minutes it had just
chosen, then used that dead session to save. The fourth fault was real and was
the product's: `SecurityPolicySerializer` did not declare the five new fields,
so DRF dropped them before validation — fixed in `identity/api.py` in the same
commit. A claimed red that nobody ran is hard-won law 7's first clause.

**That is the honest shape of this red and it is worth naming**, because a test
that only advanced a clock would have gone green against the old build the
moment somebody wrote 15 into the option tuple and nothing else — the enforcing
half is already generic over the policy row, so the ONLY thing that was ever
missing is permission to choose the value. A green here therefore has to be
bought by both halves, and the second half is asserted below rather than
assumed.

⚠ **`test_second_case_the_floor_is_not_the_default` EXISTS BECAUSE 60 IS THE
DEFAULT.** A fixture that never leaves the default cannot tell a working setting
from a hardcoded constant, which is hard-won law 7's "what would make this check
pass wrongly": with `session_timeout_minutes` ignored entirely and 60 baked in,
every case at 60 still passes. Fifteen is the value that separates them.
"""

import pytest

from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    api_get,
    api_put,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db


def test_t11__admin_sets_fifteen_minutes_and_the_user_is_signed_out_at_fifteen(idn):
    """The whole of T11: Alex chooses 15, Priya goes idle, Priya is signed out."""
    idn.seed_silvercreek()
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")

    # 1 · THE ADMIN SETS IT. This is the step that is RED before the change:
    #     15 is not in SESSION_TIMEOUT_OPTIONS, so the save is refused 422.
    saved = api_put(alex, "/settings/security-policy", {"session_timeout_minutes": 15})
    assert saved.status_code == 200, saved.content

    # 2 · IT IS READ BACK. A save that 200s and stores nothing is the failure
    #     this assertion exists for.
    read_back = api_get(alex, "/settings/security-policy")
    assert read_back.status_code == 200
    assert read_back.json()["session_timeout_minutes"] == 15

    # 3 · THE USER IS STILL SIGNED IN AT FOURTEEN MINUTES. Without this, a
    #     session that expired at ANY interval would satisfy step 4.
    idn.clock.advance(minutes=14)
    assert api_get(priya, "/me").status_code == 200

    # 4 · AND SIGNED OUT AFTER FIFTEEN. ⚠ Measured from the step-3 request,
    #     not from sign-in: that `/me` slid `last_seen_at` forward, so idle time
    #     restarted there. 15 minutes and 1 second of silence is the boundary.
    idn.clock.advance(minutes=15, seconds=1)
    assert api_get(priya, "/me").status_code == 401


def test_t11__the_floor_is_not_the_default(idn):
    """15 must behave DIFFERENTLY from 60, or the setting is not being read.

    At 30 minutes idle a utility on 15 is out and a utility on 60 is not. One
    clock, two policies, opposite answers — which no hardcoded constant can
    produce.
    """
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    assert (
        api_put(alex, "/settings/security-policy", {"session_timeout_minutes": 15}).status_code
        == 200
    )
    priya = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    idn.clock.advance(minutes=30)
    assert api_get(priya, "/me").status_code == 401, "15-minute utility must be out at 30"

    # ⚠ Alex idled the same 30 minutes under the same 15-minute rule, so Alex
    # is signed out too — the setting working, not a fault. Sign in again.
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    assert (
        api_put(alex, "/settings/security-policy", {"session_timeout_minutes": 60}).status_code
        == 200
    )
    priya_again = signed_in_client("priya@silvercreek.example", "Meadow2026sage")
    idn.clock.advance(minutes=30)
    assert api_get(priya_again, "/me").status_code == 200, "60-minute utility must still be in"


def test_t11__the_withdrawn_choices_are_refused_by_the_server(idn):
    """240 and 480 are WITHDRAWN, and a select is not a validation.

    Dropping them from the tab's array leaves the endpoint accepting them, and
    then a utility can still be put on eight hours by anything that is not the
    tab. The ruling withdrew the CHOICE, so the server is where it is withdrawn.
    """
    idn.seed_silvercreek()
    alex = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    for withdrawn in (240, 480):
        response = api_put(
            alex, "/settings/security-policy", {"session_timeout_minutes": withdrawn}
        )
        # 422 `VAL_RANGE` (never 400 in this repo), naming the field and what
        # IS allowed, so the refusal can be read and not merely counted.
        assert response.status_code == 422, f"{withdrawn} must be refused, got {response.status_code}"
        named = [
            fe for fe in response.json()["field_errors"] if fe["field"] == "session_timeout_minutes"
        ]
        assert named and named[0]["params"]["allowed"] == [15, 30, 45, 60], response.content
    for allowed in (15, 30, 45, 60):
        response = api_put(
            alex, "/settings/security-policy", {"session_timeout_minutes": allowed}
        )
        assert response.status_code == 200, f"{allowed} must be accepted, got {response.status_code}"

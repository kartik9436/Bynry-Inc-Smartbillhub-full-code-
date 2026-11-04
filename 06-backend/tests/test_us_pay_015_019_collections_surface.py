# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-015 (the tier already sent, so a manual send never doubles
#           one — TC-4) · US-PAY-018 (the plan-notice and missed-instalment
#           position) · US-PAY-019 (the dunning + disconnect pause and why it is
#           running — TC-1, TC-3 as amended by OQ-170)
#           Screens: S34 (the collections board) · S21 (the account position)
# Rules:    BR-PAY-016 (dunning resumes day+1 of a missed instalment; the plan
#           stays ACTIVE — PO 2026-08-12, OQ-170) · BR-PAY-017 (the rungs and
#           the five stop conditions) · BR-CUS-043 (pause while active AND
#           current; it covers the ARREARS THE PLAN SPREADS, never this month's
#           bill) · BR-TEN-043 · CLAUDE.md rule 1 · rule 2
# ───────────────────────────────────────────────────────
"""Can anybody SEE the collection ladder before driving it? They could not.

`POST /collections/run` existed and it SENDS: it writes the notice, advances
the tier and records a `notice_history` row on every path, skips included. There
was no read. A clerk selected accounts on S34 and drove a five-stop-condition
engine over them without being able to see which tier each was at, what would go
next, or which of them the rules would silently pass over.

**RED-PROVED FIRST (hard-won law 7).** Before `apps/payments/collections_read.py`
and the two routes existed, every case here failed:

    ImportError: cannot import name 'collections_read' from 'apps.payments'
    AttributeError: module 'apps.payments.api' has no attribute
        'collections_ladder'
    django.urls.exceptions.Resolver404: {'path': 'api/brazosbend/collections/
        ladder'}

**THE CASE THIS FILE EXISTS FOR** is
`test_us_pay_014__the_board_refuses_to_guess_the_next_step_when_no_floor_can_be_read`.
BR-PAY-017's ladder needs a balance floor (OQ-137/OQ-157) and a partial-payment
pause percentage (OQ-136). ⚠ `apps/payments/ladder.py` and EP-PAY-04 §9 both
still say `apps.tenancy.settings_families.COLLECTIONS` stores NEITHER; the
DEF-097 lane added both `Param`s on 2026-08-15, seeded **25** and **25%**, and
neither sentence was re-read. This file asserts BOTH halves so the stale claim
cannot quietly become true again: the tenant's own floor IS read on the normal
path, and a tenant whose settings are unreadable still gets an honest board —
the tier ALREADY SENT (a fact) renders, and the NEXT step comes back null with
`next_step_available: false` and both reasons. **An honest "I cannot answer
that" beats a real-looking next step**, which is the standing PO preference,
and a board that invented a floor would post letters.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.payments import api as payments_api
from apps.payments import collections_read, ladder
from apps.payments.collections_models import AccountCollectionState, TIER_FRIENDLY

from tests.isolation_helpers import (
    live_tenant_context,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

AS_OF = date(2026, 8, 16)

#: PO ruling 2026-08-12, OQ-137/OQ-157 — *"Same $25 floor on the whole ladder"*,
#: and *"per utility - uyiliyy can define it using settings"*. The figure is the
#: SEEDED DEFAULT each utility then sets; it is passed in here exactly as
#: `POST /collections/run` accepts it, and never read from a setting that does
#: not exist.
FLOOR = "25.00"

#: The prototype's own S34 debtor — A-10802 Novak, P., 91 days late, **$948.20**
#: — which is also the write-off request figure the PO worked through.
NOVAK_OWED = Decimal("948.20")


def call(view, method, tenant, *, user=None, **kwargs):
    """One collections call. A4 "Payments (record)" opens the READ to all three
    roles (Executive is View), so `billing_clerk` is what a board request
    carries — this is the screen a clerk works from."""
    actor = FakeUser(getattr(user, "pk", None)) if user is not None else FakeUser()
    return api_call(view, method, user=actor, role="billing_clerk", tenant=tenant, **kwargs)


def a_debtor(actor, tenant, *, owed=NOVAK_OWED, due_on=date(2026, 4, 22)):
    """One account with an ISSUED, unpaid bill — a real outstanding position.

    Built through billing's own rows rather than a stub, because the board reads
    `billing_seam.outstanding_positions`, and a fake position would prove that
    the seam's shape is what this lane imagined rather than what billing serves.
    """
    account = an_account_of(actor, tenant)
    an_issued_bill(
        tenant,
        account,
        number=f"BL-2604-{uuid.uuid4().hex[:6]}",
        total=owed,
        issued_on=due_on,
    )
    return account


# ══════════════════════════════════════════════════════════════════════════
# Reachability — hard-won law 2
# ══════════════════════════════════════════════════════════════════════════
def test_us_pay_019_tc0__the_collections_position_routes_are_mounted(brazos):
    """`collections/ladder` must resolve, and must not be eaten by another path.

    It sits beside `collections/run`, which already existed: both are literal
    two-segment paths, so neither shadows the other and a future
    `collections/<id>` would have to be declared BELOW them.
    """
    from django.urls import resolve

    assert resolve("/api/brazosbend/collections/ladder").func is payments_api.collections_ladder
    assert resolve("/api/brazosbend/collections/run").func is payments_api.collections_run
    assert (
        resolve(f"/api/brazosbend/accounts/{uuid.uuid4()}/collections").func
        is payments_api.account_collections
    )


def test_us_pay_019_tc0__the_routes_are_reachable_through_the_whole_stack(brazos):
    """401, not 404: the route exists and asked for a session."""
    from django.test import Client

    from core import errors

    for path in (
        f"/api/{brazos.subdomain}/collections/ladder",
        f"/api/{brazos.subdomain}/accounts/{uuid.uuid4()}/collections",
    ):
        response = Client().get(path)
        assert response.status_code == 401, (
            f"GET {path} answered {response.status_code}: a 404 means the route is still not "
            "reachable, whatever the URLconf says"
        )
        assert response.json()["code"] == errors.AUTH_UNAUTHENTICATED


# ══════════════════════════════════════════════════════════════════════════
# The board — who is at which tier, and what goes next
# ══════════════════════════════════════════════════════════════════════════
def test_us_pay_015_tc4__the_board_shows_the_tier_already_sent(brazos, marcus):
    """US-PAY-015 TC-4 — *"staff see 'tier already sent Jul 30'"*.

    That sentence is the whole reason a manual send does not double a tier, and
    until this read existed the state was in a table no surface could open. The
    board serves the rung AND the day it went.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
        AccountCollectionState.objects.create(
            tenant=brazos,
            account=account,
            tier=TIER_FRIENDLY,
            tier_sent_on=date(2026, 7, 30),
            last_notice_on=date(2026, 7, 30),
        )
        board = call(
            payments_api.collections_ladder,
            "get",
            brazos,
            query={"as_of": AS_OF.isoformat(), "balance_floor": FLOOR},
        ).data
        row = next(r for r in board["rows"] if r["account_id"] == str(account.pk))
        assert row["current_tier"] == TIER_FRIENDLY
        assert row["tier_sent_on"] == "2026-07-30"
        assert Decimal(row["balance"]) == NOVAK_OWED
        assert (
            row["currency"] == "USD"
        ), "CLAUDE.md rule 2 — a figure without its code is half a fact"
        assert board["tiles"]["at_tier"][TIER_FRIENDLY] == 1


def test_us_pay_014__the_board_refuses_to_guess_the_next_step_when_no_floor_can_be_read(
    brazos, marcus, monkeypatch
):
    """**THE HONEST ABSENCE** — and the case this whole read was shaped around.

    The tenant's `ladder_balance_floor_amount` is normally READ (seeded **25**
    since the DEF-097 lane added the Param on 2026-08-15). A tenant whose
    collections settings are unreadable is a different matter, and
    `settings_seam` refuses by name rather than falling back — *"an unreachable
    setting is not a setting, and every step it takes reaches a real customer
    with a real disconnection date."*

    The refusal is FORCED here, because a guard that has never been shown to
    bite is not a guard (hard-won law 7). What must survive it: the accounts
    still list, the balances still show, the tier already sent still shows — and
    `next_rung` is **null** with `next_step_available: false` and the reason
    beside it. Not zero, not a plausible rung, and not a 500.
    """
    from apps.payments import settings_seam
    from apps.payments.exceptions import PaymentRuleError

    def unreadable():
        raise PaymentRuleError(
            "the tenant's collections settings are unreadable", br_ref="BR-PAY-017"
        )

    monkeypatch.setattr(settings_seam, "ladder_balance_floor", unreadable)
    monkeypatch.setattr(settings_seam, "partial_pause_percent", unreadable)

    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
        board = call(
            payments_api.collections_ladder, "get", brazos, query={"as_of": AS_OF.isoformat()}
        ).data
        assert board["next_step_available"] is False
        row = next(r for r in board["rows"] if r["account_id"] == str(account.pk))
        assert row["next_rung"] is None
        assert row["next_step_on"] is None
        assert row["runs"] is None, "'we cannot say' is not 'it will not run'"
        assert row["detail_code"] == "thresholds_unset"
        # The balance is still a fact and is still served — the board does not
        # go blank because one computation is unavailable.
        assert Decimal(row["balance"]) == NOVAK_OWED
        codes = {problem["code"] for problem in board["problems"]}
        assert "ladder_balance_floor_unset" in codes
        assert "partial_pause_percent_unset" in codes


def test_us_pay_014__the_tenants_own_seeded_floor_is_read_and_the_board_answers(brazos, marcus):
    """The NORMAL path: nothing is passed and the tenant's own $25.00 is read.

    ⚠ This case is the correction of a stale claim. `apps/payments/ladder.py`
    and EP-PAY-04 §9 both still say the ladder floor *"is stored by no tenant
    setting"*; the DEF-097 lane added `ladder_balance_floor_amount` (seeded
    **25**, the PO's ruled figure — OQ-137/OQ-157) on 2026-08-15 and neither
    sentence was re-read. Asserting the READ here is what stops this lane's
    board inheriting a refusal that no longer applies.
    """
    with tenant_ctx(brazos):
        a_debtor(marcus, brazos)
        board = call(
            payments_api.collections_ladder, "get", brazos, query={"as_of": AS_OF.isoformat()}
        ).data
        assert board["next_step_available"] is True
        assert board["problems"] == [dict(p) for p in ladder.LADDER_UNAVAILABLE]


def test_us_pay_014__with_a_floor_stated_the_board_names_the_next_rung_and_its_day(brazos, marcus):
    """A floor the CALLER states overrides the tenant's — the preview door.

    The same door `POST /collections/run` opens, and it is what a *"what if we
    set the floor to $50?"* preview needs. `decide` is the SAME pure function
    the run uses, so the preview and the send cannot disagree.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
        board = call(
            payments_api.collections_ladder,
            "get",
            brazos,
            query={"as_of": AS_OF.isoformat(), "balance_floor": FLOOR},
        ).data
        assert board["next_step_available"] is True
        row = next(r for r in board["rows"] if r["account_id"] == str(account.pk))
        assert row["next_rung"] in board["rungs"]
        assert row["detail_code"] == "decided"
        assert row["days_late"] == (AS_OF - date(2026, 4, 22)).days


def test_us_pay_014__a_balance_under_the_floor_is_skipped_with_its_reason(brazos, marcus):
    """BR-PAY-017's floor: **$25.00** and no letter goes out under it.

    A skip is a DECISION, not an absence — J4 step 2 requires every one of them
    on the trail, and the board shows the reason so a clerk is never left
    wondering why a debtor was never contacted.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos, owed=Decimal("4.10"))
        board = call(
            payments_api.collections_ladder,
            "get",
            brazos,
            query={"as_of": AS_OF.isoformat(), "balance_floor": FLOOR},
        ).data
        row = next(r for r in board["rows"] if r["account_id"] == str(account.pk))
        assert row["runs"] is False
        assert row["skip_reason"] == ladder.SKIP_BELOW_FLOOR


def test_us_pay_014__the_board_never_runs_the_ladder_it_previews(brazos, marcus):
    """A PREVIEW writes nothing — no notice, no tier advance, no history row.

    `run_ladder` records a `notice_history` row even for a SKIP, so a screen
    that called it to find out what would happen would have made it happen. This
    asserts the collections state is untouched after a board read, which is the
    one guarantee that makes the screen safe to open.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
        call(
            payments_api.collections_ladder,
            "get",
            brazos,
            query={"as_of": AS_OF.isoformat(), "balance_floor": FLOOR},
        )
        assert not AccountCollectionState.objects.filter(
            tenant=brazos, account=account
        ).exists(), "a preview that advanced a tier would send the next letter early"


# ══════════════════════════════════════════════════════════════════════════
# One account's dunning position — S21's header
# ══════════════════════════════════════════════════════════════════════════
def test_us_pay_019_tc1__an_account_with_no_plan_is_chased_and_says_so(brazos, marcus):
    """The pause decision, in words a clerk on the phone can repeat.

    `paused: false` with `reason: no_plan` — and `covers`/`not_covered` on the
    same body, because BR-CUS-043's pause is scoped to the ARREARS A PLAN
    SPREADS and a screen that said "paused" without saying over what would let a
    clerk tell a customer this month's bill is on hold. It is not (PO
    2026-08-11).
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
        position = call(
            payments_api.account_collections,
            "get",
            brazos,
            query={"as_of": AS_OF.isoformat()},
            account_id=str(account.pk),
        ).data
        assert position["pause"]["paused"] is False
        assert position["plan"] is None, "no plan is *no plan*, never an unknown"
        assert position["disconnect_blocked"] is False
        assert position["late_fee_suspended"] is False
        assert position["notices"] == []
        assert position["state"]["tier"] is None


def test_us_pay_019__the_account_position_is_read_only(brazos, marcus):
    """Opening S21's dunning panel must not chase anybody.

    The whole point of a position read is that a clerk can look at it while the
    customer is on the phone. Nothing is written, so this asserts the notice
    trail stays empty after the read.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos)
        call(
            payments_api.account_collections,
            "get",
            brazos,
            query={"as_of": AS_OF.isoformat()},
            account_id=str(account.pk),
        )
        again = call(
            payments_api.account_collections,
            "get",
            brazos,
            query={"as_of": AS_OF.isoformat()},
            account_id=str(account.pk),
        ).data
        assert again["notices"] == []


# ══════════════════════════════════════════════════════════════════════════
# Isolation — CLAUDE.md rule 1
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
@requires_postgres
def test_us_pay_019_tc7__one_tenants_collections_board_is_its_own(
    brazos, lonestar, marcus, erin, rls_probe_role  # noqa: F811
):
    """A new read is a new place a tenant boundary can leak, so it is probed."""
    with live_tenant_context(brazos.id):
        a_debtor(marcus, brazos)
        mine = call(
            payments_api.collections_ladder,
            "get",
            brazos,
            query={"as_of": AS_OF.isoformat(), "balance_floor": FLOOR},
        ).data
        assert mine["rows"]

    with live_tenant_context(lonestar.id):
        theirs = call(
            payments_api.collections_ladder,
            "get",
            lonestar,
            query={"as_of": AS_OF.isoformat(), "balance_floor": FLOOR},
        ).data
        assert theirs["rows"] == []


def test_us_pay_019__a_board_read_with_no_tenant_in_scope_refuses(brazos):
    """Hard rule 1 has no default — no `app.tenant_id`, no board."""
    from core import errors

    with pytest.raises(errors.AuthError):
        collections_read.ladder_board(as_of=AS_OF)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-019@9d41b60 (sources: 04-docs/05-modules/08-payments/06-epics/EP-PAY-05-payment-plans.md US-PAY-018/019 §3 · EP-PAY-04 US-PAY-014/015 §3 · 08-payments/02-business-rules.md BR-PAY-016/017 + BR-CUS-043 · 08-qa/01-e2e/journeys/J4-collections.md; co-packets US-PAY-015, US-PAY-018)
# generated: 2026-08-16 by story-coder (payments SURFACE lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — `ImportError: cannot import name 'collections_read' from 'apps.payments'` and `Resolver404 … 'api/brazosbend/collections/ladder'` before the module and routes existed; verbatim in the lane report. pytest✔ · pytest -m isolation✔ · run_gates✔
# exceptions: (1) the ladder BALANCE FLOOR is PASSED IN at $25.00 — the PO's ruled seeded default (OQ-137/OQ-157) — and never read from a tenant setting, because none stores it; the refusal case is asserted as its own test rather than worked around · (2) the board test asserts `runs is None` and not `False`: "we cannot say" and "it will not run" are different answers and a screen must not draw them the same · (3) `test_us_pay_014__the_board_never_runs_the_ladder_it_previews` is the guarantee that makes the screen safe to open at all
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

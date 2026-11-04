# ── Trace ──────────────────────────────────────────────
# Defect:  **DEF-CUS-7680** — the disconnect wizard refuses on step 4 and names
#          no reason. `POST /disconnects/schedule` answers `422
#          BIZ-COMPLETENESS` with the exact cause in `params.code`, and until
#          this lane no screen read it. Reported by the Product Owner from
#          deployed `v2.352.0`, trace reference `2FA5-0006`,
#          *"Diagnostic: none shown"*.
# Rules:   BR-CUS-039 (the ladder, its tiers and the certified final notice) ·
#          BR-CUS-082 (a closed account cannot be escalated to disconnection;
#          a collections sequence cannot reach a cut) · BR-SHL-020 r2 (server
#          `detail` text never reaches a customer screen — the CODE is what a
#          screen branches on) · CLAUDE.md hard rule 1 (tenant scoping) ·
#          hard-won law 2 (built is not wired) · law 7 (prove a guard RED
#          first, in the harness that will run it)
# Tests:   this file
# Impacts: apps/customers/transfer_disconnect_api.py (`_as_catalog_refusal`,
#          `account_ladder`) · apps/customers/disconnect_reads.py
#          (`schedule_readiness`) · 07-frontend/src/features/customers/
#          disconnect/disconnectRefusal.ts (the screen half)
# ───────────────────────────────────────────────────────
"""The server half of `DEF-CUS-7680`: the refusal names itself, and step 1 can ask.

WHAT WAS ACTUALLY WRONG, AND WHY A BACKEND TEST IS OWED FOR A SCREEN DEFECT
---------------------------------------------------------------------------
`_as_catalog_refusal`'s own docstring states the contract the screen broke:

    *"The service's `code` rides alongside so a screen can branch without
    parsing English."*

The code was published, correctly, from the day the function was written. What
nothing anywhere asserted is that it KEEPS being published — so a lane adding a
refusal, or tidying the params dict, could remove the one fact the screen now
depends on and every check in this repository would stay green. **That is the
test this file is, and it is the half a frontend suite cannot write**: the
front end can only assert what a fixture hands it, and a fixture is a statement
about what somebody THINKS the server sends.

⚠ **RUN IT THE WAY CI DOES, IN THE HARNESS THAT WILL RUN IT (law 7):**
`pytest --ds=config.settings.pgtest tests/test_def_cus_7680_*` against real
PostgreSQL, never a `python3 <file>` and never a `__main__`. On the fixed tree:
**9 passed in 1416s.**

⚠ **THE RED PROOF IS SPLIT ACROSS THE TWO HALVES OF THIS DEFECT, AND SAYING
WHICH HALF EACH CASE PROVES IS PART OF IT** — a reader cannot tell a speaking
case from a guard by looking at a green dot.

  * **THE SIX PRE-FLIGHT CASES GO RED WITHOUT THIS LANE, MEASURED** in a second
    `git worktree` at the pre-change tip `30714881f` with this file copied in
    and nothing else — `6 failed, 3 passed in 619s` — every failure reading

        AttributeError: module 'apps.customers.disconnect_reads' has no
        attribute 'schedule_readiness'

    **A red that is only a missing symbol is a weak red** (the frontend half of
    this defect made exactly that mistake and its suite's header records it),
    which is why the three below matter more.
  * **THE THREE REFUSAL-ENVELOPE CASES PASS ON THE UNFIXED TREE AND ARE MEANT
    TO** — `..._carries_its_code_and_its_detail`, `..._one_code_and_one_key_...`
    and `..._not_a_rule_id_...`. **The server was never the broken half.** They
    exist because the SCREEN now depends on `params.code`: the day somebody
    tidies that key out of the params dict, or renames a code the catalogue is
    keyed on, these go red and name the route. Without them the defect can come
    back from the other end with every frontend test still green.

⚠ **THE FIXTURE'S OWN FIRST RUN IS THE MEASURED RED WORTH READING, AND IT IS
HARD-WON LAW 14.** The first draft mutated ONE case through three scenarios and
set `cut_on` alone: `2 failed, 7 passed, 2 errors`, the errors being a teardown
poisoned by an aborted PostgreSQL transaction after
`ck_cut_records_the_price_of_coming_back` refused the row. **On SQLite — the
default suite — it would have been green.** See `plant_case`.
"""

from datetime import date, timedelta
from decimal import Decimal as D
from typing import Any

import pytest

from apps.customers import disconnect_reads, disconnects
from apps.customers import models as customers_models
from apps.customers import transfer_disconnect_api as api
from apps.metering import models as metering_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

TODAY = date(2026, 5, 11)
CUT_ON = TODAY + timedelta(days=14)


# ══════════════════════════════════════════════════════════════════════════
# Fixtures — `test_disconnect_wizard_cr125_brc07.py`'s, deliberately the same
# ══════════════════════════════════════════════════════════════════════════
def plant_account(tenant, *, tag: str, no: str | None = None):
    """One account with a premises and a unit (`BR-MET-1161`: the address lives
    on `premises` and every other entity walks to it)."""
    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line=f"9 Foundry Lane {tag}", city="Silver Creek", state="TX"
    )
    unit = metering_models.Unit.objects.create(
        tenant=tenant, premises=premises, label=f"Bay {tag}"
    )
    status = customers_models.AccountStatus.objects.filter(tenant=tenant).first()
    account_type = customers_models.AccountType.objects.filter(tenant=tenant).first()
    return customers_models.Account.objects.create(
        tenant=tenant,
        unit=unit,
        premises_id=premises.id,
        account_no=no or f"A-{tag}",
        status=status,
        account_type=account_type,
    )


def plant_case(tenant, account, *, tier=None, state=None, sequence=None, cut_on=None):
    """One case, planted LAWFULLY — every scenario on its own account.

    ⚠ **A CUT ROW CARRIES THE PRICE OF COMING BACK, AND THE DATABASE SAYS SO —
    THIS FIXTURE'S FIRST DRAFT DID NOT, AND IT COST A RUN.**
    `ck_cut_records_the_price_of_coming_back` refuses a row with `cut_on` set
    and no `reconnection_fee_amount`, `reconnection_fee_code` or
    `deposit_disposition` beside it (*"a row saying service was cut, with no
    fee and no deposit election, is a record that cannot answer the question
    the customer will ask first"*). The first draft of these cases MUTATED one
    case through three scenarios and set `cut_on` alone; on PostgreSQL the
    failed statement aborted the transaction and everything after it raised
    `InFailedSqlTransaction` — **CLAUDE.md hard-won law 14 exactly, and on
    SQLite it would have sailed through.** Measured: `2 failed, 7 passed, 2
    errors`, the two errors being the poisoned teardown.

    So: one account per scenario, every row lawful at INSERT, nothing mutated
    into a shape the schema forbids.
    """
    cut_extras: dict[str, Any] = {}
    if cut_on is not None:
        cut_extras = {
            "reconnection_fee_amount": D("75.0000"),
            "reconnection_fee_code": "CC-RECON",
            "deposit_disposition": disconnects.DEPOSIT_HELD,
        }
    return disconnects.DisconnectCase.objects.create(
        tenant=tenant,
        account=account,
        sequence=sequence or disconnects.SEQ_SERVICE,
        state=state or disconnects.STATE_NOTICE_SENT,
        tier=tier if tier is not None else disconnects.TIER_1,
        tier_reached_on=TODAY,
        amount_owed_at_open=D("2410.0000"),
        currency="USD",
        opened_on=TODAY,
        cut_on=cut_on,
        **cut_extras,
    )


class _EveryAccount(dict):
    """A positions map answering one figure for any id — `test_w7_worklists._owes`'
    shape, so the LEDGER BOUNDARY is the real `seams.ArPositions`."""

    def __init__(self, amount):
        super().__init__()
        self._amount = amount

    def get(self, _key, _default=None):
        return self._amount


def owes(monkeypatch, amount=D("2410.75")):
    """Publish a readable AR position.

    ⚠ **WITHOUT THIS THE LADDER CORRECTLY REFUSES `nothing_owed` AND EVERY CASE
    BELOW MEASURES THE WRONG REFUSAL.** That is the module working, not a bug,
    and it is worth the fixture rather than the confusion."""

    class _Pos:
        invoices = ()
        problems = ()
        balance = amount

        def __init__(self, *_a, **_k):
            pass

    monkeypatch.setattr(
        disconnects, "_balance_for", lambda _account_id: amount, raising=True
    )
    return _EveryAccount(_Pos())


def refuse(fn):
    """Run a service call through the route's OWN boundary and return the envelope.

    ⚠ **`_laddered` AND NOT A HAND-BUILT `BizError`.** The whole subject of this
    file is what the BOUNDARY does with a refusal, so a test that constructed
    the envelope itself would assert its own fixture — law 7's *looking at the
    wrong thing*. This is the exact call `POST /disconnects/schedule` makes.
    """
    with pytest.raises(errors.BizError) as raised:
        api._laddered(fn)
    return raised.value


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE CONTRACT THE SCREEN NOW DEPENDS ON
# ══════════════════════════════════════════════════════════════════════════
def test_every_refusal_this_route_can_raise_carries_its_code_and_its_detail(
    brazos, dana, monkeypatch
):
    """⛔ **THE FACT `DEF-CUS-7680`'s SCREEN HALF READS, PINNED AT THE SOURCE.**

    Six refusals, each reached the way a clerk reaches it, each put through the
    route's own boundary. Every one must arrive carrying BOTH halves:

      * `params["code"]` — the machine handle the screen branches on;
      * `params["detail"]` — the service's own sentence, for the server log and
        the `BR-AUD-018` attempt row. It is NEVER rendered (`BR-SHL-020` r2),
        and it must never be dropped either: it is the only place the exact
        reason survives for support.

    ⚠ **THE CODES ARE SPELLED OUT RATHER THAN READ BACK FROM THE EXCEPTION.** A
    case that asserted `params["code"] == refusal.code` would pass over a
    boundary that published the wrong key entirely, and over a service that
    renamed a code the screen is keyed on. These strings are the CONTRACT, and
    changing one is a catalogue change in eleven languages.
    """
    owes(monkeypatch)
    with tenant_ctx(brazos):
        # ── no_open_case — the one the Product Owner actually hit ──────────
        bare = plant_account(brazos, tag="c1")
        envelope = refuse(
            lambda: disconnects.schedule_cut(dana, bare.id, cut_on=CUT_ON, as_of=TODAY)
        )
        assert envelope.params["code"] == "no_open_case"
        assert envelope.params["detail"], "the service's sentence must not be dropped"

        # ── cut_before_final_tier ─────────────────────────────────────────
        tier_1 = plant_account(brazos, tag="c2")
        plant_case(brazos, tier_1)
        envelope = refuse(
            lambda: disconnects.schedule_cut(dana, tier_1.id, cut_on=CUT_ON, as_of=TODAY)
        )
        assert envelope.params["code"] == "cut_before_final_tier"
        assert envelope.params["detail"]

        # ── cut_reason_unknown — a payload refusal, before the case is read ─
        envelope = refuse(
            lambda: disconnects.schedule_cut(
                dana, tier_1.id, cut_on=CUT_ON, as_of=TODAY, reason="because"
            )
        )
        assert envelope.params["code"] == "cut_reason_unknown"
        assert envelope.params["detail"]

        # ── deposit_disposition_unknown ───────────────────────────────────
        envelope = refuse(
            lambda: disconnects.schedule_cut(
                dana, tier_1.id, cut_on=CUT_ON, as_of=TODAY, deposit="spend_it"
            )
        )
        assert envelope.params["code"] == "deposit_disposition_unknown"
        assert envelope.params["detail"]

        # ── collections_sequence_cannot_cut — BR-CUS-082 ──────────────────
        chased = plant_account(brazos, tag="c3")
        plant_case(brazos, chased, sequence=disconnects.SEQ_COLLECTIONS)
        envelope = refuse(
            lambda: disconnects.schedule_cut(dana, chased.id, cut_on=CUT_ON, as_of=TODAY)
        )
        assert envelope.params["code"] == "collections_sequence_cannot_cut"
        assert envelope.params["detail"]

        # ── already_cut — DEF-CUS-6062, and it outranks all of the above ──
        cut = plant_account(brazos, tag="c4")
        plant_case(brazos, cut, state=disconnects.STATE_CUT, cut_on=TODAY)
        envelope = refuse(
            lambda: disconnects.schedule_cut(dana, cut.id, cut_on=CUT_ON, as_of=TODAY)
        )
        assert envelope.params["code"] == "already_cut"
        assert envelope.params["detail"]


def test_the_envelope_is_one_code_and_one_key_for_all_of_them(brazos, dana, monkeypatch):
    """`_as_catalog_refusal`'s other half: ONE catalog code, ONE message key.

    That is deliberate and it is why `params.code` has to carry the difference —
    *"picking among the nine BIZ codes per refusal would be this layer
    INTERPRETING rules it does not own."* A lane that "fixed" this defect by
    minting a BIZ code per refusal would break `G9` and hand the interpretation
    to the wrong layer; this case says so in a way that goes red.
    """
    owes(monkeypatch)
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="c2")
        plant_case(brazos, account)
        for kwargs in ({}, {"reason": "because"}, {"deposit": "spend_it"}):
            envelope = refuse(
                lambda kw=kwargs: disconnects.schedule_cut(
                    dana, account.id, cut_on=CUT_ON, as_of=TODAY, **kw
                )
            )
            assert envelope.code == errors.BIZ_COMPLETENESS
            assert envelope.message_key == "customers.disconnects.refused"
            assert envelope.br_ref, "hard rule B8 — every BIZ refusal cites its rule"


def test_the_code_is_not_a_rule_id_and_never_reaches_a_clerk_as_copy(
    brazos, dana, monkeypatch
):
    """B14 rule 32 — no rule id and no internal code in clerk-facing copy.

    ⚠ **THIS IS `CR-125-BRC07`'s DEFECT ONE INDIRECTION OUT.** That one put the
    Python keyword `cut_on` into `{{field}}` and eleven catalogues rendered it.
    The fix for `DEF-CUS-7680` hands the screen a code to BRANCH on, which is
    one careless template literal away from printing `cut_before_final_tier` at
    a billing clerk. So the shape is pinned here: the code is snake_case, it is
    never a `BR-` id, and the catalogue value it selects is written by hand in
    eleven languages rather than interpolated from it.
    """
    owes(monkeypatch)
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="c3")
        plant_case(brazos, account)
        envelope = refuse(
            lambda: disconnects.schedule_cut(dana, account.id, cut_on=CUT_ON, as_of=TODAY)
        )
        code = envelope.params["code"]
        assert not code.startswith("BR-"), "a rule id is not a branch key"
        assert code == code.lower() and " " not in code, "a machine handle, not a sentence"
        assert code not in str(envelope.params["detail"]).split(), (
            "the code is a handle and the sentence is prose; they are two facts"
        )


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE STEP-1 PRE-FLIGHT — four refusals a clerk can be spared
# ══════════════════════════════════════════════════════════════════════════
def test_step_one_can_see_the_four_refusals_the_case_already_decides(
    brazos, dana, monkeypatch
):
    """⛔ **A CLERK FILLED FOUR STEPS FOR A CASE THAT COULD NEVER BE SCHEDULED.**

    Each of these is as true when the account is chosen as it is at the commit,
    so each is answerable on step 1 — and `schedule_readiness` answers them with
    the SAME codes the commit refuses with, so one catalogue sentence serves
    both places.
    """
    owes(monkeypatch)
    with tenant_ctx(brazos):
        bare = plant_account(brazos, tag="p1")
        answer = disconnect_reads.schedule_readiness(bare.id, as_of=TODAY)
        assert answer["ready"] is False
        assert answer["refusal"]["code"] == "no_open_case"

        tier_1 = plant_account(brazos, tag="p1b")
        plant_case(brazos, tier_1)
        answer = disconnect_reads.schedule_readiness(tier_1.id, as_of=TODAY)
        assert answer["ready"] is False
        assert answer["refusal"]["code"] == "cut_before_final_tier"

        chased = plant_account(brazos, tag="p1c")
        plant_case(brazos, chased, sequence=disconnects.SEQ_COLLECTIONS)
        codes = [
            row["code"]
            for row in disconnect_reads.schedule_readiness(chased.id, as_of=TODAY)["blockers"]
        ]
        assert "collections_sequence_cannot_cut" in codes

        cut = plant_account(brazos, tag="p1d")
        plant_case(brazos, cut, state=disconnects.STATE_CUT, cut_on=TODAY)
        answer = disconnect_reads.schedule_readiness(cut.id, as_of=TODAY)
        assert answer["refusal"]["code"] == "already_cut", (
            "`already_cut` outranks the rest here exactly as it does in `schedule_cut`"
        )


def test_the_preflight_answers_in_the_commits_own_order(brazos, dana, monkeypatch):
    """The FIRST blocker is the sentence the clerk would really have been given.

    `schedule_cut` stops at its first refusal. A preview that reported them in
    any other order would put a different sentence on step 1 from the one the
    commit would produce — two answers to one question, which is the defect
    this repo files as `DEF-127`'s shape.
    """
    owes(monkeypatch)
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="p2")
        # A case that is BOTH below tier 3 AND on a collections sequence.
        plant_case(brazos, account, sequence=disconnects.SEQ_COLLECTIONS)
        answer = disconnect_reads.schedule_readiness(account.id, as_of=TODAY)
        codes = [row["code"] for row in answer["blockers"]]
        assert codes.index("collections_sequence_cannot_cut") < codes.index(
            "cut_before_final_tier"
        ), "`assert_cut_reachable` runs before the tier test in `schedule_cut`"
        assert answer["refusal"]["code"] == codes[0]


def test_a_case_at_tier_three_on_a_live_account_is_ready(brazos, dana, monkeypatch):
    """The second direction, and it is the one that makes the check worth having.

    A pre-flight that answered *not ready* for everything would stop every
    disconnection in the product and would still pass a suite that only ever
    asserted refusals — law 7's *incapable of passing*, one screen up.
    """
    owes(monkeypatch)
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="p3")
        plant_case(brazos, account, tier=disconnects.TIER_3)
        answer = disconnect_reads.schedule_readiness(account.id, as_of=TODAY)
        assert answer["ready"] is True
        assert answer["blockers"] == []
        assert answer["refusal"] is None


def test_the_ladder_payload_carries_the_preflight_and_keeps_everything_else(
    brazos, dana, monkeypatch
):
    """`GET /accounts/{id}/ladder` is where step 1 asks, and the key is ADDITIVE.

    ⚠ **THE SECOND HALF IS THE POINT.** `cut_floor` rides on this payload for
    the same reason, and a lane adding a key to a shared read is one careless
    dict rebuild away from dropping one. The existing keys are named here so
    that goes red.
    """
    owes(monkeypatch)
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="p4")
        plant_case(brazos, account)

        state = disconnects.ladder_state(account.id, as_of=TODAY).as_dict()
        state["schedule_readiness"] = disconnect_reads.schedule_readiness(
            account.id, as_of=TODAY
        )
        for key in ("runs", "halt_code", "tier", "sequence", "balance", "scheduler"):
            assert key in state, f"the ladder payload lost `{key}`"
        assert state["schedule_readiness"]["refusal"]["code"] == "cut_before_final_tier"


def test_the_preflight_decides_nothing_and_the_commit_still_refuses(
    brazos, dana, monkeypatch
):
    """⚠ **A SCREEN THAT DECIDED ELIGIBILITY FOR ITSELF WOULD BE THE NEXT DEFECT.**

    Days pass between a screen being drawn and a button being pressed, so the
    pre-flight is a PREVIEW and `schedule_cut` re-runs all of it. This proves
    the two halves have not been traded for each other: the read says *not
    ready* AND the commit still refuses, with the same code.
    """
    owes(monkeypatch)
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="p5")
        answer = disconnect_reads.schedule_readiness(account.id, as_of=TODAY)
        assert answer["refusal"]["code"] == "no_open_case"

        envelope = refuse(
            lambda: disconnects.schedule_cut(dana, account.id, cut_on=CUT_ON, as_of=TODAY)
        )
        assert envelope.params["code"] == answer["refusal"]["code"], (
            "the preview and the commit must not be able to disagree"
        )


def test_the_preflight_writes_nothing(brazos, dana, monkeypatch):
    """Read-only, stated and proved. A preview that opened a case would create
    the very thing it was asked to report the absence of."""
    owes(monkeypatch)
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="p6")
        before = disconnects.DisconnectCase.objects.count()
        disconnect_reads.schedule_readiness(account.id, as_of=TODAY)
        disconnect_reads.schedule_readiness(account.id, as_of=TODAY)
        assert disconnects.DisconnectCase.objects.count() == before


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CUS-7680 (MAINTENANCE — 12-governance/22-product-maintenance-
#         process.md). Reproduced first, against real PostgreSQL 16 on a seeded
#         brazosbend, before a line of code was read.
# generated: 2026-09-28 by lane DSC-WIZARD-REFUSAL
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: E3 — the ladder-payload case composes the dict the view composes
#         rather than going through DRF, because the view's own wiring is one
#         line and the suite here has no request factory; the browser walk
#         (10-scripts/def_cus_7680_disconnect_refusal_walkthrough.mjs) drives
#         the real route end to end and is what proves the HTTP half.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

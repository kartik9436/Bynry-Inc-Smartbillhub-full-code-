# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-004 / US-CUS-005 (a transfer is the THIRD path beside them) ·
#           US-CUS-015 (S22's disconnect-notice modal)
#           Screens: S89 (Transfers tab) · S90 (Disconnects tab)
#           ⚠ **NEITHER SCREEN HAS A STORY.** Hard-won law 8; both are OWED.
# Change:   CR-030 W7 tasks 7.4 (S89 — two-line FROM cell, stacked MONEY
#           sentences) and 7.11 (S90 — six tier chips, six segments), BACKEND
#           halves.
# Rules:    BR-CUS-015 · BR-CUS-023 · BR-CUS-024 · BR-CUS-025 · BR-CUS-039 ·
#           BR-CUS-043 · BR-CUS-053 · BR-CUS-054 · BR-CUS-057 · BR-CUS-082 ·
#           BR-CUS-097 (open half) · BR-NOT-005 · BR-PAY-016/017/021/036 ·
#           BR-TEN-043 · CLAUDE.md rules 1, 2, 4, 5
# Questions: OQ-366 (who the restarted ladder chases — OPEN, and no row names a
#           party) · ⛔ ONE MORE IS OWED AND UNMINTED: the six S90 segments are
#           not mutually exclusive and no rule ranks them.
# Journeys: J08 step 2b (the unresolved SUBJECT, asserted as unresolved)
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.7 (S89) ·
#           §5.8 (S90)
# ───────────────────────────────────────────────────────
"""W7 tasks 7.4 + 7.11 — the two worklist selectors, S89 and S90.

**THE TWO CASES THIS FILE EXISTS FOR** are the two places a screen could tell a
customer something untrue:

  1. `test_trf_money_never_fabricates_a_figure` — an account holding $150.00
     whose BR-CUS-057 interest cannot be read gets a MONEY line with **no
     figure**, not `$0.00` and not `$150.00`. The writer lane measured what the
     tempting zero actually serves: `'150.00'` where `$153.50` is held, keeping
     $3.50 of the customer's money.
  2. `test_dsc_last_notice_never_claims_a_delivery` — `LAST NOTICE` is *"drawn
     against a capability that does not exist"* (B18 §5.8.2's own warning) and
     the cell renders the absence. A fabricated `emailed` is what a utility
     shows a regulator when a customer says they were never told.

⚠ **THREE ASSERTIONS HERE ARE DELIBERATELY NEGATIVE AND MUST STAY THAT WAY.**

  1. `test_dsc_only_the_all_segment_is_served` asserts that five of six drawn
     segments REFUSE. They refuse because `On hold` is computed from the
     protections while the other four are the stored case state, the two axes
     are independent, and no rule ranks them. If a later lane makes this test
     green on `at_notice`, it must be because the PO ruled a precedence — not
     because the refusal was inconvenient.
  2. `test_dsc_no_row_names_the_chased_party` asserts the product names NO
     party on a post-closure collections row (OQ-366, J08 step 2b: *"a green
     assertion naming either party is a FAILURE"*).
  3. `test_dsc_chips_are_a_list_and_no_precedence_is_invented` asserts that a
     row satisfying two chips serves BOTH. Dropping one would hide a protection
     from the screen that authorises a cut.

**RED PROVED FIRST for every case** (hard-won law 7). Each guard was broken
under a mutation, run, the failure quoted in the lane report, and the mutation
reverted — no `# BREAK:` marker survives in this file (DEF-666).
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import disconnect_due
from apps.customers import disconnect_reads
from apps.customers import disconnects
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.customers import transfer_reads, transfers
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 25)

# ── ❄️ WE-7 / GT-23, frozen: $150.00 held at the tenant's rate = $3.50 ──────
DEPOSIT_HELD = D("150.00")
DEPOSIT_INTEREST = D("3.50")
CARRIED = D("153.50")  # B18 §5.7.6 row 1: `deposit carried $153.50`
ARREAR = D("542.10")  # B18 §5.7.6 row 4: `arrear follows $542.10`, Jenna Park

# ── B18 §5.8.6's own figures ────────────────────────────────────────────────
BAKERY_OWED = D("2410.00")  # A-11812 · Bramble Bakery · TIER 2 · 10-DAY
OKAFOR_OWED = D("948.20")  # A-11902 · Okafor, Emmanuel · HELD · MEDICAL
RIDGE_SHORTFALL = D("175.20")  # A-11024 · Ridge Coffee Co., BR-CUS-082's worked case


# ════════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING — copied from `tests/test_w7_disconnects.py`, which is the
# style this pair of surfaces already has. Real rows through real services
# (DEF-658), except the two MONEY columns every service door deliberately
# refuses (`services.REFUSED_FIELDS`: BR-CUS-023 the deposit, BR-CUS-015 the
# balance) — a fixture that could set them through a door would mean the
# product had one.
# ════════════════════════════════════════════════════════════════════════════
def _plan(tenant, service_code="electric"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, name="W7 Worklists", defaults={"code": "w7-worklists", "status": "published"}
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"W7 Worklists — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _unit(actor, tenant, *, label="Unit A"):
    premises = make_premises(actor, services_available=["electric", "water"])
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    metering_services.ensure_service_point(unit["id"], "electric")
    return unit


def _account(actor, tenant, *, label="Unit A", name="Rita Sandoval"):
    unit = _unit(actor, tenant, label=label)
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2026-07-01",
            "contact": {"full_name": name},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )


def _mover(actor, tenant, *, deposit=D("0"), arrear=D("0"), name="Park, Jenna", label="Unit A"):
    """B18 §5.7.6's shape — the account a transfer starts FROM, with a customer
    entity linked (BR-CUS-054), because a transfer is *the same customer* at a
    new address and the customer is READ, never matched."""
    account = _account(actor, tenant, label=label, name=name)
    customers_models.Account.objects.filter(id=account["id"]).update(
        deposit_on_file=deposit, balance=arrear
    )
    customer = customers_services.link_customer(account_id=account["id"], display_name=name)
    return customer, customers_models.Account.objects.get(id=account["id"])


def _wire_interest(monkeypatch, amount=DEPOSIT_INTEREST):
    """Publish BR-CUS-057's read — the ONE place a seam is patched.

    Patched on purpose and named as such: it proves the gap is a WIRING fact and
    not a permanent refusal, the same device `tests/test_w7_transfers.py` uses.
    """
    real_resolve = transfers.seams.resolve

    def _resolve(module, attribute, kind="services"):
        if (module, attribute) == ("customers", "deposit_interest_accrued"):
            return lambda _account_id: amount
        return real_resolve(module, attribute, kind=kind)

    monkeypatch.setattr(transfers.seams, "resolve", _resolve)


class _EveryAccount(dict):
    """A `positions` map that answers the same figure for any account id.

    The tests stand up the LEDGER BOUNDARY, not a fake of it: `seams.ArPositions`
    is the real class, so `available`, `amount_for` and DEF-127's *"an unwired
    seam reports, it never answers 0"* distinction are the product's own.
    """

    def __init__(self, amount):
        super().__init__()
        self._amount = amount

    def get(self, _key, _default=None):
        return self._amount


def _owes(monkeypatch, amount, *, available=True):
    """`available=False` is the UNREADABLE case and is a first-class fixture."""
    positions = (
        disconnects.seams.ArPositions(
            positions=None, unavailable=disconnects.seams.AR_POSITIONS_UNWIRED
        )
        if not available
        else disconnects.seams.ArPositions(positions=_EveryAccount(amount), currency="USD")
    )
    monkeypatch.setattr(disconnects.seams, "ar_positions", lambda *_a, **_k: positions)
    monkeypatch.setattr(disconnect_reads.seams, "ar_positions", lambda *_a, **_k: positions)


def _at_tier(actor, account_id, tier):
    """Walk the ladder to `tier` through the real `advance()` — never by UPDATE.

    A tier set with an UPDATE would prove that a column can hold a string.
    """
    reached = None
    while reached != tier:
        reached = disconnects.advance(actor, account_id, as_of=TODAY)["tier"]
    return reached


def _through_step_4(actor, transfer, target_unit, *, out="2026-08-28", into="2026-09-03"):
    transfers.set_target_unit(actor, transfer["id"], {"to_unit_id": str(target_unit["id"])})
    transfers.set_dates(actor, transfer["id"], {"out_date": out, "in_date": into})
    return transfers.elect_money(actor, transfer["id"], {})


def _row_for(payload, account_no):
    return next(row for row in payload["rows"] if row["account_no"] == account_no)


def _trf_row(payload, from_account_no):
    return next(row for row in payload["rows"] if row["from_account_no"] == from_account_no)


def _data_only(value):
    """A row with every stated absence's `detail` prose stripped out.

    An absence explains ITSELF — `chase_subject_unresolved` quotes BR-CUS-097
    saying *"a sub-account's residue moves to its MASTER"* in order to say that
    neither ruling names a chased party. So a naive substring search over the
    whole row finds "master" inside the very sentence that refuses to name one.
    This keeps the assertion on the DATA, which is where a party would actually
    be named.
    """
    if isinstance(value, dict):
        return {key: _data_only(item) for key, item in value.items() if key != "detail"}
    if isinstance(value, (list, tuple)):
        return [_data_only(item) for item in value]
    return value


# ════════════════════════════════════════════════════════════════════════════
# 7.4 · S89 — THE TWO-LINE `FROM ACCOUNT` CELL (B18 §5.7.2, TC-TRF-2)
# ════════════════════════════════════════════════════════════════════════════

def _prove_tier_3_service(actor, account_id, *, served_on=date(2026, 8, 22)):
    """⚠ **BR-CUS-100 (PO 2026-08-25) — a tier-3 cut needs a RECORDED PROOF OF
    SERVICE before it can be scheduled.**

    Added to these fixtures on 2026-08-25, when the guard landed. Before it,
    every one of these cases scheduled a cut on three in-app notices with
    nothing posted — which is `DEF-692` exactly: the lawfulness of a tier-3 cut
    rests on certified mail, and the product had no way to record that it
    happened.

    The proof is a record a PERSON enters, not a send the product claims: the
    channel used, the article number, and the date it was served. The article
    number here is a real USPS certified-mail format, because a fixture that
    types `"ref"` teaches the next reader that anything passes.
    """
    notice = disconnects.latest_notice_at_tier(
        disconnects.open_case_for(account_id), disconnects.TIER_3
    )
    return disconnects.record_proof_of_service(
        actor,
        notice.id,
        channel=disconnects.SERVE_CERTIFIED_MAIL,
        reference="7020 1810 0001 2345 6789",
        served_on=served_on,
    )

def test_trf_the_from_cell_is_two_lines_and_reads_a_dash_before_the_new_number(brazos, marcus):
    """B18 §5.7.2, verbatim: *"**`FROM ACCOUNT`** is **two lines**: `A-10650`
    above, `→ A-11940` beneath … The new account number appears **as soon as it
    exists** and reads `→ —` before that"*, and TC-TRF-2: *"`→ —` in the FROM
    ACCOUNT cell, not a blank"*.

    A blank second line and an absent one are indistinguishable once rendered,
    which is why the dash is produced on the server.
    """
    with tenant_ctx(brazos):
        _customer, account = _mover(marcus, brazos, label="901 Hillside Ave")
        transfers.start_transfer(marcus, {"from_account_id": str(account.id)})

        row = transfer_reads.list_transfers()["rows"][0]
        assert row["from_cell"] == [account.account_no, "→ —"]
        assert len(row["from_cell"]) == 2
        assert row["to_account_no"] is None
        assert row["step_cell"] == "1 of 5"


def test_trf_the_second_line_carries_the_new_number_as_soon_as_it_exists(brazos, marcus):
    """The other half of §5.7.2: *"as soon as it exists"*. After the one commit
    (TC-TRF-6) the cell reads `A-10650` / `→ A-11940`."""
    with tenant_ctx(brazos):
        _customer, account = _mover(marcus, brazos, label="901 Hillside Ave")
        target = _unit(marcus, brazos, label="26 Meadowbank Rise")
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        _through_step_4(marcus, started, target)
        done = transfers.commit_transfer(marcus, started["id"])

        new = customers_models.Account.objects.get(id=done["to_account_id"])
        row = _trf_row(transfer_reads.list_transfers(), account.account_no)
        assert row["from_cell"] == [account.account_no, f"→ {new.account_no}"]
        assert row["state"] == "done"
        assert row["step_cell"] == "5 of 5"


# ════════════════════════════════════════════════════════════════════════════
# 7.4 · S89 — THE STACKED `MONEY` SENTENCES, AND THE ABSENCES
# ════════════════════════════════════════════════════════════════════════════
def test_trf_money_stacks_two_sentences_with_the_arrear_in_amber(brazos, marcus, monkeypatch):
    """B18 §5.7.2, verbatim: *"**`MONEY`** stacks up to two sentences: `deposit
    carried $153.50` and, beneath, `arrear follows $542.10` in **amber**"*.

    ❄️ WE-7 / GT-23's frozen pair — $150.00 principal + $3.50 interest =
    **$153.50** — and §5.7.6's `arrear follows $542.10` on Jenna Park. Nothing
    here invents a figure.
    """
    with tenant_ctx(brazos):
        _wire_interest(monkeypatch)
        _customer, account = _mover(
            marcus, brazos, deposit=DEPOSIT_HELD, arrear=ARREAR, label="901 Hillside Ave"
        )
        transfers.start_transfer(marcus, {"from_account_id": str(account.id)})

        money = transfer_reads.list_transfers()["rows"][0]["money"]
        assert money["sentences"] == ["deposit carried $153.50", "arrear follows $542.10"]
        assert [line["kind"] for line in money["lines"]] == ["deposit_carried", "arrear_follows"]
        assert [line["tone"] for line in money["lines"]] == ["ink", "amber"]
        # rule 2: STORED to four decimals, DISPLAYED at two, never a float.
        assert money["lines"][0]["amount"] == {"stored": "153.5000", "display": "153.50"}
        assert money["lines"][1]["amount"] == {"stored": "542.1000", "display": "542.10"}
        assert money["currency"] == account.currency


def test_trf_money_never_fabricates_a_figure(brazos, marcus):
    """⚠ **THE CASE THIS FILE EXISTS FOR (one of two).**

    BR-CUS-057's deposit-interest accrual is CONFIRMED and NOT BUILT, so the
    carried figure cannot be read. The cell must say *"there is a deposit and we
    cannot state it"*, which is neither a missing line (indistinguishable from
    no deposit) nor a number.

    The writer lane measured what the tempting `ZERO` actually serves:
    **`'150.00'`** where **`$153.50`** is held — *"it serves the principal AS the
    carried amount and keeps $3.50 of the customer's money."*
    """
    with tenant_ctx(brazos):
        _customer, account = _mover(
            marcus, brazos, deposit=DEPOSIT_HELD, arrear=ARREAR, label="901 Hillside Ave"
        )
        transfers.start_transfer(marcus, {"from_account_id": str(account.id)})

        money = transfer_reads.list_transfers()["rows"][0]["money"]
        deposit_line = next(line for line in money["lines"] if line["kind"] == "deposit_carried")
        # The LINE is present — the deposit exists — and carries NO figure.
        assert deposit_line["text"] is None
        assert deposit_line["amount"] == {"stored": None, "display": None}
        assert deposit_line["unavailable"]["code"] == transfers.GAP_DEPOSIT_INTEREST
        # …and neither a zero nor the principal appears in anything a screen
        # RENDERS as a figure. The absence's own `detail` explains the trap in
        # those very numbers ("reading the interest as 0.00 would state $150.00
        # where $153.50 is held"), so the check is scoped to the figures and not
        # to the prose that warns about them.
        figures = repr([(line["text"], line["amount"]) for line in money["lines"]])
        figures += repr(money["sentences"])
        assert "0.00" not in figures
        assert "150.00" not in figures
        # `sentences` is SHORTER than `lines` here, which is exactly why both
        # exist: a screen reading only the sentences would show one line.
        assert money["sentences"] == ["arrear follows $542.10"]
        assert len(money["lines"]) == 2


def test_trf_money_states_the_four_absences_and_moves_nothing(brazos, marcus, monkeypatch):
    """⚠ **NO MONEY MOVES IN A TRANSFER.** `transfers.money_statement` serves
    figures plus stated absences and this cell carries them verbatim:

      · `transfer_money_rule_does_not_exist` — always; a transfer is a THIRD
        path and BR-CUS-025/081 and B18 §5.7.6 describe different products.
      · `deposit_carry_has_no_transfer_path` — BR-CUS-024's mechanics are
        PROPOSED and BR-CUS-025 says closure is the only time it moves.
      · `arrears_follow_has_no_posting_path` — hard rule 5.
      · `balance_is_the_cached_ar_figure` — BR-CUS-015.

    And the deposit is provably neither refunded nor re-collected, which is the
    half of TC-TRF-3 that IS signed.
    """
    with tenant_ctx(brazos):
        _wire_interest(monkeypatch)
        _customer, account = _mover(
            marcus, brazos, deposit=DEPOSIT_HELD, arrear=ARREAR, label="901 Hillside Ave"
        )
        target = _unit(marcus, brazos, label="26 Meadowbank Rise")
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        _through_step_4(marcus, started, target)
        transfers.commit_transfer(marcus, started["id"])

        money = _trf_row(transfer_reads.list_transfers(), account.account_no)["money"]
        codes = {row["code"] for row in money["unavailable"]}
        assert transfers.GAP_TRANSFER_MONEY_UNRULED in codes
        assert transfers.GAP_DEPOSIT_NO_TRANSFER_PATH in codes
        assert transfers.GAP_ARREARS_NO_POSTING_PATH in codes
        assert transfers.GAP_BALANCE_IS_A_CACHE in codes
        assert set(money["gaps"]) == codes

        # Nothing moved: the deposit was not refunded and not re-collected.
        after = customers_models.Account.objects.get(id=account.id)
        assert after.deposit_on_file == DEPOSIT_HELD
        assert after.balance == ARREAR


# ════════════════════════════════════════════════════════════════════════════
# 7.4 · S89 — THE EXCLUSION CONTRACT (§5.7.3, TC-TRF-1)
# ════════════════════════════════════════════════════════════════════════════
def test_trf_the_list_publishes_the_exclusion_contract_and_never_re_implements_it(brazos, marcus):
    """B18 §5.7.3, verbatim: *"A transfer appears only here. Its two halves are
    deliberately kept out of Move-ins and Move-outs — the same job listed three
    times would be counted three times."*

    This list is the *"only here"* half, so what it publishes is the COMPLEMENT:
    the set a Move-ins/Move-outs list must subtract. It is
    `transfers.transfer_half_account_ids()` CALLED — the contract, not a copy —
    and every account id on every row is inside it. If those two ever disagree,
    one job is about to be counted twice.

    ⚠ **THE OPEN JOB IS THE CASE THAT MATTERS, AND THIS TEST DID NOT HAVE IT
    UNTIL A MUTATION WALKED THROUGH THE GAP.** Re-scoping the published set to
    `include_open=False` — the shape of re-implementing the contract instead of
    calling it — left a committed-only fixture completely green, because a
    committed job is in both sets. The contract's own docstring says why the
    open job counts: *"a transfer at step 3 has ALREADY taken its outgoing
    account out of the Move-outs count … and §5.7.6's fixture proves it, since
    `A-11455 · Park, Jenna` sits at `3 of 5` and is not in the Move-outs five."*
    So the fixture below carries BOTH a committed job and a job stopped at step
    2, and asserts the open one's account is published.
    """
    with tenant_ctx(brazos):
        _customer, account = _mover(marcus, brazos, label="901 Hillside Ave")
        target = _unit(marcus, brazos, label="26 Meadowbank Rise")
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        _through_step_4(marcus, started, target)
        done = transfers.commit_transfer(marcus, started["id"])

        # B18 §5.7.6's `Park, Jenna` shape — an OPEN job, mid-wizard.
        _c2, open_account = _mover(marcus, brazos, name="Osei, Grace", label="12 Harbour View")
        open_target = _unit(marcus, brazos, label="500 Main · 210")
        open_job = transfers.start_transfer(marcus, {"from_account_id": str(open_account.id)})
        transfers.set_target_unit(marcus, open_job["id"], {"to_unit_id": str(open_target["id"])})

        payload = transfer_reads.list_transfers()
        published = set(payload["exclusion"]["half_account_ids"])
        assert published == transfers.transfer_half_account_ids()
        assert payload["exclusion"]["contract"] == list(transfers.EXCLUSION_CONTRACT)
        for row in payload["rows"]:
            assert row["from_account_id"] in published
            if row["to_account_id"] is not None:
                assert row["to_account_id"] in published
        # TC-TRF-1's predicate, on the real committed job…
        assert transfers.is_transfer_half(account.id) is True
        assert transfers.is_transfer_half(done["to_account_id"]) is True
        # …and on the OPEN one, which is the half a re-scoped copy loses.
        assert str(open_account.id) in published
        assert transfers.is_transfer_half(open_account.id) is True


# ════════════════════════════════════════════════════════════════════════════
# 7.4 · S89 — THE FIVE KPI TILES (§5.7.1) AND THE SEARCH (§5.7.2)
# ════════════════════════════════════════════════════════════════════════════
def test_trf_the_kpi_tiles_count_elections_not_figures(brazos, marcus, monkeypatch):
    """B18 §5.7.1's `DEPOSITS CARRYING` and `ARREARS FOLLOWING`.

    They count the clerk's step-4 ELECTION, which is what makes them countable
    without inventing a figure to count. On the fixture: one open job at step 4
    with $150.00 held and $542.10 owing reads `OPEN 1 · DEPOSITS CARRYING 1 ·
    ARREARS FOLLOWING 1`, and `MOVING THIS WEEK 1` because its out date (Aug 28)
    is within 7 days of Aug 25. The second job, never elected, is counted by
    `OPEN` and by neither election tile.
    """
    with tenant_ctx(brazos):
        _wire_interest(monkeypatch)
        _customer, account = _mover(
            marcus, brazos, deposit=DEPOSIT_HELD, arrear=ARREAR, label="901 Hillside Ave"
        )
        target = _unit(marcus, brazos, label="26 Meadowbank Rise")
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        _through_step_4(marcus, started, target, out="2026-08-28", into="2026-09-03")

        _c2, other = _mover(marcus, brazos, name="Osei, Grace", label="12 Harbour View")
        transfers.start_transfer(marcus, {"from_account_id": str(other.id)})

        kpis = transfer_reads.kpi_strip(as_of=TODAY)
        assert kpis["open"] == 2
        assert kpis["moving_this_week"] == 1
        assert kpis["deposits_carrying"] == 1
        assert kpis["arrears_following"] == 1
        assert kpis["completed_this_month"] == 0
        # No rule states which clock a KPI window uses; the basis is DATA.
        assert kpis["period_basis"] == "tenant_month_to_date"


def test_trf_search_finds_either_address_and_states_the_request_leg_absence(brazos, marcus):
    """B18 §5.7.2: *"**Search:** "Customer, account #, either address, or
    request #…" — **"either address"** is the whole point of the tab"*.

    The TARGET address finds the job, which is the half a Move-outs list could
    never answer. ⛔ `request #` is served as an ABSENCE: §5.7.6 links Park to
    `SR-26-0047` and the `transfers` table has no service-request column.
    """
    with tenant_ctx(brazos):
        _customer, account = _mover(marcus, brazos, label="901 Hillside Ave")
        target = _unit(marcus, brazos, label="26 Meadowbank Rise")
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        transfers.set_target_unit(marcus, started["id"], {"to_unit_id": str(target["id"])})

        by_target = transfer_reads.list_transfers(q="Meadowbank")
        assert by_target["total"] == 1
        by_origin = transfer_reads.list_transfers(q="Hillside")
        assert by_origin["total"] == 1
        by_customer = transfer_reads.list_transfers(q="Park")
        assert by_customer["total"] == 1
        by_account = transfer_reads.list_transfers(q=account.account_no)
        assert by_account["total"] == 1
        assert transfer_reads.list_transfers(q="Nothing At All")["total"] == 0

        # ⚠ WAS `== ["transfer_has_no_request_link"]` UNTIL 2026-08-25. The lane
        # served the fourth drawn search leg as a STATED ABSENCE so a clerk
        # typing a request number met a sentence rather than silence, and
        # reported that the PO had to choose. **The PO ruled the leg AWAY**
        # (BR-CUS-099, DEF-688): "Drop the leg — remove 'or request #' from the
        # box". So there is nothing left to state — the box does not offer it,
        # and an absence for a thing nobody is offered would be noise.
        assert by_target["search"]["unavailable"] == []
        assert by_target["search"]["legs"] == ("customer", "account_no", "either_address")
        # The hint must not re-advertise it. This is the assertion that would
        # catch a later lane copying §5.7.2's drawn placeholder back in.
        assert "request" not in by_target["search"]["hint"].lower()


def test_trf_the_list_paginates(brazos, marcus):
    """11b G5 — pagination is mandatory on every list."""
    with tenant_ctx(brazos):
        for n in range(3):
            _c, account = _mover(marcus, brazos, name=f"Mover {n}", label=f"{n} Marten Row")
            transfers.start_transfer(marcus, {"from_account_id": str(account.id)})

        first = transfer_reads.list_transfers(page=1, per=2)
        assert first["total"] == 3 and first["pages"] == 2 and len(first["rows"]) == 2
        second = transfer_reads.list_transfers(page=2, per=2)
        assert len(second["rows"]) == 1
        seen = {row["id"] for row in first["rows"]} | {row["id"] for row in second["rows"]}
        assert len(seen) == 3, "a row appeared on two pages — the order is not stable"


def test_trf_the_columns_and_steps_are_b18s_own(brazos, marcus):
    """§5.7.2's eight columns and §5.7.4's five steps, served as DATA so the
    payload and the screen cannot disagree about which cells exist.

    ⚠ **NINE SINCE 2026-08-27 — CR-039 wave D task 15, and this test going RED
    is it working.** The design's eight are unchanged and in order; `reference`
    LEADS them, because the CR's finding 5 is *"A clerk cannot quote a
    reference"* and a number a clerk cannot SEE is not a number. The divergence
    from the drawing is stamped in `transfer_reads.COLUMNS` and on the column
    itself in `TransfersTab.tsx`.

    **This is the THIRD hand-pinned place that had to move for one change** —
    `transfer_reads.COLUMNS`, `TransfersTab.tsx`'s config, and here — which is
    DEF-807's lesson arriving again on a different list. It is left as a literal
    rather than derived from `COLUMNS`: a literal restates the tuple instead of
    checking it, but that IS the check when the claim is *"these are B18's own
    columns and this one addition"*.
    """
    with tenant_ctx(brazos):
        payload = transfer_reads.list_transfers()
        assert payload["columns"] == [
            "reference",  # CR-039 W-D 15 — not drawn by B18; see the docstring
            "from_account",
            "customer",
            "from_to",
            "out_date",
            "in_date",
            "step",
            "money",
            "state",
        ]
        assert len(payload["steps"]) == transfers.STEP_COUNT == 5
        # ⚠ NOT B18 §5.7.2's drawn placeholder any more — BR-CUS-099 removed the
        # request-number leg, so the drawing is stale here and the RULE wins.
        assert payload["search"]["hint"] == "Customer, account #, or either address…"


# ════════════════════════════════════════════════════════════════════════════
# 7.11 · S90 — SIX TIER CHIPS (B18 §5.8.2)
# ════════════════════════════════════════════════════════════════════════════
def test_dsc_there_are_exactly_six_tier_chips_and_the_dash_is_not_one():
    """B18 §5.8.2, verbatim: *"**`TIER`** is a bordered chip: `TIER 1 ·
    REMINDER` · `TIER 2 · 10-DAY` · `TIER 3 · 48-HOUR` (accent) · `HELD ·
    MEDICAL` · `HELD · PAYMENT PLAN` · `HELD · WEATHER MORATORIUM` (grey) ·
    `—`"*.

    SIX chips and a DASH. The dash is an ABSENCE with two causes — nothing sent
    yet, or payments' `second_5_day` rung, which B18 draws no chip for — and it
    is not a seventh chip.
    """
    assert len(disconnect_reads.TIER_CHIPS) == 6
    assert [disconnect_reads.CHIP_LABELS[chip] for chip in disconnect_reads.TIER_CHIPS] == [
        "TIER 1 · REMINDER",
        "TIER 2 · 10-DAY",
        "TIER 3 · 48-HOUR",
        "HELD · MEDICAL",
        "HELD · PAYMENT PLAN",
        "HELD · WEATHER MORATORIUM",
    ]
    # §5.8.2: TIER 3 in the accent, the three HELD chips in grey.
    assert disconnect_reads.CHIP_TONES[disconnects.TIER_3] == "accent"
    assert all(
        disconnect_reads.CHIP_TONES[chip] == "grey"
        for chip in disconnect_reads.CHIP_FOR_PROTECTION.values()
    )
    # The three ladder chips are `disconnects`' own spelling, not a second one.
    assert disconnect_reads.TIER_CHIPS[:3] == disconnects.LADDER_TIERS
    # One chip per protection B18 §5.8.3 names — three, not four.
    assert set(disconnect_reads.CHIP_FOR_PROTECTION) == set(disconnects.PROTECTIONS)


def test_dsc_a_ladder_chip_and_a_held_chip_render_from_real_rows(brazos, marcus, monkeypatch):
    """§5.8.6's own shapes: `A-11812 · Bramble Bakery` at `TIER 2 · 10-DAY`
    owing $2,410.00, and `A-11902 · Okafor` at `HELD · MEDICAL` owing $948.20
    with `—` for CUT DATE and `—` for LAST NOTICE."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, BAKERY_OWED)
        bakery = _account(marcus, brazos, label="Bramble Bakery", name="Bramble Bakery")
        _at_tier(marcus, bakery["id"], disconnects.TIER_2)

        okafor = _account(marcus, brazos, label="77 Okafor Way", name="Okafor, Emmanuel")
        disconnects.record_protection(
            marcus,
            okafor["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 8, 1),
            expires_on=date(2026, 12, 31),
        )

        payload = disconnect_reads.list_disconnects(as_of=TODAY)
        assert payload["total"] == 2

        bakery_row = _row_for(payload, bakery["account_no"])
        assert [chip["code"] for chip in bakery_row["tier"]["chips"]] == [disconnects.TIER_2]
        assert bakery_row["tier"]["chips"][0]["label"] == "TIER 2 · 10-DAY"
        assert bakery_row["tier"]["ambiguous"] is False
        assert bakery_row["state"]["stored"] == disconnects.STATE_NOTICE_SENT
        assert bakery_row["state"]["held_by"] == []

        okafor_row = _row_for(payload, okafor["account_no"])
        assert [chip["code"] for chip in okafor_row["tier"]["chips"]] == [
            disconnect_reads.CHIP_HELD_MEDICAL
        ]
        # `A-11902` never entered the ladder: no case, so `—` for CUT DATE.
        assert okafor_row["case"] is None
        assert okafor_row["cut_date"] is None
        assert okafor_row["state"]["held_by"] == [disconnects.PROTECTION_MEDICAL]
        assert okafor_row["state"]["one_cell_is_unresolved"] is False


def test_dsc_chips_are_a_list_and_no_precedence_is_invented(brazos, marcus, monkeypatch):
    """⚠ **A DELIBERATELY NEGATIVE ASSERTION — READ THE MODULE DOCSTRING.**

    B18 draws ONE chip per row and its §5.8.6 fixture never needs two, because
    every HELD row there has `—` for LAST NOTICE. **The product can produce
    two**: §5.8.3's ladder diagram draws `T1 · T2 · T3 -.-> HOLD`, so a customer
    at TIER 2 who files a medical certificate has a tier reached AND a
    protection in force. Which one wins in a single cell is stated by no rule.

    So every applicable chip is served, in the drawn order, and the row says it
    is ambiguous. Dropping one would hide a protection from the screen that
    authorises a cut; picking one would be inventing a precedence.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, BAKERY_OWED)
        bakery = _account(marcus, brazos, label="Bramble Bakery", name="Bramble Bakery")
        _at_tier(marcus, bakery["id"], disconnects.TIER_2)
        disconnects.record_protection(
            marcus,
            bakery["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 8, 1),
            expires_on=date(2026, 12, 31),
        )

        row = _row_for(disconnect_reads.list_disconnects(as_of=TODAY), bakery["account_no"])
        assert [chip["code"] for chip in row["tier"]["chips"]] == [
            disconnects.TIER_2,
            disconnect_reads.CHIP_HELD_MEDICAL,
        ]
        assert row["tier"]["ambiguous"] is True
        assert "more_than_one_chip_applies" in {
            entry["code"] for entry in row["tier"]["unavailable"]
        }
        # Both axes are served and neither is a silent winner.
        assert row["state"]["stored"] == disconnects.STATE_NOTICE_SENT
        assert row["state"]["held_by"] == [disconnects.PROTECTION_MEDICAL]
        assert row["state"]["one_cell_is_unresolved"] is True
        # The ladder is FROZEN by the protection — `halt_reason`'s own answer.
        assert row["ladder"]["runs"] is False
        assert row["ladder"]["halt_code"] == disconnects.HALT_PROTECTED


def test_dsc_a_row_with_no_tier_renders_the_dash_as_an_absence(brazos, marcus, monkeypatch):
    """§5.8.6's `A-11507 · Greaves, Tom` — owes **$0.00**, tier `—`, state
    `Reconnecting`: *"a paid account still on the tab because a visit is due"*
    (TC-DSC-8). The cell renders an ABSENCE with its reason, never a blank."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("612.75"))
        greaves = _account(marcus, brazos, label="12 Greaves Row", name="Greaves, Tom")
        opened = disconnects.open_case(marcus, greaves["id"], as_of=TODAY)
        case = disconnects.DisconnectCase.objects.get(id=opened["case_id"])
        case.state = disconnects.STATE_RECONNECTING
        case.save(update_fields=["state", "updated_at"])

        _owes(monkeypatch, D("0.00"))
        row = _row_for(disconnect_reads.list_disconnects(as_of=TODAY), greaves["account_no"])
        assert row["tier"]["chips"] == []
        assert [entry["code"] for entry in row["tier"]["unavailable"]] == ["no_tier_reached"]
        assert row["owed"]["display"] == "0.00"
        assert row["state"]["stored"] == disconnects.STATE_RECONNECTING


# ════════════════════════════════════════════════════════════════════════════
# 7.11 · S90 — SIX SEGMENTS, AND THE PRECEDENCE NOBODY RULED
# ════════════════════════════════════════════════════════════════════════════
def test_dsc_there_are_exactly_six_segments_in_b18s_drawn_order():
    """B18 §5.8.2, verbatim: *"**Segments:** `All` · `At notice` · `Due to cut`
    · `On hold` · `Cut` · `Reconnecting`"*."""
    assert len(disconnect_reads.SEGMENTS) == 6
    assert [disconnect_reads.SEGMENT_LABELS[code] for code in disconnect_reads.SEGMENTS] == [
        "All",
        "At notice",
        "Due to cut",
        "On hold",
        "Cut",
        "Reconnecting",
    ]


def test_dsc_only_the_all_segment_is_served_and_an_open_question_is_owed(brazos, marcus):
    """⚠ **A DELIBERATELY NEGATIVE ASSERTION — FIVE OF SIX SEGMENTS REFUSE.**

    Measured 2026-08-25: `disconnects.STATE_ON_HOLD` is declared, sits in the
    migration's CHECK vocabulary and **is assigned nowhere in this repository**,
    and `record_protection()` does not touch `case.state`. So `On hold` is
    COMPUTED from the protections while the other four are the stored
    `disconnect_cases.state`, the two axes are independent, and a case at
    `notice_sent` whose account files a medical certificate satisfies `At
    notice` AND `On hold`. §5.8.6's fixture never shows the collision, so the
    drawing cannot be read for an answer.

    ✅ **THE QUESTION IS NOW `OQ-374`, MINTED BY THE MERGING SESSION ON THE DAY
    THIS LANE REPORTED IT OWED.** The lane could not mint it — `12-governance/`
    is outside a lane's write scope, and inventing an OQ-### from inside code is
    exactly what G8 clause B exists to catch — so it refused in prose and
    reported. This assertion was rewritten when the id landed, and the rewrite
    is the point: a test that pinned *"a question is owed"* had to go RED the
    moment the question stopped being owed, which is how anyone can tell the
    registry and the code agree.

    **The refusal message still carries no id**, deliberately. It is read by a
    utility user, and `OQ-374` means nothing to them; the id lives on the
    constant, where a developer looks.

    If a later lane makes this test green on `at_notice`, it must be because the
    PO ruled a precedence — not because the refusal was inconvenient.
    """
    with tenant_ctx(brazos):
        # The one that IS served.
        payload = disconnect_reads.list_disconnects(segment="all", as_of=TODAY)
        assert payload["segment"] == "all"
        supported = {row["code"]: row["supported"] for row in payload["segments"]}
        assert supported == {
            "all": True,
            "at_notice": False,
            "due_to_cut": False,
            "on_hold": False,
            "cut": False,
            "reconnecting": False,
        }

        for code in disconnect_reads.SEGMENTS[1:]:
            with pytest.raises(NotImplementedError) as refusal:
                disconnect_reads.list_disconnects(segment=code, as_of=TODAY)
            message = str(refusal.value)
            assert "segment" in message.lower()
            assert "OPEN QUESTION IS OWED" in message
            # ⚠ No invented OQ id, and no precedence stated either way.
            assert "OQ-3" not in message

        # An unknown value refuses too, and names the six.
        with pytest.raises(NotImplementedError):
            disconnect_reads.list_disconnects(segment="nonsense", as_of=TODAY)

        # ⚠ WAS `"OQ-OWED-UNMINTED"` UNTIL 2026-08-25. The lane reported the
        # question owed; the merging session minted OQ-374 the same day and this
        # assertion followed. The registry row and this constant must name the
        # same question or one of them is lying about what is undecided.
        assert disconnect_reads.SEGMENT_PRECEDENCE_UNRULED["tracks"] == "OQ-374"


# ════════════════════════════════════════════════════════════════════════════
# 7.11 · S90 — `LAST NOTICE`, `OWED`, `CUT DATE`
# ════════════════════════════════════════════════════════════════════════════
def test_dsc_last_notice_never_claims_a_delivery(brazos, marcus, monkeypatch):
    """⚠ **THE CASE THIS FILE EXISTS FOR (two of two).** TC-DSC-6.

    B18 §5.8.2's own warning: *"**`LAST NOTICE` is a delivery claim the product
    cannot currently make.** There is **no email, SMS or print adapter in this
    release** … **This column is drawn against a capability that does not
    exist**, and a lane must render the absence rather than fabricate a delivery
    state."*

    The cell carries the two FACTS — which tier, and when it was issued — and
    `delivery_state` is `None` with the reason attached. Never `emailed`,
    `posted`, `certified sent` or `certified signed`.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, BAKERY_OWED)
        bakery = _account(marcus, brazos, label="Bramble Bakery", name="Bramble Bakery")
        _at_tier(marcus, bakery["id"], disconnects.TIER_2)

        row = _row_for(disconnect_reads.list_disconnects(as_of=TODAY), bakery["account_no"])
        cell = row["last_notice"]
        assert cell["tier"] == disconnects.TIER_2
        assert cell["issued_on"] == TODAY.isoformat()
        assert cell["delivery_state"] is None
        assert cell["unavailable"]["code"] == "delivery_adapter_absent"
        for claim in ("emailed", "posted", "certified sent", "certified signed"):
            assert cell.get("delivery_state") != claim
        # …and the stored row is NULL, which is where the guarantee lives.
        assert (
            disconnects.DisconnectNotice.objects.filter(delivery_state__isnull=False).count() == 0
        )


def test_dsc_owed_states_its_absence_and_never_fabricates_a_zero(brazos, marcus, monkeypatch):
    """DEF-127, in `selectors._balance_cells`' own words: a substituted `$0.00`
    *"looks exactly like a settled account"* — and on THIS tab it looks like an
    account nobody should be chasing.

    An unreadable ledger gives `display: None` with the seam's own reason, and
    the ladder does not run: hard-won law 3, where the unsafe option is chasing.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, OKAFOR_OWED)
        okafor = _account(marcus, brazos, label="77 Okafor Way", name="Okafor, Emmanuel")
        disconnects.open_case(marcus, okafor["id"], as_of=TODAY)

        readable = _row_for(disconnect_reads.list_disconnects(as_of=TODAY), okafor["account_no"])
        assert readable["owed"] == {
            "stored": "948.2000",
            "display": "948.20",
            "currency": "USD",
            "source": "ledger",
            "unavailable": None,
        }

        _owes(monkeypatch, None, available=False)
        unreadable = _row_for(disconnect_reads.list_disconnects(as_of=TODAY), okafor["account_no"])
        assert unreadable["owed"]["display"] is None
        assert unreadable["owed"]["stored"] is None
        assert unreadable["owed"]["unavailable"]
        assert unreadable["ladder"]["halt_code"] == disconnects.HALT_BALANCE_UNREADABLE


def test_dsc_cut_date_is_accented_only_within_seven_days(brazos, marcus, monkeypatch):
    """B18 §5.8.2: *"**`CUT DATE`** renders in the **accent** when it is this
    week `[shot: Aug 24, Aug 26]`"*, and §5.8.1's caption for the tile is
    *"within 7 days of today"*.

    Worked from `as_of = 2026-08-25`: **Aug 26** is inside the window and
    accented; **Sep 12** is outside and is not.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("1204.50"))
        soon = _account(marcus, brazos, label="26 Calloway Ave", name="Calloway, Brett")
        _at_tier(marcus, soon["id"], disconnects.TIER_3)
        _prove_tier_3_service(marcus, soon["id"])
        disconnects.schedule_cut(marcus, soon["id"], cut_on=date(2026, 8, 26), as_of=TODAY)

        later = _account(marcus, brazos, label="77 Industrial Way", name="Northwind Mfg.")
        _at_tier(marcus, later["id"], disconnects.TIER_3)
        _prove_tier_3_service(marcus, later["id"])
        disconnects.schedule_cut(marcus, later["id"], cut_on=date(2026, 9, 12), as_of=TODAY)

        payload = disconnect_reads.list_disconnects(as_of=TODAY)
        assert _row_for(payload, soon["account_no"])["cut_date_is_this_week"] is True
        assert _row_for(payload, later["account_no"])["cut_date_is_this_week"] is False
        assert payload["kpis"]["due_to_cut_this_week"] == 1


# ════════════════════════════════════════════════════════════════════════════
# 7.11 · S90 — THE LADDER STOPS ITSELF, ON THE LIST (TC-DSC-1)
# ════════════════════════════════════════════════════════════════════════════
def test_dsc_the_halt_reason_is_recomputed_on_every_read(brazos, marcus, monkeypatch):
    """B18 §5.8.3: *"the ladder stops automatically and the row leaves this
    list. Nothing here has to be cancelled by hand."*

    The customer reaches TIER 2 owing $2,410.00 and pays it. **No function is
    called on the case.** The very next read of this list says the ladder does
    not run — which is only true because `halt_reason` is recomputed per row and
    is NOT memoized across the page. A cached run outlives the debt, and that is
    the customer who paid on Friday and got a certified letter on Monday.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, BAKERY_OWED)
        bakery = _account(marcus, brazos, label="Bramble Bakery", name="Bramble Bakery")
        _at_tier(marcus, bakery["id"], disconnects.TIER_2)

        before = _row_for(disconnect_reads.list_disconnects(as_of=TODAY), bakery["account_no"])
        assert before["ladder"]["runs"] is True

        # The money posts. Nothing else happens — no cancel, no clerk, no job.
        _owes(monkeypatch, D("0.00"))

        after = _row_for(disconnect_reads.list_disconnects(as_of=TODAY), bakery["account_no"])
        assert after["ladder"]["runs"] is False
        assert after["ladder"]["halt_code"] == disconnects.HALT_NOTHING_OWED
        # The tier it reached is a FACT and is not erased, and nothing was
        # cancelled by hand.
        assert disconnects.open_case_for(bakery["id"]).stopped_reason is None
        assert [chip["code"] for chip in after["tier"]["chips"]] == [disconnects.TIER_2]
        # DEF-320 travels with every ladder answer: nothing advances on a date.
        assert after["ladder"]["scheduler"]["advances_on_a_schedule"] is False


# ════════════════════════════════════════════════════════════════════════════
# 7.11 · S90 — OQ-366: NO ROW NAMES A CHASED PARTY
# ════════════════════════════════════════════════════════════════════════════
def test_dsc_no_row_names_the_chased_party(brazos, marcus, monkeypatch):
    """⚠ **A DELIBERATELY NEGATIVE ASSERTION. OQ-366 IS OPEN.**

    `BR-CUS-082` (PO 2026-08-24) restarts the ladder at TIER 1 on a debt that
    survived closure; `BR-CUS-097` moves a sub-account's residue to its MASTER;
    **neither says whose door the letters go to.**
    `08-qa/01-e2e/journeys/J08-final-bill-settlement-five-paths.md` step **2b**:
    *"A GREEN ASSERTION HERE THAT NAMES EITHER PARTY IS A FAILURE, because it
    means somebody chose."*

    Worked on BR-CUS-082's own fixture — `A-11024 · Ridge Coffee Co.` closes
    owing **$328.70** against **$153.50**, so **$175.20** survives and is chased
    from TIER 1. The row carries the restart FACT and the unresolved SUBJECT
    side by side, and `subject` is `None`.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, RIDGE_SHORTFALL)
        ridge = _account(marcus, brazos, label="500 Main · 200", name="Ridge Coffee Co.")
        disconnects.restart_after_closure(
            marcus, ridge["id"], as_of=TODAY, shortfall=RIDGE_SHORTFALL, currency="USD"
        )

        row = _row_for(disconnect_reads.list_disconnects(as_of=TODAY), ridge["account_no"])
        assert row["subject"] is None
        assert row["chase_subject_unresolved"]["tracks"] == "OQ-366"
        # The restart fact: TIER 1, a COLLECTIONS sequence, no cut reachable.
        assert [chip["code"] for chip in row["tier"]["chips"]] == [disconnects.TIER_1]
        assert row["ladder"]["sequence"] == disconnects.SEQ_COLLECTIONS
        assert row["case"]["amount_owed_at_open"] == {"stored": "175.2000", "display": "175.20"}
        # Nothing anywhere in the row's DATA names a party. The absence blocks
        # QUOTE the two rulings to say that neither names one, so their prose
        # contains both words by necessity — the check is on the data.
        rendered = repr(_data_only(row)).lower()
        assert "master" not in rendered
        assert "departed" not in rendered
        assert "sub-account" not in rendered


# ════════════════════════════════════════════════════════════════════════════
# 7.11 · S90 — THE FIVE KPI TILES (§5.8.1), THE UNION, AND THE SEARCH
# ════════════════════════════════════════════════════════════════════════════
def test_dsc_the_kpi_tiles_overlap_by_design_and_the_union_hides_nothing(
    brazos, marcus, monkeypatch
):
    """B18 §5.8.1's five tiles, and §5.8.6's proof that they overlap.

    A case at TIER 3 with a cut scheduled for Aug 26 is counted by BOTH `AT
    NOTICE` (*"somewhere on the ladder"*) and `DUE TO CUT THIS WEEK`. An account
    with a medical certificate and no case at all is counted by `ON HOLD —
    PROTECTED` and appears on the list — §5.8.6's `A-11902` is exactly that row,
    and a list of cases alone would be missing three of the drawn nine.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("8240.00"))
        northwind = _account(marcus, brazos, label="77 Industrial Way", name="Northwind Mfg.")
        _at_tier(marcus, northwind["id"], disconnects.TIER_3)
        _prove_tier_3_service(marcus, northwind["id"])
        disconnects.schedule_cut(marcus, northwind["id"], cut_on=date(2026, 8, 26), as_of=TODAY)

        okafor = _account(marcus, brazos, label="77 Okafor Way", name="Okafor, Emmanuel")
        disconnects.record_protection(
            marcus,
            okafor["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 8, 1),
            expires_on=date(2026, 12, 31),
        )

        payload = disconnect_reads.list_disconnects(as_of=TODAY)
        kpis = payload["kpis"]
        assert kpis["at_notice"] == 1
        assert kpis["due_to_cut_this_week"] == 1  # the SAME row — tiles overlap
        assert kpis["on_hold_protected"] == 1
        assert kpis["cut_awaiting_payment"] == 0
        assert kpis["reconnections_due"] == 0
        # §5.8.1's `CUT, AWAITING PAYMENT` caption is withheld, and the absence
        # says why. ⚠ THE CODE STRING MOVED ON 2026-08-25 (DEF-716): it was
        # `cut_base_accrual_unverified` while nothing ruled whether a cut
        # account keeps accruing. BR-CUS-103 ruled it — base charges STOP at the
        # cut — so the caption is not unverified, it is FALSE, and a code
        # implying doubt about a settled question was half the defect.
        # `tests/test_def_716_cut_accrual_caption.py` now pins this string on
        # both sides of the stack.
        assert (
            kpis["cut_awaiting_payment_unavailable"]["code"] == "cut_accrual_caption_superseded"
        )

        # THE UNION: the protected account with no case is on the list.
        assert payload["total"] == 2
        assert _row_for(payload, okafor["account_no"])["case"] is None


# ════════════════════════════════════════════════════════════════════════════
# 7.11 · S90 — EVERY TILE IS A DOOR (`DEF-CUS-6055`)
# ════════════════════════════════════════════════════════════════════════════
def test_dsc_every_kpi_tile_equals_the_rows_of_its_own_segment(brazos, marcus, monkeypatch):
    """**A tile's number is the rows behind it — all five, one test.**

    `DEF-CUS-6055`, 2026-09-20: on the first two disconnections this product
    ever completed, the register read `DUE TO CUT · 2` over two households
    whose supply was already off, and the `Due to cut` view beside it returned
    **no rows at all**. `cut_scheduled_for` is not cleared by a cut — correctly,
    it is the record of when the supply went off — so a pure date test matched
    a cut case for ever. *A date that records WHEN something happened keeps
    matching a window that was meant to mean WHEN IT WILL.*

    **Why this check is not a tautology.** `kpi_strip` counts MODEL objects out
    of `open_cases()`; `disconnect_reads.KPI_SEGMENTS` reads the payload
    `list_row` builds over `_list_queryset()`. Two derivations, two row sets —
    so the assertion fails the moment either side drifts, and it fails ON THE
    TILE THAT DRIFTED because each one is asserted by name.

    **What would make it pass wrongly** (hard-won law 7's second habit): both
    sides making the same mistake — a state excluded from the tile AND from the
    row set. That is why the fixture below puts a case in every list state and
    a protected account beside them, so every tile has something to lose.

    The fixture, worked from `as_of = 2026-08-25`:

    | account | case | expected |
    |---|---|---|
    | Bramble Bakery | TIER 2, `notice_sent` | `AT NOTICE` |
    | Northwind Mfg. | TIER 3, cut booked **Aug 26** | `AT NOTICE` + `DUE TO CUT` |
    | Calloway | TIER 3, booked Aug 27, **now `cut`** | `CUT, AWAITING RECONNECT` |
    | Greaves | `reconnecting` | `RECONNECTIONS` |
    | Okafor | no case, medical certificate | `ON HOLD` |

    **`Calloway` is the row the defect was about**: booked inside the window and
    then cut, so the old tile counted it and the `Due to cut` view did not.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("8240.00"))

        bakery = _account(marcus, brazos, label="Bramble Bakery", name="Bramble Bakery")
        _at_tier(marcus, bakery["id"], disconnects.TIER_2)

        northwind = _account(marcus, brazos, label="77 Industrial Way", name="Northwind Mfg.")
        _at_tier(marcus, northwind["id"], disconnects.TIER_3)
        _prove_tier_3_service(marcus, northwind["id"])
        disconnects.schedule_cut(marcus, northwind["id"], cut_on=date(2026, 8, 26), as_of=TODAY)

        # ⚠ **THE STATE IS WRITTEN DIRECTLY AND THAT IS DELIBERATE.**
        # `commit_cut` bills, posts a fee, re-statuses the account and settles
        # — four acts this READ knows nothing about. What this test needs is a
        # row in the `cut` state carrying the cut date it was booked with,
        # which is exactly what a committed cut leaves behind. The same posture
        # `test_dsc_a_row_with_no_tier_renders_the_dash_as_an_absence` already
        # takes for `reconnecting`.
        calloway = _account(marcus, brazos, label="26 Calloway Ave", name="Calloway, Brett")
        _at_tier(marcus, calloway["id"], disconnects.TIER_3)
        _prove_tier_3_service(marcus, calloway["id"])
        disconnects.schedule_cut(marcus, calloway["id"], cut_on=date(2026, 8, 27), as_of=TODAY)
        cut_case = disconnects.open_case_for(calloway["id"])
        cut_case.state = disconnects.STATE_CUT
        cut_case.save(update_fields=["state", "updated_at"])

        # ⚠ **PO 2026-09-20 — THE ROW THIS TEST DID NOT HAVE, ADDED BY THE
        # CUT-DATE-WATCH LANE.** *"A case due last week stops looking identical
        # to one due next month."* Booked for **Aug 18**, a week BEFORE
        # `as_of`, and still waiting: `cut_date_is_this_week` is FALSE on it
        # (the window is forward-looking, by `_within_the_week`'s own
        # docstring), so no tile counts it and the register drew it in exactly
        # the same plain text as `northwind`'s Aug 26. It is here so
        # `_seg_due_to_cut` has an overdue row it must NOT count, and so the
        # `f.due` assertions below have something to find.
        overton = _account(marcus, brazos, label="9 Overton Lane", name="Overton, Ruth")
        _at_tier(marcus, overton["id"], disconnects.TIER_3)
        _prove_tier_3_service(marcus, overton["id"])
        disconnects.schedule_cut(marcus, overton["id"], cut_on=date(2026, 8, 18), as_of=TODAY)

        greaves = _account(marcus, brazos, label="12 Greaves Row", name="Greaves, Tom")
        opened = disconnects.open_case(marcus, greaves["id"], as_of=TODAY)
        back = disconnects.DisconnectCase.objects.get(id=opened["case_id"])
        back.state = disconnects.STATE_RECONNECTING
        back.save(update_fields=["state", "updated_at"])

        okafor = _account(marcus, brazos, label="77 Okafor Way", name="Okafor, Emmanuel")
        disconnects.record_protection(
            marcus,
            okafor["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 8, 1),
            expires_on=date(2026, 12, 31),
        )

        # ⚠ **EVERY ROW, NOT A PAGE.** A tile counts the whole set (`NFR-3`
        # governs how it is FETCHED, not how much of it a count covers), so the
        # row side has to walk the pager or the comparison is against a page.
        rows: list[dict] = []
        page = 1
        while True:
            payload = disconnect_reads.list_disconnects(page=page, per=2, as_of=TODAY)
            rows.extend(payload["rows"])
            if page >= payload["pages"]:
                break
            page += 1
        kpis = payload["kpis"]
        assert len(rows) == payload["total"] == 6

        behind_the_door = {
            tile: sum(1 for row in rows if predicate(row))
            for tile, predicate in disconnect_reads.KPI_SEGMENTS.items()
        }
        # The fixture's own arithmetic, so a green run over an EMPTY tenant —
        # where 0 == 0 five times — cannot be mistaken for a passing check.
        # ⚠ **`at_notice` IS 3 SINCE 2026-09-20 (`overton`).** The overdue row
        # carries a TIER 3 chip and is not cut, so it is *somewhere on the
        # ladder*; its date is in the PAST, so the seven-day window does not
        # hold it and `due_to_cut_this_week` stays 1. That gap is exactly what
        # the `f.due` assertions below cover.
        assert behind_the_door == {
            "at_notice": 3,
            "due_to_cut_this_week": 1,
            "on_hold_protected": 1,
            "cut_awaiting_payment": 1,
            "reconnections_due": 1,
        }
        for tile, expected in behind_the_door.items():
            assert kpis[tile] == expected, (
                f"the `{tile}` tile says {kpis[tile]} over {expected} rows in its own segment "
                "— DEF-CUS-6055. A tile is a door: count it by the predicate the list uses."
            )

        # The defect in one line, on the row it happened to: booked inside the
        # window, then cut. It is counted ONCE, by `CUT`, and not by `DUE TO CUT`.
        cut_row = next(row for row in rows if row["account_no"] == calloway["account_no"])
        assert cut_row["cut_date"] == "2026-08-27"
        assert cut_row["cut_date_is_this_week"] is True
        assert cut_row["state"]["stored"] == disconnects.STATE_CUT
        assert disconnect_reads.KPI_SEGMENTS["due_to_cut_this_week"](cut_row) is False

        # ══════════════════════════════════════════════════════════════════
        # PO 2026-09-20 — THE SAME CHECK, ON THE DOOR THE WATCH LANE ADDED
        # ══════════════════════════════════════════════════════════════════
        # ⚠ **EXTENDED HERE RATHER THAN WRITTEN AS A SECOND TEST, ON PURPOSE.**
        # Two checks over one subject that disagree are worse than one, and
        # this fixture already builds every state a case can hold — which is
        # what *"what would make this pass wrongly"* needs (law 7, habit 2).
        #
        # The PO's sentence, asserted: *"A case due last week stops looking
        # identical to one due next month."*
        overdue_row = next(row for row in rows if row["account_no"] == overton["account_no"])
        ahead_row = next(row for row in rows if row["account_no"] == northwind["account_no"])
        assert overdue_row["cut_date"] == "2026-08-18"
        assert ahead_row["cut_date"] == "2026-08-26"
        # ⚠ **UNTIL THIS LANE THE ONLY SIGNAL ON THIS COLUMN RAN THE WRONG WAY
        # ROUND.** §5.8.2 accents a cut date that is *this week*, and the window
        # is forward-looking — so the accent lands on `northwind`'s Aug 26,
        # which nobody has to do anything about yet, and leaves `overton`'s
        # Aug 18, a week LATE and still connected, in plain text. That is not a
        # missing emphasis; it is emphasis on the wrong row.
        assert ahead_row["cut_date_is_this_week"] is True
        assert overdue_row["cut_date_is_this_week"] is False
        # They are no longer the same row.
        assert overdue_row["cut_due"]["status"] == "overdue"
        assert overdue_row["cut_due"]["days_overdue"] == 7
        assert ahead_row["cut_due"]["status"] == "ahead"
        assert ahead_row["cut_due"]["days_overdue"] is None
        # ⛔ AND THE CUT ROW IS NOT LATE. `cut_scheduled_for` is not cleared by
        # a cut, so a pure date test reads Aug 27 as overdue for ever — which
        # is `DEF-CUS-6055`'s general shape and the reason `due_status` takes
        # the STATE as well as the date.
        assert cut_row["cut_due"]["status"] == "done"
        assert cut_row["cut_due"]["days_overdue"] is None

        # `f.due` is a DOOR, so its number is the rows behind it — the same
        # statement this test already makes about the five tiles, on the new
        # dimension.
        for view in ("due_now", "overdue"):
            served = disconnect_reads.list_disconnects(filters={"due": view}, as_of=TODAY, per=50)
            assert served["total"] == 1, view
            assert {row["account_no"] for row in served["rows"]} == {
                overton["account_no"]
            }, view

        # ⚠ **THE TWO DIMENSIONS COMPOSE AND NEITHER HIDES A ROW.** `f.state`
        # and `f.due` ask different questions, which is why this is a filter
        # and not a segment (`OQ-374`, untouched).
        both = disconnect_reads.list_disconnects(
            filters={"state": disconnects.STATE_SCHEDULED, "due": "overdue"},
            as_of=TODAY,
            per=50,
        )
        assert {row["account_no"] for row in both["rows"]} == {overton["account_no"]}

        # ⚠ **AND THE NIGHTLY WATCH READS THE SAME PREDICATE**, so a job that
        # runs at 02:00 and a clerk who opens the register at 08:00 cannot be
        # told different things. One function, three readers.
        register = disconnect_due.due_register(as_of=TODAY)
        assert (register["overdue"], register["due_today"], register["due_now"]) == (1, 0, 1)
        assert [row["account_no"] for row in register["cases"]] == [overton["account_no"]]
        assert register["cases"][0]["days_overdue"] == 7
        assert register["cases"][0]["case_no"] == disconnects.open_case_for(
            overton["id"]
        ).case_no
        # hard-won law 7 — what it skipped, WITH A NUMBER, beside what it
        # checked. `considered` is the denominator, so a sweep that looked at
        # nothing cannot read like a sweep that found nothing.
        assert register["considered"] == 5
        assert register["skipped"] == {
            "no_cut_date": 1,
            "already_cut": 1,
            "reconnecting": 1,
        }


def test_dsc_search_covers_customer_account_and_address(brazos, marcus, monkeypatch):
    """B18 §5.8.2: *"**Search:** "Customer, account #, address, or meter #…""*.
    Every leg is BR-CUS-053's, reached through the reader that already owns it,
    so the Disconnects box finds what the Accounts box finds."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, OKAFOR_OWED)
        okafor = _account(marcus, brazos, label="77 Okafor Way", name="Okafor, Emmanuel")
        disconnects.open_case(marcus, okafor["id"], as_of=TODAY)
        other = _account(marcus, brazos, label="12 Sandoval Row", name="Sandoval, Rita")
        disconnects.open_case(marcus, other["id"], as_of=TODAY)

        assert disconnect_reads.list_disconnects(q="Okafor", as_of=TODAY)["total"] == 1
        assert disconnect_reads.list_disconnects(q=okafor["account_no"], as_of=TODAY)["total"] == 1
        assert disconnect_reads.list_disconnects(q="Sandoval Row", as_of=TODAY)["total"] == 1
        assert disconnect_reads.list_disconnects(q="Nothing At All", as_of=TODAY)["total"] == 0
        # A one-character term is not a search (IS-3) — it must not filter.
        assert disconnect_reads.list_disconnects(q="O", as_of=TODAY)["total"] == 2


def test_dsc_the_list_paginates_and_serves_b18s_columns(brazos, marcus, monkeypatch):
    """11b G5, and §5.8.2's eight columns served as DATA.

    ⚠ **NINE SINCE 2026-08-27 — CR-039 wave D task 16**, the mirror of the
    transfer list's. §5.8.2's eight are unchanged and in order; `reference`
    leads them. Stamped in `disconnect_reads.COLUMNS` and on the column itself
    in `DisconnectsTab.tsx`.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, OKAFOR_OWED)
        for n in range(3):
            account = _account(marcus, brazos, label=f"{n} Ladder Row", name=f"Owing {n}")
            disconnects.open_case(marcus, account["id"], as_of=TODAY)

        first = disconnect_reads.list_disconnects(page=1, per=2, as_of=TODAY)
        assert first["total"] == 3 and first["pages"] == 2 and len(first["rows"]) == 2
        second = disconnect_reads.list_disconnects(page=2, per=2, as_of=TODAY)
        assert len(second["rows"]) == 1
        seen = {row["account_id"] for row in first["rows"]} | {
            row["account_id"] for row in second["rows"]
        }
        assert len(seen) == 3, "a row appeared on two pages — the order is not stable"

        assert first["columns"] == [
            "reference",  # CR-039 W-D 16 — not drawn by B18; see the docstring
            "account",
            "customer",
            "address",
            "owed",
            "tier",
            "cut_date",
            "last_notice",
            "state",
        ]
        assert first["search"]["hint"] == "Customer, account #, address, or meter #…"
        assert len(first["chips"]) == 6

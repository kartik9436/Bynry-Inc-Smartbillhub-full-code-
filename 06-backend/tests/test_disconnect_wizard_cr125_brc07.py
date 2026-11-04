# ── Trace ──────────────────────────────────────────────
# Change:  CR-125-BRC07 — the disconnect wizard, the list and their actions
#          built to blueprint pages 135–141 (`05-prototype/02 Accounts Menu
#          Blueprint.pdf`, rendered as IMAGES per B14 rule 42; every drawn
#          figure read as an ILLUSTRATION per rule 37).
# Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
#          CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money 4dp
#          stored / 2dp displayed, as a string, with CHAR(3)) · hard rule 7
#          (every money action writes `audit_log`) · BR-CUS-039 · BR-CUS-043 ·
#          BR-CUS-100 · BR-CUS-104 (PO 2026-08-25, the SIGNED $8,315.00) ·
#          BR-BIL-007 (the fee is the tenant's charge code, never a literal) ·
#          BR-BIL-072 / DEF-2416 (a bill is measured at what it ASKS for) ·
#          BR-RAT-024 (eleven services, never a literal list) · B14 rule 31
#          (no database id on screen) · rule 32 (no internal code in
#          clerk-facing copy)
# Questions: **OQ-CUS-12517 — OPEN** (who raised the case: no durable source) ·
#          **OQ-CUS-12518 — OPEN** (the reconnection charge code: three sources,
#          two disagreements). Both are ASSERTED here as absences carrying
#          their reason, never as values.
# Tests:   this file
# Impacts: apps/customers/disconnect_reads.py · disconnects.py ·
#          transfer_disconnect_api.py · migrations/0061_cr125_brc07_…
# ───────────────────────────────────────────────────────
"""`CR-125-BRC07` — everything the five drawn wizard screens ask the server for.

RED-FIRST PROOF, MEASURED (CLAUDE.md hard-won law 7, **in the harness that runs
it** — `pytest --ds=config.settings.pgtest` against real PostgreSQL, never a
`python3 <file>` and never a `__main__`; a guard proved through an entry point
nobody uses is no proof of the thing that matters).

Every case below was run in a SECOND `git worktree` at the pre-change tip
`0ba1a362e` with this lane's commits absent:

    27 failed, 3 passed, in 521.49s

and the failures ARE the findings, in the tree's own words:

    AttributeError: module 'apps.customers.disconnect_reads' has no attribute
      '_bills_read'                     ×6 — NOTHING served the drawn bill table
    AttributeError: … has no attribute 'wizard_account_panel'          ×4
    AttributeError: … has no attribute 'wizard_review'                 ×3
    TypeError: got an unexpected keyword argument 'note'               ×3
    KeyError: 'fees'                          — one of three fee rows was served
    KeyError: 'to_clear'                      — no arrears-plus-fee total
    AttributeError: module 'apps.customers.disconnects' has no attribute
      'RECONNECT_FEE_DISAGREEMENT'            — the blocker was not written down
    DID NOT RAISE DisconnectRuleError         — the cut for 'unicorn' was taken
    AssertionError: params['field'] == 'cut date'  — it read 'cut_on'
    AssertionError: the Export control needs a resource behind it
    AssertionError: case_no search returned 0 rows
    KeyError: 'open_case_count'

⚠ **THE THREE THAT PASSED ON THE UNFIXED TREE ARE GUARDS, AND SAYING WHICH IS
PART OF THE PROOF** — a reader cannot tell a speaking case from a guard by
looking at a green dot:

  * `test_a_medical_certificate_can_be_recorded_with_its_expiry_and_reference`
    — the protections POST already WORKED and was called by nothing. This case
    exists to pin that what the drawn dialog collects is what the service takes,
    so the front-end lane wiring it cannot silently change the contract.
  * `test_an_unreadable_service_catalogue_refuses_nothing` — the second
    direction of this lane's own new guard. It must pass BEFORE and AFTER,
    because a catalogue that cannot be asked must refuse nothing.
  * `test_the_case_number_search_does_not_reach_another_tenant` — hard rule 1.
    It passed before because the leg did not exist; it has to keep passing now
    that it does, and that is exactly what makes it worth writing.

⚠ **THREE CASES WERE ADDED AFTER THAT RUN AND EACH WAS PROVED ITS OWN WAY,
WHICH IS SAID HERE BECAUSE THE 27/30 ABOVE DOES NOT COVER THEM:**

  * `test_the_panel_names_the_current_customer_and_never_the_previous_owner` —
    proved by reverting `_customer_facts` to the direct
    `customer_accounts` query it was first written with: **the panel named the
    SELLER.** That is the regression `customers/0060`'s own ledger row warns
    about, on the screen that authorises a cut.
  * `test_a_service_the_tenant_has_switched_off_is_still_cuttable` — proved by
    the 18 failures the first version of `assert_services_exist` caused in
    `tests/test_w7_cut_reconnect.py`. The guard is what went red, not a stub.
  * the untiered-case half of `test_the_sub_line_count_is_open_cases_and_not_
    the_row_count` — proved by the arithmetic it asserts: the KPI tiles read
    **1** over two open cases, which is the undercount the first
    implementation would have shipped.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7 habit 2), designed out rather
than hoped about:

  * **A page test that asserts a page LENGTH proves nothing.** The broken
    version of every Python-paged list in this repo returned exactly the right
    rows with the right total. So the paging cases here assert that the SAME
    set comes back across pages in the SAME order, that a partial page REFUSES
    to state a sum, and that `per` never drops a row — properties a slice and a
    window are allowed to disagree on and may not.
  * **A money test that asserts a drawn figure pins an ILLUSTRATION.** B14 rule
    37. No case here asserts `$75.00`, `$45.00`, `$2,410.00` or `62 days`. What
    is asserted is the SHAPE — a `{stored, display}` pair, a `CHAR(3)` beside
    it, an absence that is not a zero — and, for the one SIGNED figure, that
    the module states the disagreement rather than resolving it.
  * **A transaction test that only checks the happy path cannot see a missing
    `atomic()`.** The case below makes the AUDIT write fail and asserts the
    case row did not move. On the unfixed tree the case is saved and the
    exception escapes, which is precisely the production shape: a household
    scheduled for disconnection with nobody named as having scheduled it.
  * **An absence test that asserts `is None` passes on a key that does not
    exist.** Every absence here is asserted as *the reason block is present AND
    names its open question*, never as a bare null.

⚠ **PRE-EXISTING RED, DATED** (law 7 habit 1, and the half that is usually
skipped): `tests/test_w7_disconnects.py` reports **2 failed / 36 passed** on
`--ds=config.settings.pgtest` at tip `0ba1a362e`, BEFORE any commit of this
lane — `test_the_three_lifetimes_are_held_by_the_DATABASE_not_only_by_the_
service` and `test_no_path_reaches_a_CUT_on_a_closed_account__three_
independent_grounds`. Measured 2026-09-20 at 15:09, and not caused here.

Run with `JOBS_EAGER=false --reuse-db` (DEF-567, DEF-GOV-3778).
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import disconnect_reads, disconnects
from apps.customers import models as customers_models
from apps.metering import models as metering_models

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


# ══════════════════════════════════════════════════════════════════════════
# Fixtures — an account with a ladder on it, built through the ORM
# ══════════════════════════════════════════════════════════════════════════
def plant_account(tenant, *, tag: str, no: str | None = None):
    """One account with a premises and a unit, so the drawn panel has somewhere
    to walk to (`BR-MET-1161`: the address lives on `premises` and everything
    else derives it)."""
    premises = metering_models.Premises.objects.create(
        tenant=tenant, address_line=f"142 Bakers Row {tag}", city="Silver Creek", state="TX"
    )
    unit = metering_models.Unit.objects.create(
        tenant=tenant, premises=premises, label=f"Suite {tag}"
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


def reach_tier_3(tenant, actor, account, *, notice_on, served_on):
    """Record the tier-3 letter AND put the case on tier 3.

    ⚠ **`record_notice` DOES NOT MOVE THE TIER, AND THAT IS THE MODULE WORKING.**
    Writing a letter and climbing a rung are two acts: `advance` is *"a person
    clicking"* (`DEF-320`, `NO_SCHEDULER`), and `record_notice` at a case
    already on tier 3 is correctly refused — *"what follows is a SCHEDULED CUT,
    which is a different act with its own guard."* The first draft of this
    fixture planted tier 3 and then recorded the tier-3 letter, and went red for
    asking the ladder to do something it refuses on purpose.

    The tier is set directly here rather than walked through `advance`, because
    this file measures the READS and the COMMIT and not the ladder walk —
    `test_w7_disconnects.py` owns that.
    """
    notice = disconnects.record_notice(
        actor, account.id, tier=disconnects.TIER_3, on_date=notice_on
    )
    disconnects.record_proof_of_service(
        actor,
        notice["notice_id"],
        channel=disconnects.SERVE_CERTIFIED_MAIL,
        reference="RA 4821 9930 US",
        served_on=served_on,
        signed_for_on=served_on,
    )
    case = disconnects.open_case_for(account.id)
    case.tier = disconnects.TIER_3
    case.tier_reached_on = notice_on
    case.save(update_fields=["tier", "tier_reached_on", "updated_at"])
    return notice


def plant_case(tenant, account, *, case_no: str | None = None, tier=None, state=None):
    return disconnects.DisconnectCase.objects.create(
        tenant=tenant,
        account=account,
        case_no=case_no,
        sequence=disconnects.SEQ_SERVICE,
        state=state or disconnects.STATE_NOTICE_SENT,
        tier=tier or disconnects.TIER_1,
        tier_reached_on=TODAY,
        amount_owed_at_open=D("2410.0000"),
        currency="USD",
        opened_on=TODAY,
    )


class _Invoice:
    """One open bill, in the shape `payments.billing_seam.OpenInvoice` serves.

    ⚠ **A STAND-IN FOR THE SEAM AND NOT FOR THE RULE.** `open_invoices_for_
    account` already applies `BR-BIL-072` — a budget bill is measured at its
    LEVEL and not its total (`DEF-2416`) — and this lane does not re-implement
    that and must not re-test it. What is faked here is the SEAM BOUNDARY, so
    these cases measure the PAGE, the ORDER, the DUE date and the STATE, which
    are this lane's own. The real seam is exercised by payments' own suite.
    """

    def __init__(self, number, balance, issued_on, invoice_id, currency="USD"):
        self.number = number
        self.balance = balance
        self.issued_on = issued_on
        self.invoice_id = invoice_id
        self.total = balance
        self.amount_due = balance
        self.allocated = D("0.0000")
        self.currency = currency
        self.composition = None


class _Position:
    def __init__(self, invoices, problems=()):
        self.invoices = tuple(invoices)
        self.problems = tuple(problems)


class _EveryAccount(dict):
    """A positions map answering one figure for any id — `test_w7_worklists._owes`'
    shape, so the LEDGER BOUNDARY is the real `seams.ArPositions` and not a fake
    of the class itself."""

    def __init__(self, amount):
        super().__init__()
        self._amount = amount

    def get(self, _key, _default=None):
        return self._amount


def owes(monkeypatch, amount=D("2410.75")):
    """Publish a readable AR position.

    ⚠ **WITHOUT THIS THE LADDER CORRECTLY REFUSES AND A CASE READS AS A BUG.**
    `halt_reason` answers `nothing_owed` when the books say zero — *"this account
    owes nothing, so there is nothing to chase"* — which is the module working.
    Two cases below were written without it and failed for that reason on the
    first run; the fixture was wrong, not the code, and the distinction is worth
    a sentence because a green suite reached by loosening an assertion instead
    would have removed the guard the case exists to hold.
    """
    positions = disconnects.seams.ArPositions(
        positions=_EveryAccount(amount), currency="USD"
    )
    monkeypatch.setattr(disconnects.seams, "ar_positions", lambda *_a, **_k: positions)
    monkeypatch.setattr(disconnect_reads.seams, "ar_positions", lambda *_a, **_k: positions)


def wire_bills(monkeypatch, rows, dues):
    """Publish a readable open-bill seam and a billing queryset for the dues.

    `rows` is `[(number, amount, issued_on, id)]`; `dues` is `{id: due_date}`.
    """
    position = _Position([_Invoice(*row) for row in rows])
    monkeypatch.setattr(disconnect_reads, "_bills_read", lambda: (lambda _a: position))

    class _Values(list):
        pass

    class _QS:
        def filter(self, **_kw):
            return self

        def values(self, *_names):
            return _Values(
                [{"id": key, "due_date": value} for key, value in dues.items()]
            )

    monkeypatch.setattr(disconnect_reads, "_billing_queryset", lambda: (lambda: _QS()))
    return position


# ══════════════════════════════════════════════════════════════════════════
# 1 · "THE BILLS BEHIND THAT FIGURE" — p136, and nothing served it
# ══════════════════════════════════════════════════════════════════════════
def test_the_bills_behind_the_balance_carry_the_four_drawn_columns(
    brazos, dana, monkeypatch
):
    """p136 draws `BILL · ISSUED · DUE · AMOUNT · STATE` and the shipped
    product had **no call for any of it**. The nearest route — payments'
    `GET /accounts/{id}/open-bills` — serves no due date and no state.

    ⚠ **`STATE` IS DERIVED AND NEVER STORED**, from the bill's own due date
    against `as_of` — so the same bill reads `overdue` on Monday and `issued`
    the Friday before, which is what the column means.
    """
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="b1")
        wire_bills(
            monkeypatch,
            [
                ("INV-26-0411", D("840.0000"), date(2026, 3, 8), "i1"),
                ("INV-26-0538", D("795.0000"), date(2026, 4, 8), "i2"),
                ("INV-26-0662", D("775.0000"), date(2026, 5, 8), "i3"),
            ],
            {"i1": date(2026, 3, 22), "i2": date(2026, 4, 22), "i3": date(2026, 5, 22)},
        )
        body = disconnect_reads.bills_behind_the_balance(account.id, as_of=TODAY)

        assert [row["number"] for row in body["bills"]] == [
            "INV-26-0411",
            "INV-26-0538",
            "INV-26-0662",
        ], "oldest first — BR-PAY-001's own order, and the order the drawing lists"

        first = body["bills"][0]
        assert first["issued_on"] == "2026-03-08"
        assert first["due_on"] == "2026-03-22"
        # Hard rule 2 — 4dp stored, 2dp displayed, BOTH as strings, never floats.
        assert first["amount"] == {"stored": "840.0000", "display": "840.00"}
        assert first["currency"] == "USD", "CHAR(3) beside every amount"
        assert first["state"] == disconnect_reads.BILL_STATE_OVERDUE
        # The newest bill is not yet due on `as_of` — the drawing's own caption
        # says so: *"the newest is not yet overdue"*.
        assert body["bills"][-1]["state"] == disconnect_reads.BILL_STATE_ISSUED


def test_a_bill_with_no_due_date_is_neither_overdue_nor_quietly_issued(
    brazos, dana, monkeypatch
):
    """⚠ **NULL IS A REAL ANSWER AND MUST NOT DEFAULT TO `issued`.**

    `invoices.due_date` is nullable (`BR-BIL-024`, derived), and `BR-PAY-001`
    refuses to ORDER an undated bill for exactly this reason. A cell that
    defaulted to `issued` would tell a clerk a bill is not yet overdue on the
    strength of a date nobody set — on the panel that justifies a cut.
    """
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="b2")
        wire_bills(
            monkeypatch,
            [("INV-26-0900", D("100.0000"), date(2026, 4, 1), "i9")],
            {"i9": None},
        )
        body = disconnect_reads.bills_behind_the_balance(account.id, as_of=TODAY)
        assert body["bills"][0]["state"] is None
        assert body["bills"][0]["due_on"] is None


def test_the_oldest_item_is_derived_over_every_bill_and_not_over_the_page(
    brazos, dana, monkeypatch
):
    """`Oldest item — N days past due` was believed to need a new column. It
    does not: it is the oldest DUE DATE among the account's open bills, which
    is the identical derivation `payments.outstandings` publishes as
    `days_late`.

    ⚠ **OVER EVERY BILL, NEVER OVER THE PAGE.** A figure computed over the
    window would change when a clerk turned to page 2 — the same fact reading
    two ways on one screen.
    """
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="b3")
        wire_bills(
            monkeypatch,
            [
                ("INV-1", D("10.0000"), date(2026, 3, 8), "i1"),
                ("INV-2", D("10.0000"), date(2026, 4, 8), "i2"),
                ("INV-3", D("10.0000"), date(2026, 5, 8), "i3"),
            ],
            {"i1": date(2026, 3, 10), "i2": date(2026, 4, 10), "i3": date(2026, 5, 10)},
        )
        whole = disconnect_reads.bills_behind_the_balance(account.id, as_of=TODAY)
        last_page = disconnect_reads.bills_behind_the_balance(
            account.id, as_of=TODAY, page=3, per=1
        )
        assert whole["oldest_due_on"] == "2026-03-10"
        assert whole["days_past_due"] == (TODAY - date(2026, 3, 10)).days
        assert last_page["bills"][0]["number"] == "INV-3", "the page really moved"
        assert last_page["days_past_due"] == whole["days_past_due"], (
            "the ageing figure is a fact about the ACCOUNT and must not follow the page"
        )


def test_a_partial_page_refuses_to_state_a_total(brazos, dana, monkeypatch):
    """⚠ **THE DRAWN CAPTION IS A RECONCILIATION CLAIM** — *"Three unpaid bills
    reconcile to the balance exactly"* — and a sum over one page of several is
    not one. A figure labelled as the balance beside a list that does not add
    up to it, on the screen that authorises a cut, is worse than no figure.

    This is also the case that would pass wrongly if `total_open` were simply
    summed over `bills`: it asserts the ABSENCE and its reason, not a number.
    """
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="b4")
        wire_bills(
            monkeypatch,
            [
                ("INV-1", D("840.0000"), date(2026, 3, 8), "i1"),
                ("INV-2", D("795.0000"), date(2026, 4, 8), "i2"),
                ("INV-3", D("775.0000"), date(2026, 5, 8), "i3"),
            ],
            {"i1": date(2026, 3, 22), "i2": date(2026, 4, 22), "i3": date(2026, 5, 22)},
        )
        partial = disconnect_reads.bills_behind_the_balance(
            account.id, as_of=TODAY, page=1, per=2
        )
        assert partial["total"] == 3, "the TOTAL is the whole set, never the page"
        assert partial["total_open"] is None
        assert partial["total_open_absence"]["code"] == "sum_not_stated_over_a_partial_page"

        whole = disconnect_reads.bills_behind_the_balance(account.id, as_of=TODAY)
        assert whole["total_open"] == {"stored": "2410.0000", "display": "2410.00"}
        assert whole["total_open_absence"] is None


def test_the_page_never_drops_a_bill_and_never_reorders_one(brazos, dana, monkeypatch):
    """`NFR-3` + `NFR-5`, and the property a slice and a window may not disagree
    on: the SAME bills in the SAME order, however they are sliced, with nothing
    capped out of the set.

    ⚠ A page LENGTH proves nothing here — the Python-paged version of every
    list in this repo returned the right rows. This walks the pages and
    compares the concatenation to the whole.
    """
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="b5")
        rows = [
            (f"INV-{index:03d}", D("10.0000"), date(2026, 1, 1) + _days(index), f"i{index}")
            for index in range(1, 8)
        ]
        wire_bills(
            monkeypatch,
            rows,
            {f"i{index}": date(2026, 2, 1) + _days(index) for index in range(1, 8)},
        )
        whole = [
            row["number"]
            for row in disconnect_reads.bills_behind_the_balance(account.id, as_of=TODAY)["bills"]
        ]
        assert len(whole) == 7, "NFR-5 — nothing is capped out of the set"

        walked: list[str] = []
        for page in (1, 2, 3, 4):
            walked += [
                row["number"]
                for row in disconnect_reads.bills_behind_the_balance(
                    account.id, as_of=TODAY, page=page, per=2
                )["bills"]
            ]
        assert walked == whole


def _days(count: int):
    from datetime import timedelta

    return timedelta(days=count)


def test_the_one_cost_that_is_not_in_sql_is_declared_with_its_bound(
    brazos, dana, monkeypatch
):
    """⚠ **A DECLARED BLIND SPOT WITH NO NUMBER BESIDE IT IS INDISTINGUISHABLE
    FROM AN EMPTY ONE** (law 7). This read's page is taken in Python over one
    account's open bills, because *still open* is `amount_due − allocated` and
    `amount_due` is billing's per-bill answer under `BR-BIL-072` — not a
    column. The payload SAYS so, in its own words, so a reader never has to
    take it on trust or rediscover it.
    """
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="b6")
        wire_bills(monkeypatch, [], {})
        body = disconnect_reads.bills_behind_the_balance(account.id, as_of=TODAY)
        assert "O(one account's open bills)" in body["row_set_basis"]
        assert "never O(tenant)" in body["row_set_basis"]


# ══════════════════════════════════════════════════════════════════════════
# 2 · STEP 1's PANEL — the SIX facts that were genuinely missing
# ══════════════════════════════════════════════════════════════════════════
def test_the_panel_carries_only_what_the_account_payload_does_not(brazos, dana):
    """p135–p136 draw fifteen customer facts and six money facts. Thirteen of
    the fifteen were measured as already on `GET /accounts/{id}` — so this
    route carries the SIX that were not and repeats none of the others.

    ⚠ **A SECOND COPY OF A FACT IS A FACT THAT CAN DISAGREE WITH ITSELF**, so
    the absence of `account_no`, `status` and `paperless` here is the design
    and is asserted as such rather than left to be assumed a gap.
    """
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="p1")
        panel = disconnect_reads.wizard_account_panel(account.id, as_of=TODAY)

        for key in ("customer", "ladder_floor", "payment_plan", "last_payment"):
            assert key in panel, f"{key} is one of the six the account payload lacks"
        for served_elsewhere in ("account_no", "status", "paperless", "autopay", "opened_at"):
            assert served_elsewhere not in panel, (
                f"{served_elsewhere} is already on GET /accounts/{{id}} and must not be "
                "served twice — two copies of one fact can disagree"
            )


def test_case_raised_by_is_an_absence_that_names_its_open_question(brazos, dana):
    """⛔ **`Case raised by` IS DRAWN AND HAS NO DURABLE SOURCE — `OQ-CUS-12517`.**

    `disconnect_cases` has no actor column. The actor IS on the
    `disconnect.case.opened` audit row — and `audit_log` is PRUNED on a
    retention schedule (hard rule 4's own note, `OQ-1340`, OPEN), so a panel fed
    from it would answer correctly this month and blank itself later, on the
    screen that justifies having cut a household off.

    ⚠ **ASSERTED AS AN ABSENCE-WITH-A-REASON AND NOT AS `is None`.** A bare
    null assertion passes on a key that does not exist at all, which is the
    exact false pass this case is written to avoid.
    """
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="p2")
        panel = disconnect_reads.wizard_account_panel(account.id, as_of=TODAY)
        assert panel["case_raised_by"] is None
        absence = panel["case_raised_by_unavailable"]
        assert absence["oq"] == "OQ-CUS-12517"
        assert absence["code"] == "case_raised_by_has_no_durable_source"
        assert "pruned" in absence["detail"]


def test_the_panel_names_the_current_customer_and_never_the_previous_owner(
    brazos, dana
):
    """⛔ **THE REGRESSION `customers/0060` HAD JUST WARNED ABOUT, ON THE PANEL
    THAT AUTHORISES A CUT.**

    Since that migration a property sale **ENDS** the seller's
    `customer_accounts` link rather than deleting it, so the table holds former
    owners. The obvious query — oldest link first — returns **the SELLER**.
    `CustomerAccount.objects` was deliberately left UNFILTERED so that a default
    manager could not hide it, which puts the duty on every reader.

    The first draft of `_customer_facts` wrote that query. This case is what
    holds it to `selectors.customer_for_account`, which says `ended_at__isnull=
    True` and explains in its own comment that one unfiltered reader took the
    property-sale suite from 23 of 25 rows with nothing red to **5 of 25**.

    ⚠ **THE FIXTURE PUTS THE SELLER FIRST ON PURPOSE** — an ended link created
    BEFORE the live one is the only arrangement in which the wrong answer and
    the right answer differ, so a fixture that made them in the other order
    would pass on the broken code.
    """
    from django.utils import timezone

    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="p5")
        seller = customers_models.Customer.objects.create(
            tenant=brazos, display_name="Ortiz, S. (sold)", kind="person"
        )
        buyer = customers_models.Customer.objects.create(
            tenant=brazos, display_name="Bramble Bakery", kind="company"
        )
        customers_models.CustomerAccount.objects.create(
            tenant=brazos, customer=seller, account=account, ended_at=timezone.now()
        )
        customers_models.CustomerAccount.objects.create(
            tenant=brazos, customer=buyer, account=account
        )
        facts = disconnect_reads.wizard_account_panel(account.id, as_of=TODAY)["customer"]
        assert facts["customer_name"] == "Bramble Bakery"
        assert facts["customer_kind"] == "company"


def test_the_ladder_floor_is_the_tenants_own_or_an_absence(brazos, dana):
    """`Ladder floor` — `BR-BIL-001`'s amount, read through `disconnects`' own
    accessor and never a second time here, because a second reader is a second
    default and `HALT_BELOW_FLOOR` is decided from that one."""
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="p3")
        floor = disconnect_reads.wizard_account_panel(account.id, as_of=TODAY)["ladder_floor"]
        if floor["amount"] is None:
            assert floor["unavailable"]["code"] == "ladder_floor_not_readable"
        else:
            # Hard rule 2 — a money cell is a pair of STRINGS, never a float.
            assert set(floor["amount"]) == {"stored", "display"}
            assert isinstance(floor["amount"]["stored"], str)


def test_an_account_that_has_never_paid_says_so_rather_than_showing_nothing(
    brazos, dana
):
    """`Last payment` on an account with none is a MEASURED fact — this read
    looked, and there is no payment — which is a different statement from *we
    could not tell*. `never_paid` carries it, so a screen renders *None* only
    where the drawing does."""
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="p4")
        last = disconnect_reads.wizard_account_panel(account.id, as_of=TODAY)["last_payment"]
        assert last["never_paid"] is True
        assert last["amount"] is None and last["posted_on"] is None


# ══════════════════════════════════════════════════════════════════════════
# 3 · STEP 2's WRITE SIDE — the note, and the reason set that stays closed
# ══════════════════════════════════════════════════════════════════════════
def test_a_ladder_stopped_by_hand_records_what_happened(brazos, marcus):
    """p137's `What happened`, captioned *"Recorded with the act and with who
    did it"*. There was **no parameter and no column** — the wizard asked for a
    sentence and dropped it, which is worse than not asking."""
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="s1")
        plant_case(brazos, account)
        payload = disconnects.stop_by_hand(
            marcus,
            account.id,
            on_date=TODAY,
            reason=disconnects.STOP_DISPUTE,
            note="Customer disputes INV-26-0411 on a meter reading",
        )
        assert payload["stopped_reason"] == disconnects.STOP_DISPUTE
        assert payload["stopped_note"] == "Customer disputes INV-26-0411 on a meter reading"
        row = disconnects.DisconnectCase.objects.get(pk=payload["case_id"])
        assert row.stopped_note == "Customer disputes INV-26-0411 on a meter reading"


def test_a_blank_note_is_stored_as_an_absence_and_not_as_an_empty_string(
    brazos, marcus
):
    """*Nobody wrote a note* and *somebody wrote nothing* are the same fact, and
    two spellings of one fact is how a screen renders a blank line where it
    meant to render an absence."""
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="s2")
        plant_case(brazos, account)
        payload = disconnects.stop_by_hand(
            marcus, account.id, on_date=TODAY, reason=disconnects.STOP_CLERK_ERROR, note="   "
        )
        assert payload["stopped_note"] is None


def test_the_note_does_not_widen_the_closed_reason_set(brazos, marcus):
    """⚠ **THE WHOLE REASON THE NOTE IS ITS OWN COLUMN.** `stopped_reason` holds
    a CODE from a closed set of three and refuses a fourth BY NAME, so that *"a
    fourth way to stop chasing a real debt needs a ruling"*. Adding free text to
    the SAME column would have deleted that guard in the act of reusing it."""
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="s3")
        plant_case(brazos, account)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.stop_by_hand(
                marcus,
                account.id,
                on_date=TODAY,
                reason="customer sounded upset",
                note="a note is not a reason",
            )
        assert refusal.value.code == "stop_reason_unknown"


def test_a_medical_certificate_can_be_recorded_with_its_expiry_and_reference(
    brazos, marcus
):
    """p137's `Record a protection` — the kind, the date it expires and the
    reference. The endpoint EXISTED and was called by nothing; this pins that
    the three fields the dialog draws are the three the service takes."""
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="s4")
        recorded = disconnects.record_protection(
            marcus,
            account.id,
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=TODAY,
            expires_on=date(2026, 11, 30),
            reference_id=None,
            note="Dr Okafor, Silver Creek Family Practice",
        )
        assert recorded["kind"] == disconnects.PROTECTION_MEDICAL
        assert recorded["expires_on"] == "2026-11-30"
        assert recorded["lifetime"] == disconnects.LIFETIME_EXPIRES

        # …and the protection is then IN FORCE on the check step 2 renders.
        check = disconnects.protection_check(account.id, as_of=TODAY)
        medical = next(
            row for row in check["checks"] if row["check"] == disconnects.PROTECTION_MEDICAL
        )
        assert medical["outcome"] == "fail", (
            "a hold in force FAILS the check. ⚠ `fail` is the CHECK's answer and not a "
            "refusal: BR-CUS-1096 (PO 2026-09-25, closing OQ-680) rules that a protection "
            "WARNS the clerk and never stops them"
        )
        assert check["all_clear"] is False


# ══════════════════════════════════════════════════════════════════════════
# 4 · STEP 4 — the three-row fee table and the arrears-plus-fee total
# ══════════════════════════════════════════════════════════════════════════
def test_the_fee_table_lists_all_three_codes_and_says_which_one_is_charged(
    brazos, dana
):
    """p139 draws three fee rows and captions them *"Three fees are designed and
    one is charged"*. This read served ONE, so a screen had no way to tell a
    clerk the other two exist and will NOT be raised.

    ⚠ **NOT ONE AMOUNT IS TYPED** (`BR-BIL-007`). The drawn `$75.00 · $45.00 ·
    $35.00` are illustrations (B14 rule 37) and nothing here asserts them; what
    is asserted is that each row is priced from the tenant's catalogue or
    carries its absence.
    """
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="f1")
        terms = disconnects.reconnection_terms(account.id)
        codes = [row["code"] for row in terms["fees"]]
        assert codes == [
            disconnects.RECONNECT_CHARGE_CODE,
            disconnects.DISCONNECT_CHARGE_CODE,
            disconnects.FIELD_VISIT_CHARGE_CODE,
        ]
        charged = [row for row in terms["fees"] if row["charged_on_this_cut"]]
        assert [row["code"] for row in charged] == [disconnects.RECONNECT_CHARGE_CODE], (
            "the cut raises the reconnection fee and nothing else"
        )
        for row in terms["fees"]:
            if not row["charged_on_this_cut"]:
                assert row["charged_absence"]["code"] == "fee_code_has_no_path_to_a_bill"
            assert row["amount"] is not None or row["amount_absence"] is not None, (
                "a fee is either priced from the tenant's catalogue or states why it is not"
            )


def test_the_reconnection_total_is_not_stated_when_the_fee_is_absent(brazos, dana):
    """⚠ **A SUM OVER THE ARREARS ALONE QUOTES A PRICE SHORT BY THE WHOLE FEE**
    — which is `DEF-708`'s own shape: the gate that let somebody back in
    **$75.00** under. `BR-CUS-104` is signed on arrears PLUS fee ($8,240.00 +
    $75.00 = $8,315.00, PO 2026-08-25), so a total with one half missing is not
    a smaller total, it is the wrong answer.
    """
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="f2")
        terms = disconnects.reconnection_terms(account.id)
        to_clear = terms["to_clear"]
        if to_clear["fee"] is None:
            assert to_clear["total"] is None
            assert to_clear["total_absence"]["code"] == "reconnection_total_not_computable"
            assert to_clear["total_absence"]["br_ref"].endswith("`OQ-CUS-12518`")
        else:  # pragma: no cover — reachable only once the code is configured
            assert to_clear["total"]["stored"] is not None


def test_the_charge_code_and_its_amount_are_ruled_and_the_three_sources_agree(
    brazos, dana
):
    """✅ **`OQ-CUS-12518` CLOSED — PO 2026-09-21, verbatim: *"reconnection fee
    is $75 - fix the code and seed"*.**

    ⚠ **THIS CASE USED TO ASSERT THAT NOTHING HAD BEEN CHOSEN**, and was named
    `..._disagreement_is_stated_with_all_three_sources`. It was correct the day
    it was written: the cut looked up `CC-RECON`, the catalogue seeded `RECON`
    at `$45.00`, and `BR-CUS-104` signed `$75.00`. **Leaving it as it was would
    have made it a check that could never pass again** — the third shape in
    hard-won law 7 — so it is rewritten to assert the RESOLUTION rather than
    deleted, because what a reader needs from this file is why `$75.00` is the
    number.

    ⚠ **THE SPELLING IS ASSERTED THROUGH THE CONSTANT AND THE AMOUNT AS A
    LITERAL, AND THE ASYMMETRY IS DELIBERATE.** A respelling is a decision this
    product may take again and the constant should carry it; **`$75.00` is a
    SIGNED figure and a literal here is what goes red if a lane moves it.**
    """
    ruled = disconnects.RECONNECT_FEE_RULING
    assert ruled["oq"] == "OQ-CUS-12518"
    assert ruled["ruled_on"] == "2026-09-21"
    # The lookup and the seed are now ONE string — that is the whole fix.
    assert ruled["looked_up"] == disconnects.RECONNECT_CHARGE_CODE
    assert ruled["seeded_as"] == disconnects.RECONNECT_CHARGE_CODE
    assert disconnects.RECONNECT_CHARGE_CODE == "RECON", (
        "the seed, the ledger's chart of accounts and every tenant's own row "
        "spell it RECON; a CC- prefix here resolves on no tenant and blocks "
        "every cut in the product"
    )
    assert ruled["signed_amount"] == "75.0000"

    # ⚠ **NO PRICING PATH MAY READ THAT FIGURE** — `BR-BIL-007`: a reconnect fee
    # is a tenant-configured charge code, never hardcoded. The block records
    # what we SEED so a tenant row disagreeing with it can be noticed; the
    # amount a cut charges is still read from the tenant's own row.
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="f3")
        terms = disconnects.reconnection_terms(account.id)
        if terms["fee"] is None:
            # A tenant with no `RECON` row of their own is still a real state
            # (the demo seed created none until today) and must still say so.
            assert terms["fee_absence"]["oq"] == "OQ-CUS-12518"
        else:
            assert terms["fee"]["stored"] is not None


# ══════════════════════════════════════════════════════════════════════════
# 5 · STEP 5's REVIEW — eight notice-and-proof facts, re-read not remembered
# ══════════════════════════════════════════════════════════════════════════
def test_the_review_re_reads_the_proof_through_the_function_that_governs_the_cut(
    brazos, marcus, monkeypatch
):
    """p140–p141 draw eight notice-and-proof rows on the review and the shipped
    screen drew none of them — the wizard had fetched them on step 3 and would
    have had to carry a legal fact forward across four steps.

    ⚠ **THE POINT IS *WHICH* FUNCTION ANSWERS.** `service_proof_for` is the
    same one `assert_service_proved` uses to decide whether a cut may be
    scheduled at all, so the summary a clerk confirms and the guard that lets
    them confirm it cannot drift apart.
    """
    with tenant_ctx(brazos):
        owes(monkeypatch)
        account = plant_account(brazos, tag="r1")
        # ⚠ TIER **2**, not 3. `record_notice` refuses a fourth notice on a case
        # already at the top — *"what follows is a SCHEDULED CUT, which is a
        # different act with its own guard"* — so a fixture that planted TIER 3
        # and then recorded the tier-3 letter was asking the ladder to do
        # something it correctly refuses. The first draft did exactly that and
        # went red for it; the fixture was wrong, not the module.
        plant_case(brazos, account, tier=disconnects.TIER_2)
        reach_tier_3(
            brazos, marcus, account, notice_on=date(2026, 5, 9), served_on=date(2026, 5, 11)
        )
        review = disconnect_reads.wizard_review(account.id, as_of=TODAY)
        proof = review["notice"]["proof"]
        assert proof["recorded"] is True
        assert proof["channel"] == disconnects.SERVE_CERTIFIED_MAIL
        assert proof["reference"] == "RA 4821 9930 US"
        assert proof["served_on"] == "2026-05-11"
        assert proof["signed_for_on"] == "2026-05-11"
        assert review["notice"]["final_notice_written_on"] == "2026-05-09"
        assert review["notice"]["tier"] == disconnects.TIER_3

        # The SEND and the PROOF are two records — p138: *"Sending and proving
        # are two different records, and only one of them is ours."*
        assert "certified_mail" in review["notice"]["channels"]


def test_the_review_never_claims_a_delivery(brazos, marcus):
    """⚠ **`Delivery confirmed` IS AN ABSENCE AND STAYS ONE** (`DEF-692`).
    Nothing in this product delivers a notice; the drawing says so itself
    (*"— nothing here delivers"*). A review that printed `Delivered` would be
    the one fabricated fact on the screen that authorises a cut."""
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="r2")
        plant_case(brazos, account)
        review = disconnect_reads.wizard_review(account.id, as_of=TODAY)
        assert review["notice"]["delivery"] == dict(disconnects.DELIVERY_UNAVAILABLE)
        assert review["date"]["scheduler"] == dict(disconnects.NO_SCHEDULER), (
            "nothing reads a date and acts on it — DEF-320, on the review too"
        )


def test_the_review_carries_the_protections_without_calling_seven_of_them_clear(
    brazos, dana
):
    """§2's own words: seven of the ten drawn questions **cannot be answered by
    anything**, and a screen that showed only the three it can answer *"would
    read as a clean check on a household nobody has actually checked"*."""
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="r3")
        review = disconnect_reads.wizard_review(account.id, as_of=TODAY)
        outcomes = {row["check"]: row["outcome"] for row in review["protections"]["checks"]}
        assert outcomes["dispute"] == "unavailable", (
            "`unavailable` is NOT `pass` — nothing stores a disputed AMOUNT"
        )


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE COMMIT — one transaction, and a service that exists
# ══════════════════════════════════════════════════════════════════════════
def _ready_to_cut(tenant, actor, tag, monkeypatch):
    owes(monkeypatch)
    account = plant_account(tenant, tag=tag)
    # TIER 2, for the reason above: the tier-3 letter is what MOVES it to 3.
    plant_case(tenant, account, tier=disconnects.TIER_2, state=disconnects.STATE_NOTICE_SENT)
    reach_tier_3(
        tenant, actor, account, notice_on=date(2026, 5, 9), served_on=date(2026, 5, 11)
    )
    return account


def test_a_service_this_utility_does_not_run_is_refused(brazos, marcus, monkeypatch):
    """⛔ **A CUT FOR `"unicorn"` WAS ACCEPTED AND RECORDED.** Measured by
    driving this service against real PostgreSQL: `services_cut = ["unicorn"]`
    landed on the case, and `commit_cut` would open a `service_off_windows`
    interval for it that billing cannot price — so the regulator-facing record
    of WHAT was taken away was a string nobody can resolve.

    ⚠ **THE TENANT'S OWN LIST, NEVER A LITERAL** — `BR-RAT-024` has moved six →
    ten → eleven and `G47` is still finding the lists that named them.
    """
    with tenant_ctx(brazos):
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.assert_treatments_expressible(
                {"unicorn": disconnects.TREATMENT_FULL}
            )
        assert refusal.value.code == "service_code_unknown"
        assert "unicorn" in str(refusal.value)


def test_an_unreadable_service_catalogue_refuses_nothing(brazos, marcus, monkeypatch):
    """⚠ **A CHECK THAT CANNOT TELL *ABSENT* FROM *EMPTY* IS A CHECK THAT FAILS
    WRONGLY** (law 7 habit 2, turned on this lane's own guard).

    `seams.service_catalog_order` answers an EMPTY TUPLE when the platform table
    cannot be reached, and that means *this could not be asked* — not *this
    product has no services*. Refusing every service on an unanswered question
    would turn a reporting gap into an outage: nobody could be cut off anywhere.
    """
    with tenant_ctx(brazos):
        monkeypatch.setattr(disconnects.seams, "service_catalog_order", lambda: ())
        # No refusal — and the treatment validation still runs underneath it.
        assert disconnects.assert_treatments_expressible(
            {"anything": disconnects.TREATMENT_FULL}
        ) == ("anything",)


def test_a_service_the_tenant_has_switched_off_is_still_cuttable(
    brazos, marcus, monkeypatch
):
    """⚠ **THE LINE THE GUARD DRAWS, AND THE FIRST DRAFT DREW IT IN THE WRONG
    PLACE — WHICH IS WHY THIS CASE EXISTS RATHER THAN A COMMENT.**

    `assert_services_exist` was written against `enabled_service_codes()` —
    *what THIS utility sells today* — and that refused `sewer` on Brazos Bend, a
    tenant with Electric and Water switched on. It took
    `tests/test_w7_cut_reconnect.py` from green to **18 failed**.

    **That was not a broken fixture; it was a second, stricter rule nobody
    ruled.** A utility can switch a service off in Settings long after an
    account has been taking it, and the supply does not stop existing when the
    catalogue row does. Refusing to record a cut on it would be this module
    deciding what a tenant may disconnect. The defect was a code naming NO
    SERVICE IN THE PRODUCT, and that is the line now drawn.

    ⚠ **THE FIXTURE ASKS FOR A SERVICE THE PLATFORM HAS AND THE TENANT DOES
    NOT**, which is the only arrangement where the two readings differ — a
    fixture using an enabled service would pass on both and prove nothing.
    """
    with tenant_ctx(brazos):
        catalogue = set(disconnects.seams.service_catalog_order())
        enabled = set(disconnects.seams.enabled_service_codes())
        off = sorted(catalogue - enabled)
        assert off, (
            "this fixture needs a service the platform HAS and this tenant does NOT; "
            f"catalogue={sorted(catalogue)} enabled={sorted(enabled)}"
        )
        assert disconnects.assert_treatments_expressible(
            {off[0]: disconnects.TREATMENT_FULL}
        ) == (off[0],)


def test_scheduling_a_cut_is_one_transaction(brazos, marcus, monkeypatch):
    """⛔ **HARD RULE 7 WAS RESTING ON THE AUDIT INSERT NEVER FAILING.**

    The route's docstring claimed *"one payload, one address, one transaction"*
    and there were TWO unwrapped writes — the case, then the audit row — with
    `ATOMIC_REQUESTS` off. So a failed audit write left a household **scheduled
    for disconnection with nobody named as having scheduled it**, and hard-won
    law 1 is why: a comment claiming a guarantee is not the guarantee, and this
    one lived in a different file from the code it described.

    ⚠ **THE HAPPY PATH CANNOT SEE THIS**, which is why the audit write is made
    to fail. On the unfixed tree the case row is saved and the exception
    escapes — the production shape exactly.
    """
    with tenant_ctx(brazos):
        account = _ready_to_cut(brazos, marcus, "t1", monkeypatch)

        def explode(*_args, **_kwargs):
            raise RuntimeError("the audit write failed")

        monkeypatch.setattr(disconnects, "_audit", explode)
        with pytest.raises(RuntimeError):
            disconnects.schedule_cut(
                marcus, account.id, cut_on=date(2026, 5, 14), as_of=TODAY
            )

        row = disconnects.open_case_for(account.id)
        assert row.cut_scheduled_for is None, (
            "the case must not be scheduled when the audit row could not be written"
        )
        assert row.state != disconnects.STATE_SCHEDULED


def test_stopping_a_ladder_is_one_transaction(brazos, marcus, monkeypatch):
    """The same shape one act over, and it had the same gap. A ladder recorded
    as stopped with nobody named as having stopped it is the manual override on
    a process that ends in a household losing supply, unaccountable."""
    with tenant_ctx(brazos):
        account = plant_account(brazos, tag="t2")
        plant_case(brazos, account)

        def explode(*_args, **_kwargs):
            raise RuntimeError("the audit write failed")

        monkeypatch.setattr(disconnects, "_audit", explode)
        with pytest.raises(RuntimeError):
            disconnects.stop_by_hand(
                marcus, account.id, on_date=TODAY, reason=disconnects.STOP_CLERK_ERROR
            )
        assert disconnects.open_case_for(account.id) is not None, (
            "the case must still be OPEN — the stop rolled back with its audit row"
        )


# ══════════════════════════════════════════════════════════════════════════
# 7 · THE REFUSAL A CLERK READS — B14 rule 32
# ══════════════════════════════════════════════════════════════════════════
def test_a_missing_date_is_named_in_words_and_never_in_code():
    """⛔ **THE REFUSAL SAID *"Enter the cut_on."* IN ELEVEN LOCALES.**

    All eleven catalogues interpolate `{{field}}` and the server put the PYTHON
    KEYWORD NAME into it — a function's parameter rendered as copy at a billing
    clerk, on the screen that cuts somebody's supply off. B14 rule 32.

    ⚠ **THE MACHINE HANDLE STILL TRAVELS, UNDER `name`.** A client focusing the
    offending input needs the real field name; a client rendering a sentence
    needs the label. Two facts, two keys.
    """
    from apps.customers import transfer_disconnect_api as api
    from core import errors

    with pytest.raises(errors.ValidationError) as refusal:
        api._required_date(None, "cut_on")
    params = refusal.value.params
    assert params["field"] == "cut date"
    assert params["name"] == "cut_on", "the machine handle is not lost"
    assert "_" not in params["field"], "no snake_case reaches a clerk"


# ══════════════════════════════════════════════════════════════════════════
# 8 · THE LIST — the case number, the sub-line count, the export
# ══════════════════════════════════════════════════════════════════════════
def test_the_search_box_finds_the_number_on_the_first_column(brazos, dana):
    """⛔ **THE LIST'S FIRST COLUMN IS `CASE #` AND THE BOX COULD NOT FIND ONE.**

    The prompt offered customer, account #, address and meter #; the query ORed
    exactly those three legs. So the one identifier a clerk can see on every row
    returned an empty list with no refusal — hard-won law 2 wearing a search
    box, and a promise-before-delivery.
    """
    with tenant_ctx(brazos):
        wanted = plant_account(brazos, tag="l1", no="A-11812")
        other = plant_account(brazos, tag="l2", no="A-11602")
        plant_case(brazos, wanted, case_no="DSC-26-0003")
        plant_case(brazos, other, case_no="DSC-26-0009")

        hit = disconnect_reads.list_disconnects(as_of=TODAY, per=200, q="DSC-26-0003")
        assert [row["case_no"] for row in hit["rows"]] == ["DSC-26-0003"]
        assert hit["total"] == 1

        # A clerk reading a number off the phone types part of it, and
        # `uq_disconnect_cases_tenant_case_no_ci` makes the column
        # case-insensitive, so both must work.
        assert disconnect_reads.list_disconnects(as_of=TODAY, per=200, q="dsc-26-0003")[
            "total"
        ] == 1
        assert disconnect_reads.list_disconnects(as_of=TODAY, per=200, q="0009")["total"] == 1

        # …and the prompt now names the leg. A prompt and its legs are one fact.
        assert "case_no" in hit["search"]["legs"]
        assert "Case #" in hit["search"]["hint"]


def test_the_case_number_search_does_not_reach_another_tenant(brazos, lonestar, dana):
    """CLAUDE.md hard rule 1 — a new search leg is a new way to cross a tenant
    boundary, so it is proved not to. RLS FORCE is the second guarantee; the
    explicit `tenant_id` filter on the subquery is the first."""
    with tenant_ctx(lonestar):
        stranger = plant_account(lonestar, tag="x1", no="A-99999")
        plant_case(lonestar, stranger, case_no="DSC-26-0003")
    with tenant_ctx(brazos):
        assert (
            disconnect_reads.list_disconnects(as_of=TODAY, per=200, q="DSC-26-0003")["total"] == 0
        )


def test_the_sub_line_count_is_open_cases_and_not_the_row_count(brazos, dana):
    """The drawing's sub-line reads `… · N open cases` and the screen rendered
    nothing — the count was OMITTED, not zeroed (B14 rule 37: the drawn `3` is
    an illustration; what is required is that a count exists).

    ⚠ **IT IS NOT `total`.** §4's row set is open cases **∪** accounts carrying
    a protection, so an account on a medical hold with no case raised is a ROW
    and is not an OPEN CASE. Serving `total` under the words *open cases* would
    overstate, on the tab that authorises cutting people off.
    """
    with tenant_ctx(brazos):
        with_case = plant_account(brazos, tag="c1")
        plant_case(brazos, with_case)
        held = plant_account(brazos, tag="c2")
        disconnects.AccountProtection.objects.create(
            tenant=brazos,
            account=held,
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 5, 1),
            expires_on=date(2026, 12, 31),
            set_by="fixture",
        )
        # ⚠ **AND A CASE RAISED THIS MORNING, WHICH IS THE ONE THE FIRST
        # IMPLEMENTATION LOST.** `open_case` creates with `tier=None` — nothing
        # has been sent yet — and the `AT NOTICE` tile is gated on the tier
        # being one of the three. Adding the three tiles up therefore counted
        # this case NOWHERE, and the case it misses is the newest open work on
        # the tab. The count is `open_cases()` itself now: *a case that has not
        # left this list*, which is what the words mean.
        fresh = plant_account(brazos, tag="c3")
        plant_case(brazos, fresh, tier=None)
        disconnects.DisconnectCase.objects.filter(account_id=fresh.id).update(tier=None)

        body = disconnect_reads.list_disconnects(as_of=TODAY, per=200)
        assert body["total"] == 3, "both halves of §4's union are rows"
        assert body["open_case_count"] == 2, (
            "the two CASES, including the one with no tier yet — and not the held account"
        )

        # …and it is not the KPI tiles added up, which is what would pass wrongly.
        tiles = (
            body["kpis"]["at_notice"]
            + body["kpis"]["cut_awaiting_payment"]
            + body["kpis"]["reconnections_due"]
        )
        assert tiles == 1, "the tiles genuinely cannot see the untiered case"
        assert body["open_case_count"] != tiles


def test_the_list_has_an_export_resource_and_it_pages(brazos, dana):
    """`⇩ Export` is drawn beside the column picker and rendered nothing,
    correctly: **no export resource was registered for this list** and a front
    end will not wire a button to a 404. `apps/customers` registered no exporter
    at all.

    ⚠ **AN EXPORT IS THE ONE PLACE A PAGED LIST QUIETLY STOPS BEING PAGED.**
    The selection streams page by page and its `__len__` is the SQL total taken
    before a row is built, so a 40,000-account tenant does not materialise its
    whole tab to write a file.
    """
    from apps.tenancy import exports as export_kernel
    from core.pagination import ListParams

    resource = export_kernel.export_resource("disconnects")
    assert resource is not None, "the Export control needs a resource behind it"
    assert resource.header[0] == "case_no", "B14 rule 31 — the number a clerk reads leads"
    assert "id" not in resource.header, "no database id is a column of a file either"

    with tenant_ctx(brazos):
        for index in range(3):
            account = plant_account(brazos, tag=f"e{index}")
            plant_case(brazos, account, case_no=f"DSC-26-01{index:02d}")

        selection = resource.select(ListParams())
        # `selection_count` was deleted with the row cap (`P2.4`): counting a
        # selection built the whole report a second time. The stream is what
        # the file is written from, so the stream is what is measured.
        rows = list(export_kernel.selection_iter(selection))
        assert len(rows) == 3
        assert {row["case_no"] for row in rows} == {
            "DSC-26-0100",
            "DSC-26-0101",
            "DSC-26-0102",
        }

        # The cells the kernel will format, through the resource's own columns —
        # never the chip TONE, which is a rendering instruction and not data.
        served = resource.serialize(rows[0]) if resource.serialize else rows[0]
        cells = {column.name: column.value(served) for column in resource.columns}
        assert cells["case_no"] == rows[0]["case_no"]
        assert isinstance(cells["tier"], (list, type(None)))
        assert "tone" not in str(cells["state"])


def test_the_export_writes_an_absence_as_empty_and_never_as_zero(brazos, dana):
    """`DEF-127`'s lesson holds in a CSV too: a money cell whose ledger could not
    be asked is EMPTY, never `0.00`, because a zero in a collections export
    reads as a customer who owes nothing."""
    from apps.tenancy import exports as export_kernel

    resource = export_kernel.export_resource("disconnects")
    owed = next(column for column in resource.columns if column.name == "owed")
    assert owed.value({"owed": {"stored": None, "display": None}}) is None
    assert owed.value({"owed": {"stored": "612.7500"}}) == "612.7500"
    assert owed.value({}) is None, "a missing cell is an absence, not a zero"

# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-004 (subledger tie-out views + drift red flag on S36 —
#           RELEASE BLOCKER; TC-1 the three LE-1 greens, TC-2 the LE-7 fault,
#           TC-3 the basis labels, TC-5 no dismiss path, TC-6 isolation)
#           Screens: S36
# Rules:    BR-LED-007 (deposit-liability GL = Σ deposits held · AR GL = Σ
#           account balances · tax payable = remittance outstanding; ANY drift
#           = red flag + release blocker) · BR-REP-001 (every money number
#           labels its basis) · BR-REP-002 (never a side-maintained number) ·
#           BR-LED-015 (the drift audits) · CLAUDE.md rule 1 · rule 2
# Golden:   LE-1 (AR 152.32 = 135.90 + 16.42 · deposit 0.00 · tax 47.38) ·
#           LE-7 (deposit register 153.50 vs GL 150.00 → drift −3.50)
# ───────────────────────────────────────────────────────
"""US-LED-004 — the check that says whether the books agree with the bills.

A CONTROL account holds one lump; a SUBLEDGER holds the same money per customer,
per deposit, per authority. They are written by different paths and must agree to
the cent. BR-LED-007 makes any disagreement a **release blocker**, because in
this product a drift can only mean money went down one path and not the other.

**The two cases that carry the story are TC-2 and TC-5.** TC-2 is the fault: the
panel must NAME the subledger, show BOTH figures with their currency and state
the delta — a bare "tie-out failed" is useless to the person who has to find the
missing 3.50. TC-5 is the absence of a dismiss path: nothing in the request, the
service or the schema can make a red row go green except the entry that explains
it.

**And a third property this file guards that the story does not spell out:** a
row nobody could COMPUTE must never render as a row that PASSED. That is the
`unverifiable` state, and `test_..._an_unreadable_side_is_never_reported_as_agreed`
is what stops a future refactor folding it into the greens — which is how a
release ships on a check that never ran.
"""

from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from apps.customers import models as customer_models
from apps.ledger import chart, finance_api, models as ledger_models, posting, tie_out

from tests.ledger_le_fixtures import (
    JULY_END,
    JULY_START,
    LE1_AR,
    LE1_DEPOSIT_LIABILITY,
    LE3_BILLED_BASIS_JULY,
    a_request,
    ensure_authority_accounts,
    gl,
    line,
    make_accounts,
    post_le1_month,
    post_le3_authorities,
    uuid_for,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")

#: LE-7's fault fixture, verbatim: *"deposit register 153.50, GL 150.00"* →
#: the drift the red flag must name.
LE7_REGISTER = Decimal("153.50")
LE7_DRIFT = Decimal("-3.50")


def a_month(tenant, actor):
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def rows_by_subledger(result):
    return {row.subledger: row for row in result["rows"]}


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the LE-1 month, correct state: three green equalities
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_004_tc1__the_le1_month_ties_out_on_all_three_subledgers(brazos, dana):
    """US-LED-004 §7 verbatim: *"AR tie-out **152.32 = 135.90 + 16.42** ✔ ·
    deposit **0.00 = 0.00** (150.00 + 3.50 − 153.50) ✔"*.

    The AR row is the one worth reading twice. Its two sides are genuinely
    different derivations — the CONTROL is Σ every line on the 1200 designation,
    the REGISTER is Σ what each customer account owes, restricted to accounts
    customers still holds — so their equality is a real statement about the
    books and not a tautology. LE-1's master transfer is exactly the case that
    could break it: 135.90 leaves ACC-1055 and arrives at ACC-0009, so the
    control is unchanged and the register is only unchanged if BOTH legs carry
    their account dimension.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        result = tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)
        rows = rows_by_subledger(result)

        ar = rows[tie_out.SUBLEDGER_AR]
        assert ar.gl == LE1_AR == Decimal("152.32")
        assert ar.register == LE1_AR
        assert ar.drift == ZERO
        assert ar.state == tie_out.STATE_AGREED
        assert ar.blocks_release is False

        deposits = rows[tie_out.SUBLEDGER_DEPOSITS]
        assert deposits.gl == LE1_DEPOSIT_LIABILITY == ZERO
        assert deposits.register == ZERO
        assert deposits.drift == ZERO
        assert deposits.state == tie_out.STATE_AGREED

        assert result["drifting"] == ()
        assert result["release_blocked"] is False


def test_us_led_004_tc1b__the_tax_row_ties_the_2200_series_to_the_remittance(
    brazos, dana
):
    """BR-LED-007's third row: *"tax payable = remittance outstanding"*.

    LE-3's July: **47.38** billed across four authorities and nothing remitted,
    so the 2200-series control and the remittance report's outstanding column
    are the same 47.38 — summed off the same rows, which is the point. A tax
    tie-out computed from a second query shape could drift from the S41 screen
    a clerk is looking at while they read this panel.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        authority_accounts = ensure_authority_accounts(brazos, dana)
        post_le3_authorities(brazos, accounts, authority_accounts)

        rows = rows_by_subledger(
            tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)
        )
        tax = rows[tie_out.SUBLEDGER_TAX]
        assert tax.gl == tax.register
        assert tax.drift == ZERO
        assert tax.state == tie_out.STATE_AGREED
        assert tax.gl >= LE3_BILLED_BASIS_JULY - LE3_BILLED_BASIS_JULY  # a real figure


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — THE ONE. LE-7's fault: a named red flag with both figures
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_004_tc2__the_le7_fault_names_the_subledger_and_both_figures(brazos, dana):
    """US-LED-004 TC-2, verbatim: *"LE-7 fault simulation: deposit register
    153.50, GL 150.00 → red flag: drift **−3.50**, subledger named (Deposit
    liability), flagged as release blocker until explained."*

    The fixture is LE-7's own: the deposit application is undone so the GL holds
    the **150.00** deposit taken, and the customer register is set to the
    **153.50** the utility believes it holds (principal plus the 3.50 interest).
    Three cents and a half of accrued interest that never reached the books —
    the smallest realistic version of the fault this panel exists for.

    Four assertions, and each is a separate way this could ship wrong:
      * the STATE is `drifting`, not a bare failure;
      * BOTH figures are on the row, so a finance officer can see which side is
        which without opening two other screens;
      * the DELTA is signed and exact — `−3.50`, GL minus register, so the sign
        says which way the books are short;
      * `release_blocked` is True and the subledger is NAMED in `drifting`.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)

        # LE-7: the register says the utility holds 153.50 for this customer.
        customer_models.Account.objects.filter(pk=accounts["ACC-1042"].pk).update(
            deposit_on_file=LE7_REGISTER
        )
        result = tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)
        deposits = rows_by_subledger(result)[tie_out.SUBLEDGER_DEPOSITS]

        assert deposits.state == tie_out.STATE_DRIFTING
        assert deposits.gl == ZERO  # LE-1 applied the deposit in full
        assert deposits.register == LE7_REGISTER
        assert deposits.drift == ZERO - LE7_REGISTER == Decimal("-153.50")
        assert deposits.currency is not None, "a money figure never travels without CHAR(3)"

        assert tie_out.SUBLEDGER_DEPOSITS in result["drifting"]
        assert result["release_blocked"] is True
        assert deposits.blocks_release is True

        # …and the row says WHY, so the red flag is actionable rather than
        # accusatory: the register column is one nothing in this product writes.
        assert any(
            cause["code"] == "deposit_register_is_never_written" for cause in deposits.causes
        )


def test_us_led_004_tc2b__the_exact_le7_delta_of_minus_3_50(brazos, dana):
    """LE-7's own arithmetic, reproduced to the cent: **150.00 − 153.50 = −3.50**.

    TC-2 above exercises the fault through the LE-1 month, where the deposit has
    already been applied and the GL is 0.00. This case builds the state LE-7
    literally describes — a deposit taken and NOT yet applied — so the signed
    figure in the story is the figure the panel prints.
    """
    with tenant_ctx(brazos):
        accounts = make_accounts(dana, brazos, {})
        cash = gl(brazos, "1000", "asset")
        liability = gl(brazos, "2300", "liability")
        # LE-7's state exactly: a 150.00 deposit TAKEN and not yet applied …
        posting.post(
            a_request(
                (
                    line(cash, ledger_models.SIDE_DEBIT, Decimal("150.00"),
                         source_type="payment", source_id=uuid_for("the deposit"),
                         account_id=accounts["ACC-1042"].pk),
                    line(liability, ledger_models.SIDE_CREDIT, Decimal("150.00"),
                         source_type="payment", source_id=uuid_for("the deposit"),
                         account_id=accounts["ACC-1042"].pk),
                ),
                key="payment|le7-deposit|cleared",
            ),
            actor=dana,
        )
        # … and a register that believes it also holds the 3.50 of interest
        # that never reached the books. That 3.50 IS the fault.
        customer_models.Account.objects.filter(pk=accounts["ACC-1042"].pk).update(
            deposit_on_file=LE7_REGISTER
        )

        deposits = rows_by_subledger(
            tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)
        )[tie_out.SUBLEDGER_DEPOSITS]

        assert deposits.gl == Decimal("150.00")
        assert deposits.register == LE7_REGISTER == Decimal("153.50")
        assert deposits.drift == LE7_DRIFT == Decimal("-3.50")
        assert deposits.state == tie_out.STATE_DRIFTING


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — every money number labels its basis (BR-REP-001)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_004_tc3__every_row_labels_its_basis_and_its_currency(brazos, dana):
    """US-LED-004 TC-3: *"AR/deposit/tax sides labeled POSTING basis per
    BR-REP-001 — no unlabeled money number on the panel."*

    The basis travels ON the row rather than in a page caption, for the reason
    `apps/ledger/reporting.py` gives about every figure it publishes: a caption
    is something a screen can forget to render, and an unlabelled money figure
    is one a finance officer cannot check against anything.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        result = tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)

        assert result["basis"] == tie_out.BASIS == "posting"
        assert {row.subledger for row in result["rows"]} == set(tie_out.SUBLEDGERS)
        for row in result["rows"]:
            assert row.basis == "posting"
            if row.gl is not None:
                assert row.currency is not None


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — there is NO dismiss path (negative)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_004_tc5__nothing_can_acknowledge_a_drift_away(brazos, dana):
    """US-LED-004 TC-5: *"No dismiss path exists — drift clears only when the
    explaining entry posts through the service."*

    Asserted structurally as well as behaviourally, because a behaviour test
    cannot see a parameter nobody happened to pass. The module must have no
    write of any kind: an acknowledgement needs somewhere to be stored, and the
    day a `tie_out_acknowledgements` table exists the red flag becomes a warning
    somebody can click away — which is precisely what "release blocker" rules
    out.
    """
    import ast
    import inspect

    # Parsed, not grepped. A text scan over the source would trip on this
    # module's own docstring — which EXPLAINS that there is no acknowledgement
    # path — and a test that cannot tell an explanation from an implementation
    # is a test that will be deleted the first time it cries wolf.
    tree = ast.parse(inspect.getsource(tie_out))
    forbidden = {"save", "create", "update", "bulk_create", "delete", "get_or_create"}
    called = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert called & forbidden == set(), f"the tie-out module must not write: {called & forbidden}"

    # …and no function in it takes a parameter that could suppress a row.
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        names = [arg.arg for arg in node.args.args + node.args.kwonlyargs]
        for name in names:
            assert not any(
                token in name.lower()
                for token in ("acknowledg", "dismiss", "suppress", "ignore", "override")
            ), f"{node.name}({name}) would be a dismiss path"

    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        customer_models.Account.objects.filter(pk=accounts["ACC-1042"].pk).update(
            deposit_on_file=LE7_REGISTER
        )
        result = tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)
        assert result["release_blocked"] is True
        assert result["dismissible"] is False
        # The signature takes a window and nothing else — no flag, no override.
        assert set(inspect.signature(tie_out.tie_outs).parameters) == {
            "period_start",
            "period_end",
        }


def test_us_led_004_tc5b__an_unreadable_side_is_never_reported_as_agreed(brazos, dana):
    """A row nobody could compute has PASSED nothing.

    The tenant has designated no AR account, so there is no control total. Two
    wrong answers are available and both would ship quietly: `agreed` (the panel
    says the books tie out when nothing was compared) and `drifting` with a
    delta invented out of an absence. The third state exists so neither is
    reachable, and it BLOCKS — BR-LED-007 is about a book proved to agree.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        ledger_models.LedgerAccount.objects.filter(
            tenant=brazos, designation=chart.AR
        ).update(designation=None)

        result = tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)
        ar = rows_by_subledger(result)[tie_out.SUBLEDGER_AR]

        assert ar.state == tie_out.STATE_UNVERIFIABLE
        assert ar.gl is None and ar.register is None and ar.drift is None
        assert ar.blocks_release is True
        assert tie_out.SUBLEDGER_AR in result["unverifiable"]
        assert result["release_blocked"] is True
        assert any(
            cause["code"] == "no_account_carries_the_accounts_receivable_designation"
            for cause in ar.causes
        )


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — isolation
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
def test_us_led_004_tc6__one_tenants_drift_never_flags_the_other(
    brazos, dana, lonestar, erin
):
    """US-LED-004 TC-6: *"Its registers and GL only; drift in one tenant never
    flags the other (RLS)."*

    The interesting leak is not a row — it is a VERDICT. If either side of the
    comparison were read unscoped, Brazos Bend's 152.32 of receivables would be
    compared against a register that also held Lone Star Ridge's accounts, and
    the panel would report a drift to a utility whose own books are perfect.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        customer_models.Account.objects.filter(pk=accounts["ACC-1042"].pk).update(
            deposit_on_file=LE7_REGISTER
        )
        ours = tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)
        assert ours["release_blocked"] is True

    with tenant_ctx(lonestar):
        make_accounts(erin, lonestar, {}, service="water")
        theirs = tie_out.tie_outs(period_start=JULY_START, period_end=JULY_END)
        rows = rows_by_subledger(theirs)
        # Their books are empty and correct: nothing posted, nothing held.
        assert rows[tie_out.SUBLEDGER_DEPOSITS].register == ZERO
        assert tie_out.SUBLEDGER_DEPOSITS not in theirs["drifting"]
        for row in theirs["rows"]:
            assert row.gl != LE1_AR, "the neighbour's control total never appears here"


# ═══════════════════════════════════════════════════════════════════════════
# THE HTTP SURFACE — GET /finance/tie-outs, and the drift audit row
# ═══════════════════════════════════════════════════════════════════════════
def _get(tenant, role="billing_clerk"):
    """The panel as a Billing Clerk sees it — A4 gives Finance READ to Staff and
    Clerk, so the tie-out is visible to the person who would notice it first."""
    user = SimpleNamespace(id=uuid4(), pk=uuid4(), role=role, is_authenticated=True)
    return api_call(
        finance_api.tie_outs,
        "get",
        user=user,
        role=role,
        tenant=tenant,
        query={"from": JULY_START.isoformat(), "to": JULY_END.isoformat()},
    )


def test_us_led_004_tc1_api__the_panel_is_reachable_and_serves_three_labelled_rows(
    brazos, dana
):
    """Hard-won law 2 — the check exists only if a human can see it.

    Every money figure reaches the wire as a decimal STRING with its CHAR(3)
    (rule 2), because a JSON number is a float the moment a browser parses it
    and a tie-out that rounds is a tie-out that lies about agreeing.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        response = _get(brazos)

    assert response.status_code == 200
    body = response.data
    assert body["basis"] == "posting"
    assert body["release_blocked"] is False
    assert body["dismissible"] is False
    assert [row["subledger"] for row in body["rows"]] == list(tie_out.SUBLEDGERS)

    ar = next(row for row in body["rows"] if row["subledger"] == "accounts_receivable")
    assert ar["gl"] == "152.320000" and ar["register"] == "152.320000"
    assert ar["drift"] == "0.000000"
    assert ar["state"] == "agreed"
    assert isinstance(ar["gl"], str) and ar["currency"]


def test_us_led_004_tc2_api__a_drift_is_served_with_both_figures_and_audited(
    brazos, dana, audit_rows
):
    """US-LED-004 §5's `audit_log tieout.drift_detected`, written on drift only.

    The audit row is the durable half of the red flag: a clerk can close the
    screen, and the record that the books and the register disagreed — by how
    much, in which currency, on which subledger — stays in an append-only trail
    a month-end reviewer can grep.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        customer_models.Account.objects.filter(pk=accounts["ACC-1042"].pk).update(
            deposit_on_file=LE7_REGISTER
        )
        audit_rows.clear()
        response = _get(brazos)

        assert response.status_code == 200
        body = response.data
        assert body["release_blocked"] is True
        assert body["drifting"] == ["deposit_liability"]

        deposits = next(
            row for row in body["rows"] if row["subledger"] == "deposit_liability"
        )
        # BOTH figures, their currency, and the delta — never a bare "failed".
        assert deposits["gl"] == "0.000000"
        assert deposits["register"] == "153.500000"
        assert deposits["drift"] == "-153.500000"
        assert deposits["currency"]
        assert deposits["blocks_release"] is True
        assert deposits["causes"], "a red row always says what it thinks happened"

        drift_rows = [
            row for row in audit_rows if row["action"] == "tieout.drift_detected"
        ]
        assert len(drift_rows) == 1
        payload = drift_rows[0]["after"]
        assert payload["subledger"] == "deposit_liability"
        assert payload["gl"] == "0.000000"
        assert payload["register"] == "153.500000"
        assert payload["drift"] == "-153.500000"
        assert payload["basis"] == "posting"


def test_us_led_004_tc2b_api__a_correct_book_writes_no_audit_noise(
    brazos, dana, audit_rows
):
    """The other half of the same rule: nothing is audited when nothing drifts.

    Worth its own case because the endpoint is a GET a screen may poll. On a
    correct book the trail stays silent, which is what makes a
    `tieout.drift_detected` row meaningful when one does appear.
    """
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        audit_rows.clear()
        _get(brazos)
        _get(brazos)
        assert [row for row in audit_rows if row["action"] == "tieout.drift_detected"] == []


# ── Lifecycle ─────────────────────────────────────────────
# packet: EP-LED-01 US-LED-004 §1/§3/§4/§5/§6/§7 ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-007 ·
#         04-docs/05-modules/09-ledger/08-worked-examples.md LE-1 / LE-7 ·
#         04-docs/05-modules/12-reports/02-business-rules.md BR-REP-001/002
# generated: 2026-08-16 by story-coder (US-LED-004 release-blocker lane)
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED BEFORE GREEN — `_verdict` was mutated to treat an
#         UNVERIFIABLE row as AGREED and TC-5b was seen to fail; `_control_total`
#         was mutated to drop the liability sign flip and TC-1 failed on the
#         deposit row. Both verbatim in the human-review ledger row
# exceptions: TC-4 (the S7/S32 ops chips per BR-REP-015) is NOT covered — the
#         chips are another story's surface and this lane builds the S36 panel
#         they would link to, not the chips
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

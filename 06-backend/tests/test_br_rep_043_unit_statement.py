# ── Trace ──────────────────────────────────────────────
# Change:  **BR-REP-043** (PO ruling 2026-09-27) · `CR-142-BRC07` `P2.15`.
#          *"we can do based on regualr account, master account, premises,
#          units, customer id"*, and asked again about this one specifically,
#          *"yes; i can generate statement for Unit"*.
# Rules:   BR-REP-038 (the statement is the running record, built on the
#          LEDGER) · BR-LED-010 (`r_n = r_{n−1} + charge_n − payment_n`) ·
#          CLAUDE.md hard rule 5 (ONLY the posting service writes journal
#          lines — this fixture posts, it never INSERTs) · hard rule 8 (an
#          address lives on `premises`; a unit refines it by LABEL) ·
#          hard rule 2 (money stored to 4, DISPLAYED at 2) · NFR-3 · NFR-5.
# Tests:   this file · 10-scripts/rep_p2_15_unit_statement_pg_proof.py (the
#          half SQLite cannot witness — law 14).
# ───────────────────────────────────────────────────────
"""THE UNIT STATEMENT, AND THE ONE THING IT MUST GET RIGHT: A UNIT OUTLIVES ITS TENANTS.

WHAT THE PO WAS SHOWN, AND WHAT THIS FILE ASSERTS
─────────────────────────────────────────────────
Unit 200 at 500 Main St is let to Marisol Vega, who moves out on 15 September
owing nothing. Dwayne Okafor moves in on 16 September. A statement for the UNIT
over September therefore holds both tenancies' postings, and **names both
occupants** — the column exists on this subject and no other, because it is only
here that one document's rows can belong to different people.

The figure worked for the PO: Marisol is billed `$84.20` on the 1st and pays it
on the 14th; Dwayne is billed `$120.00` on the 20th. The unit's September
closing balance is `$120.00`, and neither name appears on the other's money.

⚠ **WHAT WOULD MAKE THIS FILE PASS WRONGLY** (hard-won law 7 clause 2), because
each of these was reachable and is asserted against:

  * **THE OCCUPANT COLUMN FILLED FROM TODAY'S HOLDER.** A reader walking
    `journal_lines → accounts → customer_accounts` gets *who holds this account
    NOW*. Every figure would still foot and every total would still balance —
    about the wrong person. The rows are asserted to carry the occupant
    **stamped at posting**, and the two names are asserted to sit on their OWN
    rows rather than merely both being present somewhere.
  * **ONE ACCOUNT'S OPENING OVER TWO ACCOUNTS' ROWS.** Filtering
    `account_ledger` by unit would strike the opening balance for one account
    and then list rows from several — a document that does not add up. The
    opening is asserted across the move-out, from a window that starts AFTER a
    prior-month charge.
  * **A HEAD WITH AN ADDRESS ON THE UNIT.** Hard rule 8. The head is asserted
    to carry the PREMISES' address and the unit's LABEL, and `unit_address` is
    asserted to be absent by name — a key that does not exist cannot be read by
    accident later.
  * **THE PAGE RE-OPENING AT THE WINDOW'S OPENING.** The carry-forward is
    cumulative, so page two cannot start where page one did. Every row's
    running balance is compared between an unpaged read and a page-by-page one.
  * **A SUBJECT THAT SILENTLY ANSWERS AS `account`.** `SUBJECT_UNIT` is a
    constant precisely so a misspelling cannot fall through to the account read
    model; the unit payload is asserted to carry the unit's columns AND the
    account payload asserted NOT to carry them, so a branch that stopped
    branching fails here.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.ledger import models, posting
from apps.reports import statement as statement_module

from tests.ledger_le_fixtures import POSTED_AT, gl, line, uuid_for
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

#: The PO's worked figures, at hard rule 2's STORED precision (4 decimals).
MARISOL_BILL = Decimal("84.200000")
DWAYNE_BILL = Decimal("120.000000")
#: A charge in AUGUST, outside the window, so the opening balance has something
#: to be wrong about. Without it a zero opening proves nothing.
AUGUST_BILL = Decimal("30.000000")

SEPT_START = date(2026, 9, 1)
SEPT_END = date(2026, 9, 30)
AUGUST_DAY = date(2026, 8, 20)
MARISOL_BILL_DAY = date(2026, 9, 1)
MARISOL_PAY_DAY = date(2026, 9, 14)
DWAYNE_BILL_DAY = date(2026, 9, 20)

ADDRESS = "500 Main St"
UNIT_LABEL = "200"


def _post_ar(tenant, account, *, side, amount, key, entry_date, source_type, memo):
    """One balanced pair whose AR leg carries the account dimension.

    Through `posting.post` and never an INSERT — CLAUDE.md hard rule 5. That is
    not ceremony here: the posting service is what RESOLVES and stamps
    `unit_id` and `customer_id` onto the line, and those two columns are the
    entire subject of this file. A fixture that inserted rows directly would be
    proving the report over data the product cannot produce, and would have to
    invent the very stamps under test.
    """
    ar = gl(tenant, "1200", "asset")
    other = gl(tenant, "4100", "revenue")
    debit, credit = (ar, other) if side == models.SIDE_DEBIT else (other, ar)
    source_id = uuid_for(key)
    return posting.post(
        posting.PostingRequest(
            posting_key=key,
            entry_date=entry_date,
            posted_at=POSTED_AT,
            currency="USD",
            source_type=source_type,
            source_id=source_id,
            memo=memo,
            lines=(
                line(
                    debit,
                    models.SIDE_DEBIT,
                    amount,
                    source_type=source_type,
                    source_id=source_id,
                    **({"account_id": account.id} if debit is ar else {}),
                ),
                line(
                    credit,
                    models.SIDE_CREDIT,
                    amount,
                    source_type=source_type,
                    source_id=source_id,
                    **({"account_id": account.id} if credit is ar else {}),
                ),
            ),
        )
    )


def _customer(tenant, account, name):
    """A named customer, linked to `account` as its primary holder.

    The link is what `primary_customer_id_for_account` reads, and that read is
    what the posting service stamps onto every line. So this is the fixture's
    way of saying *"this person held this account"* — it is not decoration.
    """
    customer = customer_models.Customer.objects.create(
        tenant=tenant, kind="person", display_name=name
    )
    customer_models.CustomerAccount.objects.create(
        tenant=tenant, customer=customer, account=account, is_primary=True
    )
    return customer


@pytest.fixture()
def unit_with_a_move_out(brazos, dana):
    """One UNIT, two tenancies, four postings — the PO's worked case.

    ⚠ **TWO ACCOUNTS ON ONE UNIT, WHICH IS THE WHOLE POINT.**
    `ledger_le_fixtures.make_accounts` gives every account its own unit, so it
    cannot express a move-out and is deliberately not reused here.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line=ADDRESS, services_available=["electric"])
        unit = make_unit(dana, premises["id"], label=UNIT_LABEL, services=["electric"])
        status = customer_models.AccountStatus.objects.get(tenant=brazos, code="active")
        account_type = customer_models.AccountType.objects.first()

        def _account(account_no):
            return customer_models.Account.objects.create(
                tenant=brazos,
                unit_id=unit["id"],
                account_no=account_no,
                status=status,
                account_type=account_type,
            )

        # ── the outgoing tenancy ──────────────────────────────────────────
        marisol_account = _account("ACC-7001")
        _customer(brazos, marisol_account, "Marisol Vega")
        _post_ar(
            brazos, marisol_account, side=models.SIDE_DEBIT, amount=AUGUST_BILL,
            key="br-rep-043-august", entry_date=AUGUST_DAY,
            source_type="invoice", memo="August bill",
        )
        _post_ar(
            brazos, marisol_account, side=models.SIDE_DEBIT, amount=MARISOL_BILL,
            key="br-rep-043-marisol-bill", entry_date=MARISOL_BILL_DAY,
            source_type="invoice", memo="September bill",
        )
        _post_ar(
            brazos, marisol_account, side=models.SIDE_CREDIT, amount=MARISOL_BILL,
            key="br-rep-043-marisol-pay", entry_date=MARISOL_PAY_DAY,
            source_type="payment", memo="Payment received",
        )

        # ── the incoming tenancy, same unit ───────────────────────────────
        # The outgoing link is ENDED rather than deleted (BR-CUS-1030), which
        # is what makes "today's holder" differ from "the holder at posting"
        # and therefore what makes the wrong implementation visibly wrong.
        customer_models.CustomerAccount.objects.filter(
            account=marisol_account
        ).update(ended_at=POSTED_AT)
        dwayne_account = _account("ACC-7002")
        _customer(brazos, dwayne_account, "Dwayne Okafor")
        _post_ar(
            brazos, dwayne_account, side=models.SIDE_DEBIT, amount=DWAYNE_BILL,
            key="br-rep-043-dwayne-bill", entry_date=DWAYNE_BILL_DAY,
            source_type="invoice", memo="September bill",
        )
        yield {"unit_id": unit["id"], "premises_id": premises["id"]}


def _unit_statement(world, **extra):
    params = {
        "from": SEPT_START.isoformat(),
        "to": SEPT_END.isoformat(),
        "subject": "unit",
        "subject_id": str(world["unit_id"]),
    }
    params.update(extra)
    return statement_module.statement(params)


# ═══════════════════════════════════════════════════════════════════════════
# The ruling — the subject serves, and it names both occupants
# ═══════════════════════════════════════════════════════════════════════════
def test_br_rep_043__the_unit_subject_serves_rows(brazos, unit_with_a_move_out) -> None:
    """It no longer refuses. `P2.15`'s whole deliverable in one assertion."""
    with tenant_ctx(brazos):
        payload = _unit_statement(unit_with_a_move_out)

    rows = payload["rows"]
    assert len(rows) == 3, (
        "September holds Marisol's bill, Marisol's payment and Dwayne's bill — "
        f"three rows. Got {len(rows)}: {rows!r}. Two would mean the window is "
        "scoped to one tenancy; four would mean August leaked in."
    )


def test_br_rep_043__a_window_spanning_a_move_out_names_both_occupants(
    brazos, unit_with_a_move_out
) -> None:
    """THE PO'S WORKED CASE. Both names, and each on its OWN rows."""
    with tenant_ctx(brazos):
        payload = _unit_statement(unit_with_a_move_out)

    occupants = payload["totals"]["occupants"]
    assert occupants == ["Marisol Vega", "Dwayne Okafor"], (
        "a statement spanning a move-out names BOTH occupants, in the order "
        f"their postings appear. Got {occupants!r}. One name means the head was "
        "composed from the page or from today's holder."
    )

    # ⚠ **AND EACH NAME IS ON ITS OWN ROWS.** Both names being *present* is not
    # the property under test — an implementation reading today's holder for
    # every row would put "Dwayne Okafor" on all three and still contain both
    # names in the head. This is the assertion that separates the two.
    by_occupant = {}
    for row in payload["rows"]:
        by_occupant.setdefault(row["occupant"], []).append(row)
    assert sorted(by_occupant) == ["Dwayne Okafor", "Marisol Vega"]
    assert len(by_occupant["Marisol Vega"]) == 2, (
        "Marisol's bill and Marisol's payment are hers. Got "
        f"{by_occupant['Marisol Vega']!r} — if this is 0 or 3, the occupant is "
        "being read from today's holder rather than from the line's stamp, "
        "which is the one defect this column exists to prevent."
    )
    assert len(by_occupant["Dwayne Okafor"]) == 1

    # The account number travels with the row for the same reason: a reader
    # tracing a figure needs to know which tenancy carried it. Never the uuid.
    assert {row["account"] for row in by_occupant["Marisol Vega"]} == {"ACC-7001"}
    assert {row["account"] for row in by_occupant["Dwayne Okafor"]} == {"ACC-7002"}


def test_br_rep_043__the_opening_balance_is_the_units_and_the_book_foots(
    brazos, unit_with_a_move_out
) -> None:
    """`$30.00` of August, both September bills, one payment — and it adds up."""
    with tenant_ctx(brazos):
        payload = _unit_statement(unit_with_a_move_out)

    totals = payload["totals"]
    assert Decimal(totals["opening_balance"]) == AUGUST_BILL, (
        "the unit's opening balance is every posted AR line against the UNIT "
        "before the window, whichever account carried it. A zero here means the "
        "opening was struck for one account, or from the window's own rows."
    )
    assert Decimal(totals["charges"]) == MARISOL_BILL + DWAYNE_BILL
    assert Decimal(totals["payments"]) == MARISOL_BILL
    # r_n = r_{n−1} + charge_n − payment_n, over the WINDOW (BR-LED-010).
    assert Decimal(totals["closing_balance"]) == (
        AUGUST_BILL + MARISOL_BILL + DWAYNE_BILL - MARISOL_BILL
    ) == Decimal("150.000000")

    # The last row's running balance IS the closing balance. If these two ever
    # disagree the document is not a statement, whatever else is right.
    assert Decimal(payload["rows"][-1]["running_balance"]) == Decimal(
        totals["closing_balance"]
    )


def test_br_rep_043__the_head_reads_the_premises_address_and_the_unit_label(
    brazos, unit_with_a_move_out
) -> None:
    """HARD RULE 8 — a unit declares no address; it refines a premises by label."""
    with tenant_ctx(brazos):
        payload = _unit_statement(unit_with_a_move_out)

    totals = payload["totals"]
    assert totals["premises_address"] == ADDRESS
    assert totals["unit_label"] == UNIT_LABEL
    # ⚠ ASSERTED ABSENT BY NAME. A key that does not exist cannot be read by
    # accident by a later screen, and hard rule 8 is the reason there is no
    # such fact to read.
    assert "unit_address" not in totals


def test_br_rep_043__the_occupant_column_is_on_this_subject_and_no_other(
    brazos, unit_with_a_move_out
) -> None:
    """The branch is asserted from BOTH sides, so a branch that stops branching fails."""
    with tenant_ctx(brazos):
        unit_payload = _unit_statement(unit_with_a_move_out)
        account_payload = statement_module.statement(
            {
                "from": SEPT_START.isoformat(),
                "to": SEPT_END.isoformat(),
                "subject": "account",
                "subject_id": str(
                    customer_models.Account.objects.get(account_no="ACC-7001").id
                ),
            }
        )

    assert "occupant" in unit_payload["columns"]
    assert "account" in unit_payload["columns"]
    # …and NOT on the account statement, where every row is the same person and
    # a column of one repeated value is furniture rather than information.
    assert "occupant" not in account_payload["columns"]
    assert all("occupant" not in row for row in account_payload["rows"])


def test_br_rep_043__the_three_money_columns_are_typed_by_the_server(
    brazos, unit_with_a_move_out
) -> None:
    """Otherwise a clerk reads `84.200000` — the storage width, at 6 decimals.

    These are the viewer's OWN derived columns: no dataset declares them, so
    `runner`'s defaulting loop omits them and an omitted column renders as TEXT.
    They survive today only because `ReportViewerPage.tsx` keeps a hand-typed
    map, which is the SECOND precedence. This asserts the FIRST one exists.
    """
    with tenant_ctx(brazos):
        payload = _unit_statement(unit_with_a_move_out)

    meta = payload["column_meta"]
    for column in ("charge", "payment", "running_balance"):
        assert meta[column]["type"] == "money", (
            f"{column} is money and the server must say so. Untyped, the wire "
            "value 84.200000 reaches the clerk exactly as stored."
        )
    # …and the two new columns are NOT money — they are a name and a number.
    assert meta.get("occupant") is None
    assert meta.get("account") is None


# ═══════════════════════════════════════════════════════════════════════════
# NFR-3 — it pages, and the carry-forward survives the page
# ═══════════════════════════════════════════════════════════════════════════
def test_br_rep_043__the_running_balance_is_identical_paged_and_unpaged(
    brazos, unit_with_a_move_out
) -> None:
    """The one property a statement cannot be wrong about and still be a statement."""
    with tenant_ctx(brazos):
        whole = _unit_statement(unit_with_a_move_out)
        pages = [
            _unit_statement(unit_with_a_move_out, per=1, page=n) for n in (1, 2, 3)
        ]

    walked = [row for page in pages for row in page["rows"]]
    assert len(walked) == len(whole["rows"]) == 3
    # ⚠ **COMPARED AS NUMBERS AND NEVER AS STRINGS, AND THIS FILE LEARNED IT THE
    # HARD WAY.** `queries._money` serves the EXACT decimal the read model
    # struck, and the paged path's opening comes from a SQL aggregate while the
    # unpaged path's comes from a Python sum — so the same figure arrives as
    # `"30.0000000000000"` on one and `"30.000000"` on the other. The first
    # draft of this case compared the strings and went red on two values that
    # are equal. `test_br_rep_038_statement.py` records the identical trap one
    # file over; this is that comment being obeyed rather than rediscovered.
    assert [Decimal(row["running_balance"]) for row in walked] == [
        Decimal(row["running_balance"]) for row in whole["rows"]
    ], (
        "row n's running balance must be the same figure whether it was read on "
        "page n or in one unpaged read. A difference means the page re-opened "
        "at the window's opening instead of carrying forward."
    )

    # `page_opening_balance` is the window's opening ONLY on page one.
    assert Decimal(pages[0]["totals"]["page_opening_balance"]) == AUGUST_BILL
    assert Decimal(pages[1]["totals"]["page_opening_balance"]) == (
        AUGUST_BILL + MARISOL_BILL
    )

    # ⚠ **AND `totals` IS THE WINDOW'S ON EVERY PAGE.** A closing balance that
    # moved with the page would be what the rows in front of the clerk come to,
    # not what the unit owes.
    for page in pages:
        assert Decimal(page["totals"]["closing_balance"]) == Decimal(
            whole["totals"]["closing_balance"]
        )
        assert page["totals"]["occupants"] == whole["totals"]["occupants"], (
            "the head names the window's occupants on EVERY page. Naming only "
            "the page's would put one person's name on page one and another's "
            "on page two of one document."
        )


def test_br_rep_043__the_export_is_every_row_and_not_a_page(
    brazos, unit_with_a_move_out
) -> None:
    """Two functions, not a flag (brief §8.2) — so an export cannot inherit `per`."""
    with tenant_ctx(brazos):
        streamed = list(
            statement_module.statement_stream(
                {
                    "from": SEPT_START.isoformat(),
                    "to": SEPT_END.isoformat(),
                    "subject": "unit",
                    "subject_id": str(unit_with_a_move_out["unit_id"]),
                    "per": 1,
                }
            )
        )
    assert len(streamed) == 3, (
        "the export yields every row of the window even when `per` says 1. "
        f"Got {len(streamed)} — an export that reached the paging function "
        "would write a valid-looking one row over a three-row unit."
    )
    assert [row["occupant"] for row in streamed] == [
        "Marisol Vega",
        "Marisol Vega",
        "Dwayne Okafor",
    ]


# ═══════════════════════════════════════════════════════════════════════════
# The refusals that must SURVIVE
# ═══════════════════════════════════════════════════════════════════════════
def test_br_rep_043__customer_and_premises_still_refuse_by_name(brazos) -> None:
    """`P2.15` unblocked ONE subject. The other two must still say what is missing.

    A lane that "turned the subjects on" by deleting the refusal table would
    pass every test above and serve an account's statement under a customer's
    heading — hard-won law 2's mirror on a money screen.
    """
    from apps.reports import queries

    for subject in ("customer", "premises"):
        with tenant_ctx(brazos):
            with pytest.raises(queries.DatasetCannotServe):
                statement_module.statement(
                    {
                        "from": SEPT_START.isoformat(),
                        "to": SEPT_END.isoformat(),
                        "subject": subject,
                        "subject_id": "irrelevant",
                    }
                )
    assert "unit" not in statement_module.SUBJECTS_NOT_SERVED


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 Phase 2 · P2.15 · BR-REP-043 (PO ruling 2026-09-27)
# screens: 2·1 Report viewer at /reports/statement?subject=unit
# generated: 2026-09-27 by lane REP-SUBJECTS
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

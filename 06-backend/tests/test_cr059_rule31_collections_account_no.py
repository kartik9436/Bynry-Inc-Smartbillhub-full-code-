# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-015 · US-PAY-014 (the collections board this reads)
#           Screens: S34 (the collections board — the Collections tab)
# Rules:    B14 rule 31 (RATIFIED 2026-08-30 — PO: *"no Databse ID on screen -
#           that is a rule"*) · B14 rule 33 (a FACT is at most six words) ·
#           BR-PAY-029 (collections lists read balance high → low) ·
#           CLAUDE.md hard rule 1 (tenant scoping)
# ───────────────────────────────────────────────────────
"""A raw database UUID was printed to a utility clerk. This is the guard.

**THE DEFECT, as the PO met it.** On the Payments → Collections tab the ACCOUNT
column read

    01a046dd-d809-7e20-81a3-87b1eddc1b64   $496.95   10   Nothing sent yet

while the Outstandings tab one click away read `AC-2026-00048` for the same
customer. `CollectionsPage.tsx` rendered `<td>{row.account_id}</td>` because
`collections_read.ladder_board` served no account NUMBER: it builds its rows on
`billing_seam.outstanding_positions`, which reads BILLING's invoices and knows
nothing about a customer reference.

**IT WAS A KNOWN LIMITATION THAT BECAME A RULE BREACH.** The screen's own
exceptions note reported it at the time it was written — *"the honest fix is
`account_no` on the board row"* — and then B14 rule 31 was ratified on
2026-08-30 and turned a reported gap into a defect. Hard-won law 1: a comment
describing a gap is a note, never a plan, and this file is what a plan looks
like.

════════════════════════════════════════════════════════════════════════════
WHY A BACKEND TEST CAN HONESTLY SAY "NO CELL"
════════════════════════════════════════════════════════════════════════════
Rule 31 is about RENDERED OUTPUT and no gate in this repo reads any (B14's own
status table says so). `test_no_rendered_cell_of_the_board_is_a_uuid` closes as
much of that as a Python test can: it reads the columns straight out of
`CollectionsPage.tsx` — every `row.<field>` that appears inside a `<td>` of
`LadderRow` — and checks THOSE fields on a REAL board row served by the real
read model. So the day a lane puts `row.account_id` back inside a cell, this
test picks the field up by itself and goes red on the uuid; it does not depend
on a hand-kept list of column names that would rot the moment the screen moved.
It is not a substitute for a rendered check. The shape for one is
`10-scripts/render-checks/cr053-bill-surface.mjs` (DEF-2716, S30) and S34 still
has none — REPORTED, not silently covered.

════════════════════════════════════════════════════════════════════════════
AND A BLANK NUMBER IS NOT A MISSING ONE
════════════════════════════════════════════════════════════════════════════
`customers.Account.account_no` is a `TextField()`, so an account that has never
been numbered carries `""` and not NULL — `models.py` says so beside the
CR-046 constraint: *"under the 2026-08-27 ruling `account_no` is blank on every
row"* for an imported book of accounts. `""` would render as an EMPTY CELL,
which rule 31 forbids as loudly as the uuid did: *"where neither exists, the
field says so IN WORDS"*. So the read model normalises blank to null and the
screen says **"No account number"** — four words, inside rule 33's six-word cap
for a FACT — and never falls back to the id.
"""

import re
import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from apps.payments import api as payments_api
from apps.payments import collections_read

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_pay_020_023_bank_rec import an_account_of, an_issued_bill
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

AS_OF = date(2026, 8, 16)

#: PO ruling 2026-08-12 (OQ-137/OQ-157) — *"Same $25 floor on the whole
#: ladder"*. Passed in exactly as `POST /collections/run` accepts it, so this
#: file asserts the ACCOUNT COLUMN rather than re-asserting the threshold read.
FLOOR = "25.00"

#: The number the PO saw on the SIBLING tab for the same customer. The whole
#: defect is that one tab printed this and the other printed the row's uuid.
NOVAK_NO = "AC-2026-00048"

#: A uuid as it reaches a screen. Deliberately the shape the PO reported —
#: eight hex, a dash — and not a strict uuid parse, because a truncated or
#: re-formatted id on a screen is the same breach.
UUID_ON_SCREEN = re.compile(r"^[0-9a-f]{8}-", re.IGNORECASE)

COLLECTIONS_PAGE = (
    Path(__file__).resolve().parents[2]
    / "07-frontend"
    / "src"
    / "features"
    / "payments"
    / "CollectionsPage.tsx"
)


def call(view, method, tenant, **kwargs):
    """One board request as the clerk who works this screen (A4 · billing_clerk)."""
    return api_call(view, method, user=FakeUser(), role="billing_clerk", tenant=tenant, **kwargs)


def a_debtor(
    actor, tenant, *, account_no, owed=Decimal("496.95"), due_on=date(2026, 8, 6), service="electric"
):
    """One account with an ISSUED, unpaid bill — a real outstanding position.

    Built through billing's own rows, exactly as
    `test_us_pay_015_019_collections_surface.a_debtor` does, because the board
    reads `billing_seam.outstanding_positions` and a stubbed position would
    prove the seam's shape is what this lane imagined.

    `service` is a parameter for `an_account_of`'s own reason: Lone Star Ridge
    is water-only and metering correctly refuses an electric unit there, and
    the cross-tenant case needs a real account in BOTH utilities.
    """
    account = an_account_of(actor, tenant, service=service)
    account.account_no = account_no
    account.save(update_fields=["account_no"])
    an_issued_bill(
        tenant,
        account,
        number=f"BL-2608-{uuid.uuid4().hex[:6]}",
        total=owed,
        issued_on=due_on,
    )
    return account


def board_rows(tenant):
    return call(
        payments_api.collections_ladder,
        "get",
        tenant,
        query={"as_of": AS_OF.isoformat(), "balance_floor": FLOOR},
    ).data["rows"]


def rendered_fields() -> tuple[str, ...]:
    """Every `row.<field>` the collections board prints INSIDE a table cell.

    Read from the screen rather than listed here, so a column added tomorrow is
    covered tomorrow. `key={row.account_id}` on the `<tr>` is deliberately NOT
    matched: a React key and a route parameter are not visible values, and rule
    31 governs what a utility user can READ.
    """
    source = COLLECTIONS_PAGE.read_text(encoding="utf-8")
    start = source.find("function LadderRow(")
    assert start != -1, (
        "LadderRow is gone from CollectionsPage.tsx, so this test no longer knows which "
        "fields the board renders. Point it at the new row component before trusting it "
        "green — a check that cannot fail is worse than no check."
    )
    body = source[start : source.find("\n}", start)]
    # A COMMENT IS NOT A CELL. `{/* … */}` blocks are stripped before the scan
    # or this check reads the sentence explaining why `row.account_id` is no
    # longer printed as though it were printing it — a false RED on the fix,
    # which is the same failure class as a check that cannot go red at all.
    body = re.sub(r"\{/\*.*?\*/\}", "", body, flags=re.DOTALL)
    cells = body.split("<td")[1:]
    assert cells, "no <td> found in LadderRow — the row component changed shape"
    fields: list[str] = []
    for cell in cells:
        # `(?<![.\w])` so a translation key like `payments.row.noAccountNo`
        # is not read as a field of the row — `\b` matches after the dot.
        for field in re.findall(r"(?<![.\w])row\.(\w+)", cell):
            if field not in fields:
                fields.append(field)
    return tuple(fields)


# ══════════════════════════════════════════════════════════════════════════
# B14 rule 31 — the NUMBER is the visible value
# ══════════════════════════════════════════════════════════════════════════
def test_rule31__the_board_row_carries_the_human_facing_account_number(brazos, marcus):
    """The row must SERVE `AC-2026-00048`, not only the id behind it.

    Nothing a screen cannot read can be shown, so the fix has to land on the
    read model: the frontend had no number to print because the board never
    sent one.
    """
    with tenant_ctx(brazos):
        a_debtor(marcus, brazos, account_no=NOVAK_NO)
        rows = board_rows(brazos)

    assert len(rows) == 1
    assert rows[0]["account_no"] == NOVAK_NO, (
        "the collections board serves no human-facing account number, so the screen has "
        "nothing to print but the row's uuid — B14 rule 31"
    )


def test_rule31__no_rendered_cell_of_the_board_is_a_uuid(brazos, marcus):
    """THE DEFECT, in the shape the PO met it — over the REAL columns.

    The fields come from `CollectionsPage.tsx` itself (see `rendered_fields`),
    so this asserts the screen and not a copy of it.
    """
    with tenant_ctx(brazos):
        a_debtor(marcus, brazos, account_no=NOVAK_NO)
        rows = board_rows(brazos)

    fields = rendered_fields()
    assert "account_no" in fields, (
        f"the account column still does not render `account_no` (it renders {fields!r}) — "
        "the screen half of this defect is unfixed"
    )
    leaked = {
        field: rows[0][field]
        for field in fields
        if isinstance(rows[0].get(field), str) and UUID_ON_SCREEN.match(rows[0][field])
    }
    assert not leaked, (
        f"a database id is the visible value of {sorted(leaked)} on the collections board: "
        f"{leaked!r} — B14 rule 31, PO 2026-08-30 *'no Databse ID on screen - that is a rule'*"
    )


def test_rule31__an_unnumbered_account_says_so_and_never_falls_back_to_the_id(brazos, marcus):
    """A blank `account_no` comes back NULL — not `""`, and never the uuid.

    `account_no` is a `TextField()`, so an unnumbered account holds `""`. The
    screen writes `row.account_no ?? "No account number"`, and `""` is not
    null: it would slip past the fallback and draw an EMPTY CELL, which rule 31
    forbids in the same sentence as the id (*"the field says so in words"*).
    So the normalisation belongs here, where every reader of the board gets it.
    """
    with tenant_ctx(brazos):
        account = a_debtor(marcus, brazos, account_no="   ")
        rows = board_rows(brazos)

    assert rows[0]["account_no"] is None, (
        "a blank account number must reach the screen as null so the field can say so in "
        f"words; got {rows[0]['account_no']!r}, which renders as an empty cell"
    )
    assert rows[0]["account_no"] != str(account.pk)
    assert rows[0]["account_no"] != str(account.id)


def test_rule31__the_number_never_crosses_a_tenant(brazos, marcus, lonestar, erin):
    """Hard rule 1 — and it is the fix's OWN risk, not a decoration.

    The number is reached by asking CUSTOMERS for account rows, so this change
    added a read of another module's table set to a screen that previously did
    not have one. What makes it lawful is that it goes through customers' own
    published `account_queryset()`, which filters on `app.tenant_id` itself
    (RLS FORCE is the second guarantee) — never a queryset this module builds.

    So: give two utilities a debtor apiece with an unmistakable number each and
    assert **neither board can name the other's customer.** A lookup written as
    `Account.objects.filter(pk__in=…)` would pass every other case in this file
    and fail this one.
    """
    with tenant_ctx(lonestar):
        a_debtor(erin, lonestar, account_no="LS-9999-00001", service="water")
        theirs = board_rows(lonestar)

    with tenant_ctx(brazos):
        a_debtor(marcus, brazos, account_no=NOVAK_NO)
        ours = board_rows(brazos)

    assert [row["account_no"] for row in ours] == [NOVAK_NO]
    assert [row["account_no"] for row in theirs] == ["LS-9999-00001"]


def test_rule31__a_board_outside_a_tenant_refuses_rather_than_answering(brazos, marcus):
    """No `app.tenant_id`, no board — the read model refuses before it reads.

    The companion to the case above: the account lookup cannot be given a
    tenant to look at, so the only safe answer without one is a refusal.
    """
    from core import errors

    with tenant_ctx(brazos):
        a_debtor(marcus, brazos, account_no=NOVAK_NO)

    with pytest.raises(errors.AuthError):
        collections_read.ladder_board(as_of=AS_OF, balance_floor=Decimal(FLOOR))

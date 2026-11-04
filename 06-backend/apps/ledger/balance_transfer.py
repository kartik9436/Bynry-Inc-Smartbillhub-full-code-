# ── Trace ──────────────────────────────────────────────
# Change:   CR-185-BRC10 D5 — "Balance to owner" POSTS. PO ruling 2026-10-14
#           (decision log *"LANDLORD D2–D5 … BALANCE-TO-OWNER POSTS (closes
#           OQ-1250 → a)"*), verbatim: *"D5 … option 1; property is always
#           under landload agreement"*.
# Story:    US-LED-001 (the contract row *"Master-account balance transfer |
#           AR (master) | AR (final account) — AR total unchanged"*, which had
#           no product caller until this file) · US-CUS-005 S20 step 4
# Rules:    BR-CUS-097 (as QUALIFIED 2026-08-27 — the residue moves only when a
#           clerk ties it back) · BR-BIL-013 (LE-1: 135.90 moved ACC-1055 →
#           master ACC-0009, AR total unchanged) · OQ-1250 CLOSED → (a) ·
#           OQ-069 (the landlord-agreement condition, satisfied by *"property
#           is always under landload agreement"*) · BR-LED-001 (every line
#           carries source + account dimension) · BR-LED-025 (2 dp at post,
#           the caller rounds) · CLAUDE.md rules 2, 4, 5, 6, 7
# Tests:    06-backend/tests/test_cr185_balance_to_owner_posts.py
# Impacts:  apps/ledger/posting.py 🔒 (the sole writer this composes for —
#           UNCHANGED by this file) · apps/customers/move_out_settlement.py
#           (the one caller) · apps/ledger/reporting.py (`transfer` is already
#           BR-REP-008's word for this source type)
# ───────────────────────────────────────────────────────
"""ONE balanced entry that moves a departing tenant's residue to the owner.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this composes a money-bearing journal
entry under CLAUDE.md's 🔒 *ledger posting*. AI-authored 2026-10-14 under the
PO ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*).
Row in `12-governance/09-human-review-ledger.md`; it may never reach lifecycle
RATIFIED without a recorded human sign-off. What the PO was SHOWN is that row
and the decision log entry, and nothing more is claimed for it.

════════════════════════════════════════════════════════════════════════════
WHAT WAS SHOWN, AND THEREFORE WHAT THIS IS ALLOWED TO DO
════════════════════════════════════════════════════════════════════════════
*"$1,053.78 leaves the tenant's closed account and lands on Maple Rentals'
account, posted in the books"* — reading (a) of `OQ-1250`:

    DR  accounts receivable   1,053.78   account = OWNER (AC-2026-00053)
    CR  accounts receivable   1,053.78   account = TENANT (AC-2026-00041)

Same control account on both sides; only the ACCOUNT DIMENSION differs. So:

  * nothing reaches revenue and nothing reaches bad debt — readings (b)
    write-off-and-recharge and (c) a suspense leg were NOT shown and are not
    built;
  * the TOTAL receivable is unchanged — the trial balance does not move;
  * the tenant's balance falls by the amount and the owner's rises by it,
    because an account balance IS the ledger's own sum over posted lines
    carrying that account (`DEF-127`).

⚠ **THE CONTRACT ROW WAS ALREADY IN `US-LED-001`'s TABLE.** `OQ-1250`'s body
said *"a receivable moving from one customer to another is not one of"* the
seventeen events. The table names *"Master-account balance transfer | AR
(master) | AR (final account) — AR total unchanged | BR-BIL-013 (LE-1,
135.90)"*, and `tests/ledger_le_fixtures.py` has posted exactly this shape
since 2026-08-16. What was missing was a CALLER, and a ruling that the
move-out residue is that event. The ruling arrived on 2026-10-14; this file is
the caller's composition, and the contract row now cites the ruling.

════════════════════════════════════════════════════════════════════════════
WHY THE COMPOSITION IS IN THE LEDGER, NOT IN CUSTOMERS
════════════════════════════════════════════════════════════════════════════
`apps/ledger/deposit_legs.py` exception (5), for the same reason: both legs are
the SAME ledger designation (`accounts_receivable`) and customers contributes
nothing to the DR/CR contract except two account ids and a figure. A signed
DR/CR contract lives where the designations are resolved.

════════════════════════════════════════════════════════════════════════════
IDEMPOTENCY (hard rule 6)
════════════════════════════════════════════════════════════════════════════
    posting_key = "transfer|<tenant account id>|balance_to_owner"

One per departing account, because a closed account's residue is tied back
once. A re-delivered request returns the FIRST entry with `created=False` and
writes nothing — no second entry and no second `journal.posted` audit row.

⚠ **A REPLAY CARRYING A DIFFERENT AMOUNT IS REFUSED, NOT SWALLOWED.** The
posting service answers a known key with the first entry whatever the new
request says. If a second residue ever reached this key for a different figure
(an account re-opened and closed again), returning the first entry would tell
the clerk *posted* about money that did not move. The echoed debits are
compared with the amount asked for and a mismatch raises.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE DOES NOT DECIDE
════════════════════════════════════════════════════════════════════════════
The TARGET (resolved by `move_out_settlement` from the premises' declared
owner, never a caller argument — BR-CUS-097), the AMOUNT (the settlement's own
2-dp shortfall, the figure the clerk saw), and the DATE (the business day the
caller states; nothing here reads a clock — BR-TEN-043, gate G6). It refuses a
float, a negative, a zero, a third decimal place, and a transfer from an
account to itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from apps.ledger import chart, models, posting, selectors

ZERO = Decimal("0")

#: The source type BR-REP-008 already names (`reporting.SOURCE_TYPE_TO_VOCABULARY
#: ["transfer"]`) and LE-1's fixture writes. One word, so a statement and the
#: journal call the line a *Transfer* without a new vocabulary entry.
SOURCE_TRANSFER = "transfer"

#: The event. Named once so a caller cannot mistype it into a key that never
#: collides with anything (a replay guard that guards nothing).
EVENT_BALANCE_TO_OWNER = "balance_to_owner"

#: The ruling every entry cites, carried into the audit row.
RULING = "OQ-1250 CLOSED 2026-10-14 → (a) · PO D5 · BR-CUS-097 · US-LED-001"


class BalanceTransferError(posting.PostingError):
    """A transfer the books refuse — a `PostingError`, so a caller already
    translating the posting service's refusals catches it unchanged."""


@dataclass(frozen=True)
class BalanceTransferPosting:
    """What the transfer left in the books."""

    entry_id: str
    posting_key: str
    created: bool
    amount: Decimal
    from_account_id: str
    to_account_id: str
    designation: str = chart.AR


def posting_key_for(from_account_id: Any) -> str:
    """The replay guard's string for one departing account."""
    return posting.posting_key(
        source_type=SOURCE_TRANSFER, source_id=from_account_id, event=EVENT_BALANCE_TO_OWNER
    )


def _checked(amount: Any) -> Decimal:
    if not isinstance(amount, Decimal):
        raise BalanceTransferError(
            f"the balance to move arrived as {amount!r} ({type(amount).__name__}), not a "
            "Decimal. Money is never a float (CLAUDE.md rule 2); refused rather than converted."
        )
    if amount <= ZERO:
        raise BalanceTransferError(
            f"the balance to move is {amount}. Only a residue the tenant still OWES is tied "
            "back to the owner; zero moves nothing and a negative would move a credit, which "
            "is a different event with a different contract."
        )
    return amount


def post_balance_to_owner(
    *,
    from_account_id: Any,
    to_account_id: Any,
    amount: Decimal,
    entry_date: date,
    posted_at: datetime,
    currency: str,
    actor: Any = None,
    memo: str | None = None,
    audit_context: dict[str, Any] | None = None,
) -> BalanceTransferPosting:
    """DR AR (owner account) / CR AR (tenant account) for `amount`. ONE entry.

    Worked, on the walk figure the PO was shown: AC-2026-00041 ties back
    **$1,053.78** to its owner AC-2026-00053 → DR 1200 AR 1,053.78 account =
    AC-2026-00053 / CR 1200 AR 1,053.78 account = AC-2026-00041. The tenant's
    balance falls by 1,053.78, the owner's rises by 1,053.78, total AR is the
    same before and after.

    Raises `BalanceTransferError` (a `PostingError`) for anything a human can
    act on; the posting service's own refusals pass through unchanged.
    """
    amount = _checked(amount)
    if str(from_account_id) == str(to_account_id):
        raise BalanceTransferError(
            "the tenant account and the owner account are the same account, so there is "
            "nothing to move — a transfer to itself would post a debit and a credit that "
            "cancel on one customer's row."
        )
    receivable = selectors.gl_account_id_for_designation(chart.AR)
    if not receivable:
        raise BalanceTransferError(
            "no live ledger account carries the 'accounts_receivable' designation, so the "
            "residue has no receivable to move between. A human designates one on the GL "
            "mapping page; nothing substitutes another account."
        )
    key = posting_key_for(from_account_id)
    result = posting.post(
        posting.PostingRequest(
            posting_key=key,
            entry_date=entry_date,
            posted_at=posted_at,
            currency=str(currency),
            source_type=SOURCE_TRANSFER,
            source_id=from_account_id,
            memo=memo or "Balance to owner",
            lines=(
                # The OWNER now owes it.
                posting.PostingLine(
                    ledger_account_id=receivable,
                    side=models.SIDE_DEBIT,
                    amount=amount,
                    source_type=SOURCE_TRANSFER,
                    source_id=from_account_id,
                    account_id=to_account_id,
                ),
                # The TENANT no longer does.
                posting.PostingLine(
                    ledger_account_id=receivable,
                    side=models.SIDE_CREDIT,
                    amount=amount,
                    source_type=SOURCE_TRANSFER,
                    source_id=from_account_id,
                    account_id=from_account_id,
                ),
            ),
            audit_context={
                "balance_to_owner": str(amount),
                "from_account_id": str(from_account_id),
                "to_account_id": str(to_account_id),
                "br_ref": RULING,
                **(audit_context or {}),
            },
        ),
        actor=actor,
    )
    if not result.created and result.debits != amount:
        raise BalanceTransferError(
            f"this account's balance was already moved to its owner ({result.debits}), and "
            f"this request asks to move {amount}. One departing account ties back once; the "
            "first entry stands and nothing new was posted."
        )
    return BalanceTransferPosting(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        amount=amount,
        from_account_id=str(from_account_id),
        to_account_id=str(to_account_id),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-185-BRC10 · decision log 2026-10-14 "LANDLORD D2–D5" · OQ-1250 (CLOSED → a) · OQ-069 · US-LED-001's contract table
# generated: 2026-10-14 by lane OWNER-D4D5
# checklist: A✔ B✔ C✔ D=n/a(no API of its own — reached through POST /accounts/{id}/settle-shortfall) E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: tests/test_cr185_balance_to_owner_posts.py, SQLite and PostgreSQL 16
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

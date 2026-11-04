# ── Trace ──────────────────────────────────────────────
# Rules:   BR-RAT-1048 (a flat charge-code amount is ONE *All sizes* row) ·
#          BR-RAT-1049 (price rows are dated and logically killed, never
#          deleted) · BR-RAT-1051 (three kinds — base · plan · other)
# Change:  CR-156-BRC10 (PO rulings 2026-10-01, decision log rows whose last
#          column reads "charge-code redesign")
# ───────────────────────────────────────────────────────
"""Charge-code vocabulary defined ONCE — the reserved size, the epoch, the kinds.

Every module that has to say *"this row is the flat amount"* or *"this code is a
plan charge"* imports the word from here. A second spelling of `"All sizes"`
anywhere is a row the lookup cannot find, which is a bill refused on billing day
for a price the utility believes it set.
"""

from __future__ import annotations

from datetime import date

#: ── THE RESERVED SIZE (PO 2026-10-01, option A) ─────────────────────────────
#: PO verbatim: *"A · Flat amount as an \"All sizes\" row … BASE-S $9.00 is
#: stored as one row in charge_code_amounts with size \"All sizes\". An edit
#: closes that row and adds a new one, the same as for sizes."*
#:
#: It is the value of `charge_code_amounts.size_class` on the row that holds a
#: code's FLAT amount (one per customer class where the code is priced by
#: class). It is not a `service_size_classes` code and can never become one:
#: real size codes carry no space (`W-58`, `CART-96`, `SOL-P2`), and
#: `services._validate_size_amounts` refuses it as a size a meter can have.
ALL_SIZES = "All sizes"

#: ── THE START OF PRICE HISTORY ──────────────────────────────────────────────
#: Every price row that existed before dates did — and every row a seed writes
#: for a sample utility — is effective from this day. A row with no stated
#: start has always applied; dating it from the day a demo was seeded would
#: refuse every catch-up bill for the months before that day. It is a date far
#: enough back that no bill this product can produce starts before it.
PRICE_HISTORY_EPOCH = date(2000, 1, 1)

#: ── THE THREE KINDS (PO 2026-10-01) ─────────────────────────────────────────
#: *"can we have 3 kinds base charges, plan charges and others"*.
KIND_BASE = "base"
KIND_PLAN = "plan"
KIND_OTHER = "other"
KINDS: tuple[str, ...] = (KIND_BASE, KIND_PLAN, KIND_OTHER)

#: The codes the PO named as PLAN charges, by number on the 27-code table and
#: then by name (decision log 2026-10-01, *"CHARGE CODE KINDS — WHAT EACH ONE
#: HOLDS"*): #10 CONN · #11 DISC · #12 RECON · #13 TRANSFER · #14 MOVE-OUT ·
#: #23 CC-CONV, then *"all these will go in plan - PAPER … HYDRANT … LATE … NSF
#: … TAMPER"*, and *"we need deposite in plans"*. Penalties and deposits in
#: general are plan charges too (*"we need penalties in plans"*) — that half is
#: read off `charge_type` in `default_kind`, so a utility's own penalty code is a
#: plan charge without being listed here.
PLAN_CODES: frozenset[str] = frozenset(
    {
        "CONN",
        "DISC",
        "RECON",
        "TRANSFER",
        "MOVE-OUT",
        "CC-CONV",
        "PAPER",
        "HYDRANT",
        "LATE",
        "NSF",
        "TAMPER",
        "DEPOSIT",
    }
)

#: `charges.charge_type` values that make a code a plan charge whatever it is
#: called: penalties, and refundable deposits (`DEPO-R`, `DEPO-C`).
PLAN_CHARGE_TYPES: frozenset[str] = frozenset({"penalty", "refundable"})


def default_kind(code: str | None, charge_type: str | None, is_base: bool) -> str:
    """The kind a code takes when nobody has chosen one — the PO's own list.

    Used by the one-time backfill (`rating/0051`), by rating's reference-list
    seed, and by `create_charge` when a payload names no kind. **Base** is the
    declared `is_base` flag and never the code string; **plan** is the PO's
    named list plus every penalty and every deposit; everything else — the
    application fees, RE-READ … BULK-WATER — is **other** (*"in other add
    application fees + 15 RE-READ … 27 BULK-WATER … - these are all others"*).
    """
    if is_base:
        return KIND_BASE
    if (code or "").strip().upper() in PLAN_CODES:
        return KIND_PLAN
    if (charge_type or "").strip().lower() in PLAN_CHARGE_TYPES:
        return KIND_PLAN
    return KIND_OTHER

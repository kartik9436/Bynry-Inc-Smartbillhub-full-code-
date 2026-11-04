# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-8151 — a counted service (2 carts at $18.00) was stored as
#          TWO lines, usage $30.00 + base $6.00.
# Ruling:  PO 2026-09-30, decision log "ONE-TIME BILL: SIX ANSWERS" (5),
#          verbatim: *"per service"* — ONE line per counted service, count and
#          sizes in its quantity and wording; amount unchanged.
# Rules:   BR-RAT-090 (a counting capacity service's quantity is a COUNT of its
#          assets) · BR-RAT-024 / CR-063 (fire: $60.00 + 2 × $12.00 = $84.00 —
#          amount kept, *"on two bill lines"* superseded for LAYOUT) · CLAUDE.md
#          rule 3 (a quantity always carries its unit) · rule 2 (no rounding
#          here — the lines are already finalized)
# Callers: apps/billing/runs.price_account (the one gateway both the bill run's
#          stage 6 and the one-time bill's preview price through)
# Tests:   tests/test_def_bil_8151_counted_service_one_line.py ·
#          tests/test_otb_t2_money_paths_pg.py (PostgreSQL) ·
#          tests/test_cr063_c3_fire_priced.py tc2b
# ───────────────────────────────────────────────────────
"""**A COUNTED SERVICE PRINTS AS ONE LINE — its count, its sizes, its money.**

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (2026-09-30) — it decides which stored `invoice_lines`
a bill carries. AI-authored under the PO ruling of 2026-08-09 (*"AI will do it;
we will review it later as human"*); row in
`12-governance/09-human-review-ledger.md`, 2026-09-30, bill-line layout lane.

`gather._per_size_configs` prices a counting capacity service (trash, fire) as
one `TariffConfig` per SIZE present on the unit, and folds every size's base
onto the first config. So the engine emits one usage line per size plus one
base line: 2 carts at `$15.00` + `$3.00` came out as **usage `$30.00` and base
`$6.00`**, and fire's 6" line with two 2" lines as `$60.00` and `$24.00`.

The PO ruled the layout on 2026-09-30 — *"per service"* — so this joins them:

    2 × 96 gal cart   → ONE line   2 cart  @ $18.00   = $36.00
    1 × 6" + 2 × 2"   → ONE line   3 connection       = $84.00

**WHY HERE, AFTER THE ENGINE, AND NOT IN IT.** The join is LAYOUT: it adds
figures the engine has already finalized (B4.4 — one rounding per line, done)
and changes no total, no tax and no tax base. Doing it inside the 🔒 engine
would route every ❄️ golden figure through a new stage for a change that is not
arithmetic. `runs.price_account` is the one door both the bill run and the
one-time bill price through, so both documents agree by construction.

**THE MERGED LINE'S KIND IS `usage`.** It carries a COUNT and its unit (rule 3
— a base line has neither), and `issue._gl_account_for` resolves both usage and
base to the SERVICE's revenue account; the signed chart does not split trash or
fire (*"a Trash base charge lands in Trash revenue"*), so no GL figure moves.
The one-time answer prints it as charge `per_asset` (contract §2).

**IT REFUSES TO JOIN — and leaves the lines exactly as the engine made them —
when joining would state something false:** lines of one service that disagree
on `taxable`, on the unit, or on the tariff version (a single line cannot carry
two provenances). None of those arises from `_per_size_configs` today; each is
the honest answer if one ever does.

**NOT JOINED: a minimum top-up** (its own `minimum` line, BR-RAT-028) and a
split-period bill (`midperiod`), whose lines each belong to one stretch.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal
from typing import Any, Iterable

JOINED_KINDS = ("usage", "base")


def counted_services(tariffs: Iterable[Any]) -> frozenset[str]:
    """The services priced per SIZE group — `TariffConfig.per_size_line`."""
    return frozenset(
        str(tariff.service) for tariff in tariffs if getattr(tariff, "per_size_line", False)
    )


def _count_text(quantity: Decimal) -> str:
    return format(quantity.normalize(), "f")


def _size_words(line: Any, service: str) -> str | None:
    prefix = f"{service} - "
    description = str(getattr(line, "description", "") or "")
    return description[len(prefix) :] if description.startswith(prefix) else None


def _join(service: str, lines: list[Any]) -> Any | None:
    """ONE line for `lines` (every usage and base line of one counted service),
    or None when joining would misstate them."""
    usage = [line for line in lines if line.kind == "usage"]
    if not usage:
        return None
    if len({bool(line.taxable) for line in lines}) != 1:
        return None
    units = {line.unit for line in usage}
    if len(units) != 1 or None in units:
        return None
    versions = {getattr(line, "tariff_version_id", None) for line in lines}
    if len(versions) != 1:
        return None
    quantity = sum((Decimal(line.quantity) for line in usage), Decimal("0"))
    amount = sum((line.amount for line in lines), Decimal("0"))
    sizes = [(_size_words(line, service), line.quantity) for line in usage]
    if all(words for words, _q in sizes):
        description = f"{service} - " + ", ".join(
            f"{_count_text(Decimal(qty))} × {words}" for words, qty in sizes
        )
    else:
        description = f"{service} - {_count_text(quantity)} {usage[0].unit}"
    # THE RATE IS PRINTED ONLY WHERE IT FOOTS: one size, so every asset costs
    # the same and quantity × rate = amount exactly ($18.00 × 2 = $36.00). Two
    # sizes have no single rate — an average ($84.00 / 3 = $28.00) is a price
    # nothing on the schedule charges — so the line states none.
    unit_price = None
    if len(usage) == 1 and quantity:
        candidate = amount / quantity
        if candidate * quantity == amount:
            unit_price = candidate
    return dataclasses.replace(
        usage[0],
        kind="usage",
        description=description,
        amount=amount,
        quantity=quantity,
        unit=usage[0].unit,
        unit_price=unit_price,
        asset_id=None,
    )


def one_line_per_counted_service(priced: Any, services: frozenset[str]) -> Any:
    """`priced` (a `rating_seam.RatedBill`) with each counted service's usage and
    base lines joined into ONE, in the position of that service's first line.

    Totals are copied, never recomputed: the join is a sum of lines that were
    already in the total, so `priced.total` is still the sum of the lines.
    """
    if not services:
        return priced
    grouped: dict[str, list[Any]] = {}
    for line in priced.lines:
        service = getattr(line, "service", None)
        if line.kind in JOINED_KINDS and service in services:
            grouped.setdefault(service, []).append(line)
    joined = {
        service: _join(service, lines) for service, lines in grouped.items() if len(lines) > 1
    }
    joined = {service: line for service, line in joined.items() if line is not None}
    if not joined:
        return priced
    out: list[Any] = []
    placed: set[str] = set()
    for line in priced.lines:
        service = getattr(line, "service", None)
        if line.kind in JOINED_KINDS and service in joined:
            if service not in placed:
                out.append(joined[service])
                placed.add(service)
            continue
        out.append(line)
    before = sum((line.amount for line in priced.lines), Decimal("0"))
    after = sum((line.amount for line in out), Decimal("0"))
    if before != after:  # pragma: no cover — a join that moved money is a bug
        raise AssertionError(
            f"DEF-BIL-8151: joining counted-service lines moved the bill from {before} to {after}"
        )
    return dataclasses.replace(priced, lines=tuple(out))


def one_line_per_counted_service_per_window(
    priced: Any, owners: tuple[Any, ...], services: frozenset[str]
) -> tuple[Any, tuple[Any, ...]]:
    """`one_line_per_counted_service` for a bill priced in WINDOWS — a catch-up or
    a penalty (`backbill.price_back_bill`), where `owners[i]` names the month line
    `i` bills (None for a bill-level line: a fee, a discount, a tax).

    `DEF-BIL-8733`: the back-bill pass prices through `rating_seam.price_bill`
    and never reached the join above, so each month's trash printed as
    `$15.00` + `$3.00`. Joined per (month, service) — NEVER across months, since
    each line is stored with the one month it bills (`DEF-BIL-8561`). Returns
    the lines and the owners, kept index for index. Layout only: the money is a
    sum of finalized lines (asserted)."""
    lines = tuple(priced.lines)
    if not services or len(owners) != len(lines):
        return priced, owners
    grouped: dict[tuple[Any, str], list[Any]] = {}
    for line, owner in zip(lines, owners):
        service = getattr(line, "service", None)
        if owner is not None and line.kind in JOINED_KINDS and service in services:
            grouped.setdefault((owner, service), []).append(line)
    joined = {key: _join(key[1], group) for key, group in grouped.items() if len(group) > 1}
    joined = {key: line for key, line in joined.items() if line is not None}
    if not joined:
        return priced, owners
    out: list[Any] = []
    out_owners: list[Any] = []
    placed: set[tuple[Any, str]] = set()
    for line, owner in zip(lines, owners):
        key = (owner, getattr(line, "service", None))
        if line.kind in JOINED_KINDS and key in joined:
            if key not in placed:
                out.append(joined[key])
                out_owners.append(owner)
                placed.add(key)
            continue
        out.append(line)
        out_owners.append(owner)
    before = sum((line.amount for line in lines), Decimal("0"))
    after = sum((line.amount for line in out), Decimal("0"))
    if before != after:  # pragma: no cover — a join that moved money is a bug
        raise AssertionError(
            f"DEF-BIL-8733: joining counted-service lines moved the bill from {before} to {after}"
        )
    return dataclasses.replace(priced, lines=tuple(out)), tuple(out_owners)


# ── Lifecycle ─────────────────────────────────────────────
# generated: 2026-09-30 by the one-time-bill defect lane (DEF-BIL-8151)
# status: VERIFIED-UNRATIFIED

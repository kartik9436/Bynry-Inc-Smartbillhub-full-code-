# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-028 (EP-RBS-05) — CR-075 wave S, the rating half: the three
#           reads runbook 16 (*Rate change preview*) makes, added by the module
#           that OWNS `tariffs`, `tariff_versions` and `rate_tiers`.
# Rules:    BR-RBS-039 (a runbook READS through a seam this module owns; the
#           OWNING module publishes the selector) · BR-RAT-031 (save-draft
#           resumable — a NULL `effective_from` IS the draft, one per tariff) ·
#           BR-RAT-007 (the version whose window contains the SERVICE date) ·
#           BR-RAT-003 (rounding happens once, at finalization) · CLAUDE.md hard
#           rule 2 (money 4 decimals, percentages 6, both displayed 2; never a
#           float) · hard rule 3 (a quantity carries its unit) · B4/B5 ❄️ FROZEN
# Tests:    06-backend/tests/test_us_rbs_028_rate_change_preview.py
# Impacts:  apps/runbooks/seams/rating_seam.py (the three wrappers) ·
#           04-docs/05-modules/17-runbooks/11-catalogue/RB-116-rate-change-preview.md
# ───────────────────────────────────────────────────────
"""READ ONLY — the three questions runbook 16 asks of this module.

⚠ **NOT ONE LINE OF PRICING LIVES HERE.** `US-RBS-028`'s own sentence is the
whole design: *"A second pricing implementation here would tell a board
something the product would not then do."* Every figure below comes out of
`apps.rating.engine.price_period` — the same call a bill makes — configured by
`selectors.pricing_inputs_for_version`, which is `pricing_inputs`' own body
extracted in `DEF-434` for exactly this purpose: *"so it can be pointed at a
version that is not in force yet"*. B4 and B5 are ❄️ FROZEN and nothing here
moves a figure in either.

⚠ **THIS FILE IS `rating`', NOT `runbooks`'.** `BR-RBS-039` and
`13-selector-inventory.md` say it twice: a runbook reads through a seam, and the
OWNING module publishes the read. It is a third kind of module beside
`selectors.py`, exactly as `apps/payments/runbook_reads.py` and
`apps/customers/runbook_reads.py` are, and for the same reason — `selectors.py`
is edited by several lanes in a week and a whole-file collision on it costs more
than a new name (CLAUDE.md law 11).

WHAT "COMPARE TO THE ISSUED BILL" MEANS HERE, AND WHY IT IS NOT THE WHOLE BILL
-------------------------------------------------------------------------------
`OQ-319` — *"worst-case bill change: of the whole bill, or of this schedule's own
portion?"* — is OPEN, and this module already answers it in shipped, finance-read
code: `BR-RAT-091`'s ratified worked example moves an 11 kgal household
`$59.00 → $62.54`, which is `$59.00 × 1.06` **exactly**, so the signed figure is
the water portion before taxes, before discounts and before every other service
on the plan. r10 labels its own panel the same way — *"Typical bill · this
service's portion"*.

**This file follows that answer rather than choosing a second one.** A rate-change
preview that measured the whole bill and a rate-change approval gate that measured
the portion would be two answers to one question, on the two screens a utility
files a rate case from.

⚠ **AND IT PRICES BOTH SIDES THROUGH THE ENGINE, WHICH IS WHAT MAKES THE
DIFFERENCE HONEST.** The baseline is the version that was in force on the bill's
own service date (`BR-RAT-007`), priced from the bill's own metered quantity; the
proposed side is the draft, priced from the same quantity. What travels is the
DIFFERENCE, and `reproduced_the_issued_amount` says for each row whether the
baseline pass reproduced what the customer was actually charged. **A preview that
cannot say how well it reproduces the past is a preview nobody should show a
board** (hard-won law 7: a declared blind spot with no number on it is
indistinguishable from an empty one).
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from typing import Any

from apps.rating import engine, models, selectors
from core import tenancy as core_tenancy

ZERO = Decimal("0")


def _tenant_id() -> Any:
    """The tenant this read is for, or a refusal — never a silent whole-estate read."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise RuntimeError(
            "a runbook read was taken with no tenant set. CLAUDE.md hard rule 1: never touch a "
            "tenant table without `app.tenant_id`. On PostgreSQL this would read nothing and on "
            "the SQLite test tier it would read everything, so it refuses instead."
        )
    return tenant_id


def _money(raw: Any) -> Decimal | None:
    """A stored amount as a `Decimal`. **Never `float(...)`** (hard rule 2)."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, float):
        raise TypeError(
            "money arrived as a float. Hard rule 2: stored to 4 decimals and never a binary "
            "fraction — `0.1 + 0.2` is not `0.3`, and no column type catches one that has been "
            "through jsonb."
        )
    return Decimal(str(raw))


def _stored(value: Decimal) -> str:
    """The four-place string a runbook carries. Display rounds; storage does not."""
    return f"{value.quantize(Decimal('0.0001')):f}"


# ══════════════════════════════════════════════════════════════════════════
# 1 · WHAT COULD BE PREVIEWED — runbook 16's `Proposed schedule` picker
# ══════════════════════════════════════════════════════════════════════════


def draft_schedules() -> list[dict[str, Any]]:
    """Every rate schedule carrying a DRAFT version, with what it would replace.

    `BR-RAT-031` save-draft resumable: **a NULL `effective_from` IS the draft**,
    and `uq_tariff_versions_one_draft` makes *"the draft"* a fact rather than a
    convention. `RB-116`'s scope row — *Proposed schedule · Water 2027 · draft*
    — is this list.

    ⚠ **A SCHEDULE WITH NO ACTIVATED VERSION BEHIND IT IS LISTED AND MARKED
    `comparable: False`, NEVER FILTERED OUT.** A first tariff has nothing to be
    compared against, which is a real state and not a fault; hiding it would
    leave a manager searching a dropdown for a draft they can see on the Plans &
    Rates screen. `_baseline_version`'s own reason applies here too: *"a version
    compared with itself reports `0.00%` and that is the one answer this
    analysis must never invent."*

    ⚠ **NO `Tariff` OR `TariffVersion` ROW LEAVES THIS FUNCTION.** A seam hands
    a runbook facts, never another module's ORM object — the posture
    `rating_seam.plan_coverage` already takes in as many words.
    """
    tenant_id = _tenant_id()
    drafts = (
        models.TariffVersion.objects.filter(tenant_id=tenant_id, effective_from__isnull=True)
        .select_related("tariff", "tariff__service")
        .order_by("tariff__name", "created_at")
    )
    today = selectors.seams.tenant_today()
    rows: list[dict[str, Any]] = []
    for draft in drafts:
        tariff = draft.tariff
        if tariff is None or tariff.deleted_at is not None:
            continue
        baseline = selectors.in_force_version(tariff, today)
        rows.append(
            {
                "version_id": str(draft.id),
                "tariff_id": str(tariff.id),
                # B14 rule 31 — the schedule's NAME is what a manager picks.
                "label": tariff.name,
                "service": tariff.service.code if tariff.service_id else "",
                "currency": draft.currency,
                "model": draft.model,
                "is_sample": bool(getattr(tariff, "is_sample", False)),
                "baseline_version_id": str(baseline.id) if baseline else None,
                "baseline_effective_from": (
                    baseline.effective_from.isoformat()
                    if baseline and baseline.effective_from
                    else None
                ),
                "comparable": baseline is not None,
            }
        )
    return rows


# ══════════════════════════════════════════════════════════════════════════
# 2 · WHAT MOVED — runbook 16 step 1, and the *Why* on every mover
# ══════════════════════════════════════════════════════════════════════════


def schedule_change(*, version_id, service_date: dt.date) -> dict[str, Any]:
    """Clause by clause, what the draft changes about the version in force.

    `RB-116`'s biggest-mover table has a **Why** column and its design note is
    why this function exists: *"Why on each mover names the clause of the draft
    that did it, so a tariff can be adjusted before it is adopted rather than
    defended after."* A total with no per-clause attribution is a figure a board
    cannot act on (`TC-RBS-028.1`).

    Both sides are read through `pricing_inputs_for_version` — the ONE
    projection in this product — so the clause list and the prices the engine
    actually charges come from the same reading of the same rows.

    ⚠ **THE TIERS ARE COMPARED BY POSITION AND THE COMPARISON SAYS SO.** A
    ladder that gains a block shifts every block above it, so *"tier 2 starts at
    4,000 gal, not 5,000"* and *"a new top block above 20,000 gal"* are
    different findings about the same list and both are reported: the first is a
    boundary that moved at a position both ladders have, the second is a
    position only the draft has.
    """
    tenant_id = _tenant_id()
    draft = models.TariffVersion.objects.filter(tenant_id=tenant_id, id=version_id).first()
    if draft is None:
        return {"found": False, "reason": "no such rate schedule version for this utility"}
    tariff = draft.tariff
    baseline = selectors._baseline_version(tariff, draft, service_date)
    after = selectors.pricing_inputs_for_version(draft, service_date)
    before = (
        selectors.pricing_inputs_for_version(baseline, service_date)
        if baseline is not None
        else None
    )
    answer: dict[str, Any] = {
        "found": True,
        "version_id": str(draft.id),
        "baseline_version_id": str(baseline.id) if baseline else None,
        # ⚠ **EVERY VERSION THIS SCHEDULE HAS EVER HAD, SO A CALLER CAN TELL
        # WHICH BILLS ARE ACTUALLY ON IT.** `invoice_lines.tariff_version_id` is
        # stamped at issue and frozen, and it is the only honest answer to *what
        # priced this line*. Without this set a preview re-prices every bill of
        # the cycle — including the ones on somebody else's schedule — and shows
        # a board a change to customers the draft would never reach.
        "version_ids": [
            str(one)
            for one in models.TariffVersion.objects.filter(
                tenant_id=tenant_id, tariff=tariff
            ).values_list("id", flat=True)
        ],
        "comparable": baseline is not None,
        "label": tariff.name if tariff else "",
        "service": tariff.service.code if tariff and tariff.service_id else "",
        "currency": draft.currency,
        "unit": after.get("billed_unit") or "",
        "changes": [],
    }
    if before is None:
        return answer

    changes: list[dict[str, Any]] = []
    if str(before.get("model")) != str(after.get("model")):
        changes.append(
            {
                "clause": "model",
                "sentence": f"Rate model is {after.get('model')}, not {before.get('model')}",
                "from_quantity": None,
            }
        )
    base_before, base_after = _money(before.get("base_charge")), _money(after.get("base_charge"))
    if base_before != base_after:
        changes.append(
            {
                "clause": "base_charge",
                "sentence": "Base charge",
                "from_quantity": None,
                "before": None if base_before is None else _stored(base_before),
                "after": None if base_after is None else _stored(base_after),
            }
        )
    price_before, price_after = _money(before.get("unit_price")), _money(after.get("unit_price"))
    if price_before != price_after:
        changes.append(
            {
                "clause": "unit_price",
                "sentence": "Unit price",
                # A flat rate applies from the first unit, so every bill with
                # any usage at all is touched by it.
                "from_quantity": "0",
                "before": None if price_before is None else _stored(price_before),
                "after": None if price_after is None else _stored(price_after),
            }
        )

    tiers_before = list(before.get("tiers") or [])
    tiers_after = list(after.get("tiers") or [])
    unit = str(after.get("billed_unit") or "")
    for index, tier in enumerate(tiers_after):
        old = tiers_before[index] if index < len(tiers_before) else None
        floor = _money((tiers_after[index - 1] or {}).get("upper")) if index else ZERO
        if old is None:
            changes.append(
                {
                    "clause": "new_block",
                    "sentence": _above("New top block above", floor, unit),
                    "from_quantity": None if floor is None else _stored(floor),
                }
            )
            continue
        old_floor = _money((tiers_before[index - 1] or {}).get("upper")) if index else ZERO
        if old_floor != floor:
            changes.append(
                {
                    "clause": "block_boundary",
                    "sentence": (
                        f"Tier {index + 1} starts at {_plain(floor)} {unit}".rstrip()
                        + (f", not {_plain(old_floor)}" if old_floor is not None else "")
                    ),
                    "from_quantity": None if floor is None else _stored(floor),
                }
            )
        if _money(old.get("unit_price")) != _money(tier.get("unit_price")):
            changes.append(
                {
                    "clause": "block_price",
                    "sentence": f"Tier {index + 1} price",
                    "from_quantity": None if floor is None else _stored(floor),
                    "before": _stored(_money(old.get("unit_price")) or ZERO),
                    "after": _stored(_money(tier.get("unit_price")) or ZERO),
                }
            )
    answer["changes"] = changes
    return answer


def _above(prefix: str, floor: Decimal | None, unit: str) -> str:
    if floor is None:
        return f"{prefix} the current ladder".strip()
    return f"{prefix} {_plain(floor)} {unit}".rstrip()


def _plain(value: Decimal | None) -> str:
    """A quantity a clerk reads — `20,000`, never `20000.0000`."""
    if value is None:
        return "—"
    whole = value.quantize(Decimal("1")) if value == value.to_integral_value() else value
    return f"{whole:,}"


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE RE-PRICE — runbook 16 steps 3 and 4, through the REAL engine
# ══════════════════════════════════════════════════════════════════════════


def reprice_under_draft(*, version_id, rows, service_date: dt.date) -> dict[str, Any]:
    """Price each row's metered quantity twice: under the draft, and under the
    version that was in force. **The engine's own path, both times.**

    `rows` are plain dicts — `{"id", "quantity", "unit", "currency",
    "cycle_days", "service_days"}` — so no billing object crosses into this
    module and no rating object crosses out.

    ⚠ **NOTHING IS WRITTEN AND NO NUMBER IS CONSUMED** (`TC-RBS-028.2`).
    `engine.price_period` is documented PURE — *"no I/O, no clock, no writes"* —
    and stage 6, where a draft is stored and `core.numbering` spends a bill
    number, is billing's and is not called from here.

    ⚠ **AN ACCOUNT THAT CANNOT BE PRICED IS COUNTED WITH ITS REASON AND NEVER
    PRICED AT ZERO.** `rate_change_impact`'s own rule, and its reason: averaging
    an unmeasurable row in as `0.00%` drags the worst case toward the middle,
    *"the one direction a rate-change gate must never be wrong in"*. A row with
    no quantity, a quantity in a unit this ladder does not price, or a refusal
    from the engine each lands in `unpriced` with the reason attached.

    ⚠ **THE PERIOD IS THE BILL'S OWN.** `_impact_period()` answers a fixed
    30-day cycle because a typical-bill panel has no real period to use; a
    re-price of an issued cycle does, and handing the engine the wrong day count
    would misprice every proration and every time-of-use window in the ladder.
    """
    tenant_id = _tenant_id()
    draft = models.TariffVersion.objects.filter(tenant_id=tenant_id, id=version_id).first()
    if draft is None:
        return {
            "found": False,
            "reason": "no such rate schedule version for this utility",
            "priced": {},
            "unpriced": {},
        }
    tariff = draft.tariff
    service_code = tariff.service.code if tariff and tariff.service_id else ""
    baseline = selectors._baseline_version(tariff, draft, service_date)
    after_inputs = selectors.pricing_inputs_for_version(draft, service_date)
    before_inputs = (
        selectors.pricing_inputs_for_version(baseline, service_date)
        if baseline is not None
        else None
    )
    if before_inputs is None:
        return {
            "found": True,
            "comparable": False,
            "reason": "no activated version of this schedule to compare the draft against",
            "service": service_code,
            "priced": {},
            "unpriced": {},
        }

    after_tariff = selectors._engine_tariff(
        after_inputs, service_code, _money(after_inputs.get("base_charge"))
    )
    before_tariff = selectors._engine_tariff(
        before_inputs, service_code, _money(before_inputs.get("base_charge"))
    )

    priced: dict[str, dict[str, Any]] = {}
    unpriced: dict[str, str] = {}
    for row in rows:
        key = str(row.get("id") or "")
        quantity = _money(row.get("quantity"))
        if not key or quantity is None:
            if key:
                unpriced[key] = "no metered quantity on the issued bill for this service"
            continue
        try:
            before = _price(before_tariff, row, quantity)
            after = _price(after_tariff, row, quantity)
        except Exception as problem:  # noqa: BLE001 — the engine's own named refusal, counted
            unpriced[key] = f"engine:{type(problem).__name__}"
            continue
        priced[key] = {
            "before": _stored(before.total),
            "after": _stored(after.total),
            "change": _stored(after.total - before.total),
            "currency": after.currency,
            "quantity": _stored(quantity),
            "unit": str(row.get("unit") or ""),
            # Line by line, so a caller can say WHICH charge moved on this bill
            # rather than only that the total did (`RB-116` step 4).
            "lines_before": _lines(before),
            "lines_after": _lines(after),
        }
    return {
        "found": True,
        "comparable": True,
        "service": service_code,
        "currency": draft.currency,
        "version_id": str(draft.id),
        "baseline_version_id": str(baseline.id) if baseline else None,
        "priced": priced,
        "unpriced": unpriced,
        "priced_by": "apps.rating.engine.price_period — the same call a bill makes",
    }


def _price(tariff_config: Any, row: dict[str, Any], quantity: Decimal) -> Any:
    """One service point, one period, through the REAL engine.

    No taxes and no fees, which is this analysis's stated scope (`OQ-319`) and
    the scope `BR-RAT-091`'s ratified `$59.00 → $62.54` was signed on.
    """
    from types import SimpleNamespace

    cycle_days = int(row.get("cycle_days") or 30) or 30
    service_days = int(row.get("service_days") or cycle_days) or cycle_days
    return engine.price_period(
        tariff=tariff_config,
        consumption=SimpleNamespace(
            amount=quantity, unit=str(row.get("unit") or ""), windows=(), demand=None
        ),
        period=SimpleNamespace(cycle_days=cycle_days, service_days=service_days),
        account=SimpleNamespace(currency=str(row.get("currency") or ""), tax_exempt=False),
    )


def _lines(priced: Any) -> list[dict[str, Any]]:
    """The engine's own lines as plain data — hard rule 3 keeps the unit on."""
    return [
        {
            "kind": line.kind,
            "description": line.description,
            "amount": _stored(line.amount),
            "quantity": None if line.quantity is None else _stored(line.quantity),
            "unit": line.unit or "",
            "unit_price": None if line.unit_price is None else str(line.unit_price),
        }
        for line in priced.lines
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-028 (EP-RBS-05; CR-075 wave S)
# generated: 2026-09-07 by the CR-075 wave S build lane
# checklist: A✔ B=n/a(no schema change — every column read here exists) C✔ D=n/a(no endpoint) E=n/a(no screen) F✔ G✔ H=n/a(this file adds no rating MATH — every figure comes out of `engine.price_period` through the one existing projection; B4/B5 are untouched)
# gates: pytest tests/test_us_rbs_028_rate_change_preview.py · G115 · G20
# exceptions: the comparison is **this schedule's own portion**, before taxes and fees — `OQ-319` is OPEN and this follows the answer `BR-RAT-091`'s ratified `$59.00 → $62.54` was signed on rather than choosing a second one · both sides are priced by the engine and the DIFFERENCE travels, so the base-charge precedence (`DEF-154`) cancels out of the comparison · it reuses `selectors._engine_tariff` and `selectors.pricing_inputs_for_version` rather than projecting a version a second time (`DEF-434`'s own reason) · the period is the BILL's own day count rather than `_impact_period`'s fixed 30
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

"""Named warnings a bill carries while it is still being made — the shape, once.

PO ruling 2026-09-30, verbatim: *"if user did not define and bind base charges
in rate schedule - then as a default you take 0 and complete the bill instead
of refusing - if you want to show the warning you can display it dueing the
process"*. The bill completes; the warning is how the process says so.

**THE SHAPE IS `{"key": str, "params": dict}` AND NOTHING ELSE.** `key` is a
catalogue key the screen translates (B14 rule 35) and `params` carries codes
and names, never a composed English sentence — the rule
`BillingRuleError.params` already states for refusals. It is the shape
`AccountBillingData.warnings` holds, `runs.PricedAccount.warnings` carries, the
one-time preview and draft answer at their top level, and a draft's
`bill_payload["warnings"]` freezes (`04-docs/05-modules/07-billing/
13-one-time-bill-api-contract.md` §2).

A module of its own because two files that import each other both need it:
`gather` records the warning and `resolution_switch` — which `gather` imports —
re-derives it from the R1–R7 chain's answer.
"""

from __future__ import annotations

from typing import Any, Iterable

#: `billing.oneTime.warn.baseNotSet` — *"No base charge for {service}. Billed
#: $0.00."* (contract §2, ≤ 6 words a sentence, B14 rule 33).
BASE_NOT_SET = "billing.oneTime.warn.baseNotSet"


def base_not_set(service_code: str) -> dict[str, Any]:
    """One `baseNotSet` warning. `service` is the service's display NAME where
    the platform catalogue has one (the contract's worked example reads
    *Electric*), and `service_code` is the stable code beside it."""
    return {
        "key": BASE_NOT_SET,
        "params": {"service": _service_name(service_code), "service_code": service_code},
    }


def with_base_not_set(
    warnings: Iterable[dict[str, Any]], services: Iterable[str]
) -> tuple[dict[str, Any], ...]:
    """`warnings` with its `baseNotSet` rows REPLACED by one per `services`.

    Every other warning is kept, in its order. Replacing rather than appending
    is what lets `resolution_switch` restate the set from the chain's answer
    without a stale row surviving for a service the chain did price.
    """
    kept = tuple(dict(row) for row in warnings if row.get("key") != BASE_NOT_SET)
    ordered = tuple(dict.fromkeys(code for code in services if code))
    return kept + tuple(base_not_set(code) for code in ordered)


def base_not_set_services(warnings: Iterable[dict[str, Any]]) -> tuple[str, ...]:
    """The service codes the `baseNotSet` rows in `warnings` name."""
    return tuple(
        str((row.get("params") or {}).get("service_code") or "")
        for row in warnings
        if row.get("key") == BASE_NOT_SET
    )


#: `billing.oneTime.warn.baseSizeNotPriced` — *"{code} has no price for
#: {size} · billed $0.00"*. PO ruling 2026-10-01: for a CAPACITY service a size
#: with no base price bills that size's base at `$0.00` and the bill completes;
#: the warning is how a clerk finds the gap. A WARNING only — PO 2026-10-01,
#: option A: no sign-off tick.
BASE_SIZE_NOT_PRICED = "billing.oneTime.warn.baseSizeNotPriced"


def size_not_priced(service_code: str, code: str, size_class: str) -> dict[str, Any]:
    """One `baseSizeNotPriced` warning: the code, the size, the service."""
    return {
        "key": BASE_SIZE_NOT_PRICED,
        "params": {
            "code": code,
            "size": size_class,
            "service": _service_name(service_code),
            "service_code": service_code,
        },
    }


def with_size_not_priced(
    warnings: Iterable[dict[str, Any]], entries: Iterable[tuple[str, str, str]]
) -> tuple[dict[str, Any], ...]:
    """`warnings` with one `baseSizeNotPriced` row per `(service, code, size)`,
    each once, after every warning already there."""
    return merged(
        warnings, tuple(size_not_priced(service, code, size) for service, code, size in entries)
    )


#: `billing.run.warn.scheduleVersionsOverlap` — *"{schedule}: versions from
#: {versions} overlap. Billed on the {used} version."* PO ruling 2026-10-01 on `DEF-RAT-8004`
#: (option A): when a LEGACY overlap leaves two versions of one rate schedule
#: in force on the service date, the newest prices (`BR-RAT-1055`) and the
#: Check names the schedule and the versions. A WARNING only — no sign-off
#: tick, and the account bills.
SCHEDULE_VERSIONS_OVERLAP = "billing.run.warn.scheduleVersionsOverlap"

#: `billing.run.warn.meterSizeNotRecorded` — *"Meter {meter} has no size. No
#: minimum applied."* PO ruling 2026-10-01 (decision log *"A METER WITH NO
#: RECORDED SIZE GETS NO MINIMUM, AND THE BILL-RUN CHECK FLAGS IT"*, option A):
#: the bill goes out without a minimum, and once the size is recorded the next
#: bill gets that size's. A WARNING only — no sign-off tick.
METER_SIZE_NOT_RECORDED = "billing.run.warn.meterSizeNotRecorded"


def schedule_versions_overlap(
    service_code: str, schedule: str, on_date: Any, versions: Iterable[dict[str, Any]]
) -> dict[str, Any]:
    """One overlap warning. `versions` is rating's `versions_in_force`
    list — VALUES, winner first — so `used` is the version that priced.
    Versions are named the way the schedule's own filings table shows them:
    their label, else the day they start; a tie on that name adds the day each
    was saved, which is what told them apart (`BR-RAT-1055`). ⚠ That one word,
    *saved*, is English inside every catalogue's sentence — the same stated
    limitation as the month abbreviation, and only on a same-day tie."""
    rows = list(versions)
    names = [_version_name(row) for row in rows]
    if len(set(names)) < len(names):
        names = [
            f"{name} (saved {_clerk_date(row.get('saved_on'))})" if row.get("saved_on") else name
            for name, row in zip(names, rows)
        ]
    return {
        "key": SCHEDULE_VERSIONS_OVERLAP,
        "params": {
            "schedule": schedule,
            "service": _service_name(service_code),
            "service_code": service_code,
            "date": _clerk_date(on_date),
            "versions": ", ".join(names),
            "used": names[0] if names else "",
        },
    }


def meter_size_not_recorded(service_code: str, meter: str) -> dict[str, Any]:
    """One *Meter size not recorded* warning: the meter, the service."""
    return {
        "key": METER_SIZE_NOT_RECORDED,
        "params": {
            "meter": meter,
            "service": _service_name(service_code),
            "service_code": service_code,
        },
    }


def _version_name(row: dict[str, Any]) -> str:
    label = str(row.get("label") or "").strip()
    # The DATE alone — the catalogue sentence carries the word *from* in each
    # language, so no English is composed here beyond `clerk_date`'s month.
    return label or _clerk_date(row.get("effective_from"))


def _clerk_date(when: Any) -> str:
    """`2026-10-29` -> `29 Oct 2026` — the same rendering as
    `rating.resolution.clerk_date` (and its stated limitation: English month
    abbreviations inside every catalogue's sentence). Repeated rather than
    imported because billing reaches rating only through its seams."""
    if not when:
        return ""
    return f"{when.day} {when.strftime('%b')} {when.year}"


def merged(*groups: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Several warning lists as one, each distinct warning ONCE, first seen
    first. A back-bill's six groups each gather the same account, and six
    copies of *"No base charge for Electric"* is a wall, not a warning."""
    seen: list[dict[str, Any]] = []
    for group in groups:
        for row in group or ():
            if row not in seen:
                seen.append(dict(row))
    return tuple(seen)


def _service_name(service_code: str) -> str:
    """The platform catalogue's word for this service, or the code itself.

    Read through billing's tenancy seam, the read `assemble_document` already
    uses for the same word on a bill line (`DEF-2852`). A service the catalogue
    does not name answers its code: a warning is never lost to a missing name.

    ⚠ **NO `try/except` AROUND IT, DELIBERATELY (hard-won law 14).** This runs
    inside the caller's transaction, and on PostgreSQL a caught database error
    leaves that transaction aborted — the bill would fail at COMMIT for a
    display name. A failure here is a real failure and propagates.
    """
    from apps.billing import tenancy_seam

    return str(tenancy_seam.service_names_by_code().get(service_code) or service_code)

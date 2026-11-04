# ── Trace ──────────────────────────────────────────────
# Change:   CR-030 W3 task 3.8 — the ACC-01 **Usage** tab. Design:
#           04-docs/02-decisions/18-cr030-onboarding-design.md §5.2.2.
#           Screens: S21 (Usage tab)
# Story:    US-CUS-011 (the S21 operational tabs)
# Rules:    BR-MET-106 (computed from reads, STORED, RESTATED never edited,
#           ABSENT when unread, estimates counted and marked — PO 2026-08-24) ·
#           BR-MET-028 (an estimate carries consumption and no current_value) ·
#           BR-TEN-057 (the sample tag lives on the owning row) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 3 (explicit unit) ·
#           rule 4 (corrections are new rows) · rule 6 (idempotency)
# Questions: OQ-358 (a month whose reads disagree about the unit)
# Tests:    06-backend/tests/test_br_met_106_monthly_usage.py
# Impacts:  apps/metering/monthly_usage.py (the rules) ·
#           apps/metering/monthly_usage_reads.py (the read model) ·
#           apps/metering/api.py (`GET /accounts/{id}/usage`)
# ───────────────────────────────────────────────────────
"""BR-MET-106 — the monthly-usage WRITE path. The SOLE writer of one table.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — the idempotency key is a CLAUDE.md 🔒
path. AI-authored 2026-08-24 under the PO ruling of 2026-08-09; the ledger row
is written to this lane's scratchpad because
`12-governance/09-human-review-ledger.md` belongs to another lane today, and is
REPORTED for the orchestrator to land.

Nothing else in this repo may write `meter_read_monthly_usage`. The read model
next door is read-only; the endpoint is thin; `sample_data.py` does not seed it.

────────────────────────────────────────────────────────────────────────────
WHAT A RECOMPUTE DOES, AND WHY IT NEVER DOUBLE-WRITES
────────────────────────────────────────────────────────────────────────────
`recompute_account(...)` walks the account's read LINEAGE HEADS (the rows with
no `superseded_by_id` — the same set `meter_reads`' own unique constraint is
scoped to), buckets them by service and calendar month, and for each bucket
asks `monthly_usage.summarise` for the figure. Then, per month:

  * **the head's fingerprint matches** → nothing is written, nothing is
    audited, and the existing row is returned. This is CLAUDE.md rule 6 for a
    computation nobody submits a key for: the key is the CONTENT (sorted
    lineage-head ids + quantity + unit + estimate count, SHA-256). Running the
    recompute a hundred times over unchanged reads leaves exactly one row.
  * **the fingerprint differs** → the head is SUPERSEDED (its
    `superseded_by_id` + `superseded_at` set, which is the one UPDATE B2 r8
    permits on this shape) and a NEW row is inserted. **This is BR-MET-106's
    *"corrections RESTATE, they never edit"* and CLAUDE.md hard rule 4: the old
    statement survives, carrying the `computed_at` and the read ids it was
    true for, and the chart reads the head.**
  * **there is no head and there are reads** → a first row is inserted.
  * **there is a head and the reads are GONE** → the head is superseded with
    `reason="reads_withdrawn"` and NO replacement is written, because
    BR-MET-106 says an unread month is ABSENT and a zero row would claim the
    meter was read and did not move.

────────────────────────────────────────────────────────────────────────────
THE ONE CASE THAT REFUSES, BY NAME
────────────────────────────────────────────────────────────────────────────
**OQ-358** — one account, one service, one month, two units. `summarise`
raises and this module lets it propagate: the prime directive says implement to
the boundary and stub the gap, and silently picking a unit would change a
customer's number without anyone deciding to.

────────────────────────────────────────────────────────────────────────────
WHAT IT NEVER DOES
────────────────────────────────────────────────────────────────────────────
* **It never writes outside `metering`.** `accounts` and `services` are read
  through their ids only; no row in `customers` or `tenancy` is touched
  (CLAUDE.md module map, B2 §2).
* **It never posts to the ledger and never touches money.** A consumption is
  not an amount; rule 2's 4-dp law governs money columns and not this one.
* **It never invents a month.** A month with no reads gets no row, ever.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable, Sequence

from django.db import transaction
from django.utils import timezone

from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.dbfields import uuid7

from apps.metering import models, monthly_usage as rules
from apps.metering.monthly_usage_asset import HEAD_FILTER, AssetMonthlyUsage

_USAGE = models.MonthlyUsage
_ASSET_USAGE = AssetMonthlyUsage
_READ = models.MeterRead

#: **THE REGISTERS A CONSUMPTION SUM MUST NEVER TOUCH — DEF-798, declared ONCE.**
#:
#: `models.NON_CONSUMPTION_CHANNELS` is the named set and it holds `export`
#: (BR-AST-029) and `generation` (BR-MET-135). **`demand` is deliberately NOT in
#: it**, because that tuple exists for registers that measure a DIFFERENT
#: DIRECTION of energy, and a demand register measures the same energy's peak
#: RATE — `selectors._channel_quantities` therefore handles it as its own
#: dimension on the money path rather than as an exclusion.
#:
#: For a consumption SUM the distinction does not matter and the answer is the
#: same: BR-RAT-014's demand figure is a delta between two maxima in kW, nobody
#: consumed it, and DEF-798's measured 14 is exactly that number landing in a
#: kWh total. So the sum's exclusion set is the named tuple PLUS demand, and it
#: is composed here — one name, imported by every reader (`asset_usage.py` is
#: the second), so a register minted tomorrow joins one line and not three.
NEVER_CONSUMPTION: tuple[str, ...] = models.NON_CONSUMPTION_CHANNELS + (models.CHANNEL_DEMAND,)

#: The action codes this module writes to `audit_log` (BR-AUD-003 dotted form).
ACTION_STATED = "monthly_usage.stated"
ACTION_RESTATED = "monthly_usage.restated"
ACTION_WITHDRAWN = "monthly_usage.withdrawn"

#: The same three, one grain finer (BR-MET-141, OQ-421 ruled 2026-08-27). A
#: SEPARATE entity_type rather than the same one with an extra column: an
#: auditor asking *"who restated Sarah's July?"* must not be handed a meter's
#: demand register in the same list as her account's energy total.
ASSET_ACTION_STATED = "asset_monthly_usage.stated"
ASSET_ACTION_RESTATED = "asset_monthly_usage.restated"
ASSET_ACTION_WITHDRAWN = "asset_monthly_usage.withdrawn"


# ── OQ-358, AND WHAT A CALLER MAY DO WITH IT (`OQ-690`, closed 2026-09-05) ───
@dataclass(frozen=True)
class UnrestatedMonth:
    """One (service, month) — or (asset, register, month) — left as it was.

    ⚠ **THIS IS NOT AN ERROR TYPE AND IT IS NOT A FAILURE.** It is the record
    that a month was DELIBERATELY not restated because `OQ-358` has no answer
    yet, so its stored figure still says whatever it last legitimately said and
    the reads it could not summarise are on file and unaffected.

    `question` is carried as a STRING and is always `"OQ-358"` today. It is a
    field rather than a constant so a receipt can print the id without the
    screen having to know which question was hit — the clerk sees the sentence,
    the id is there for whoever goes looking (`CR-016`).
    """

    grain: str  #: "account" or "asset"
    account_id: str
    period_month: date
    reason: str
    question: str = "OQ-358"
    service_id: str | None = None  #: set on the account grain
    asset_id: str | None = None  #: set on the asset grain
    channel: str | None = None  #: the register, on the asset grain


def _hold_month(
    problems: list[UnrestatedMonth] | None,
    refusal: rules.MixedUnitMonth,
    **fields: Any,
) -> None:
    """Record a month as un-restated, or RE-RAISE when nobody asked to collect.

    ⚠ **THE DEFAULT IS STILL THE REFUSAL, AND THAT IS DELIBERATE.** A caller
    that passes no `problems` list gets exactly the behaviour this module has
    had since 2026-08-24: `MixedUnitMonth` propagates, `recompute_account`'s
    own `@transaction.atomic` rolls the whole recompute back, and nothing is
    written (`test_br_met_106_tc7`). **Tolerating the refusal is OPT-IN, per
    caller**, because the three callers that opt in — the read commit, the
    read-correction path and the backfill command — are the three the PO's
    rules cover, and a lane wiring a fourth should have to think about it.

    ⚠ **NO SAVEPOINT IS NEEDED HERE AND ONE WOULD BE CARGO CULT — read this
    before "fixing" it (CLAUDE.md hard-won law 14).** Law 14 applies to code
    that catches a DATABASE error and carries on: on PostgreSQL a failed
    statement aborts the transaction, so the next query raises and the work is
    lost at COMMIT. **`MixedUnitMonth` is raised by `monthly_usage.summarise`,
    which is PURE PYTHON** — it compares `unit` strings on `ReadFact` objects
    that were fetched before the loop began and issues no statement of its own.
    So when this function is reached, **no statement has failed and the
    transaction is healthy.** The savepoint that law 14 *does* require on this
    path is already present and is `recompute_account`'s own `@transaction
    .atomic` decorator: when a genuine database error escapes one account's
    recompute, that decorator rolls back to its savepoint and leaves the
    connection usable for the next account. **Do not remove that decorator.**
    """
    if problems is None:
        raise refusal
    problems.append(UnrestatedMonth(reason=str(refusal), **fields))


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _audit(
    actor: Any, action: str, row: Any, *, entity_type: str = "monthly_usage", **kw: Any
) -> None:
    """CLAUDE.md rule 7 is written about MONEY actions and this is not one.

    The row is written anyway, and the reason is BR-MET-106's own: a restated
    month changes a number a customer has already been shown, and *who
    recomputed it and when* is the only way to answer "this used to say 612".
    The per-meter grain (BR-MET-141) carries the same obligation for the same
    reason, under its own `entity_type`.
    """
    core_audit.write_row(
        action=action,
        entity_type=entity_type,
        entity_id=row.id,
        actor_user_id=_actor_id(actor),
        before=kw.get("before"),
        after=kw.get("after"),
    )


def _snapshot(row: models.MonthlyUsage) -> dict[str, Any]:
    return {
        "account_id": str(row.account_id),
        "service_id": str(row.service_id),
        "period_month": row.period_month.isoformat(),
        "quantity": str(row.quantity),
        "unit": row.unit,
        "read_count": row.read_count,
        "estimated_read_count": row.estimated_read_count,
        "source_fingerprint": row.source_fingerprint,
    }


def _asset_snapshot(row: AssetMonthlyUsage) -> dict[str, Any]:
    """The same fields one grain finer, plus the two that MAKE it finer."""
    return {
        "account_id": str(row.account_id),
        "asset_id": str(row.asset_id),
        "channel": row.channel,
        "service_id": None if row.service_id is None else str(row.service_id),
        "period_month": row.period_month.isoformat(),
        "quantity": str(row.quantity),
        "unit": row.unit,
        "read_count": row.read_count,
        "estimated_read_count": row.estimated_read_count,
        "source_fingerprint": row.source_fingerprint,
    }


# ── reading the reads ───────────────────────────────────────────────────────
def _fact_rows(
    tenant_id: Any, *, account_id: Any = None, asset_id: Any = None
) -> list[tuple[rules.ReadFact, Any]]:
    """Every lineage-HEAD read, as `(ReadFact, service_id)` pairs. ONE query.

    ⚠ **THIS IS THE SINGLE PLACE A ROW BECOMES A `ReadFact` IN THIS PRODUCT,
    AND THAT IS OQ-421'S ONE CONSTRAINT IN CODE.** The PO's ruling of
    2026-08-27 stores the twelve-month figure per METER as well as per account,
    and the decision log attaches one thing the build may not do: *"the stored
    per-meter row must be produced by the SAME functions the computed figure
    uses, not a second implementation — otherwise the account total and the
    meter total can disagree and no test would say which is right."*

    Two grains, two groupings, **one query and one construction**: the account
    grain groups these pairs by SERVICE (`_read_facts`) and the meter grain
    groups the same pairs by (ASSET, CHANNEL) (`asset_channel_facts`). Neither
    can see a read the other cannot, and neither can read a field differently.

    Tenant-scoped explicitly (hard rule 1) even though RLS is FORCEd — the
    app-layer filter and the database policy are two independent defences and
    the isolation suite proves each separately.

    `superseded_by_id__isnull=True` is what makes a correction a RESTATEMENT
    rather than a double count: a superseded read is history, and its
    replacement is the row that carries the corrected consumption.

    ⚠ The service is resolved by the join `asset → service_point → service`,
    the same one `selectors.reads_list` already filters on. It is returned
    BESIDE the fact rather than filtered on here, because the two grains treat
    a NULL differently and each says so where it groups.
    """
    # BR-MET-1189 (PO 2026-10-04, DEF-WRK-9642): where one register holds two
    # readings on one date, usage counts ONE — the highest approved and
    # validated (`counted_reading`). Summing both would double the day.
    from apps.metering import counted_reading

    qs = counted_reading.only_counted(
        _READ.objects.filter(tenant_id=tenant_id).filter(superseded_by_id__isnull=True)
    )
    if account_id is not None:
        qs = qs.filter(account_id=account_id)
    if asset_id is not None:
        qs = qs.filter(asset_id=asset_id)

    rows = qs.values_list(
        "id",
        "read_at",
        "consumption",
        "unit",
        "status",
        "asset__service_point__service_id",
        "asset_id",
        "channel",
        *_COVERAGE_FIELDS,
    )
    pairs: list[tuple[rules.ReadFact, Any]] = []
    for (
        read_id,
        read_at,
        consumption,
        unit,
        status,
        service_id,
        row_asset_id,
        channel,
        *coverage,
    ) in rows:
        pairs.append(
            (
                rules.ReadFact(
                    read_id=str(read_id),
                    read_at=read_at,
                    consumption=consumption,
                    unit=unit,
                    # BR-MET-028: an estimate is a STATUS, and it carries
                    # consumption with no `current_value`. Both are checked, so
                    # a row that lost its status but never had a register value
                    # is still marked rather than silently counted as an actual.
                    is_estimate=(status == "estimated"),
                    # DEF-798 — WHICH REGISTER. Without these two the sum below
                    # is register-blind: a kW peak-delta lands in the kWh energy
                    # total and a TOU meter's windows are counted on top of its
                    # own `total`. See `select_consumption_facts`.
                    asset_id=str(row_asset_id),
                    channel=channel,
                    **_coverage_of(status, read_at, *coverage),
                ),
                service_id,
            )
        )
    # 🔒 DEF-MET-10163 (PO 2026-10-15, *"go with 1 and 3"*) — an estimate a
    # LATER actual on the same meter and register already counts is left out of
    # BOTH grains' sums, here, at the one place a row becomes a fact (OQ-421's
    # constraint: one construction for the account and the meter grain). The
    # rows themselves are untouched (hard rule 4). See `rules.covered_estimate_ids`.
    covered = _covered_estimates(tenant_id, [fact for fact, _ in pairs])
    if covered:
        pairs = [(fact, service_id) for fact, service_id in pairs if fact.read_id not in covered]
    return pairs


def with_estimate_holders(account_ids: Sequence[Any]) -> list[Any]:
    """`account_ids` plus every OTHER account holding an estimate on their meters.

    🔒 DEF-MET-10163 — the trigger half. When an actual reading is posted, the
    estimate it now covers must leave its month's sum, and `recompute_account`
    restates every month of an account, so the estimate's month moves with the
    actual's whenever both are one account's. They are not always: the actual
    can be the next occupant's reading on the same meter. Those accounts are
    added here — over-inclusively, which is free, because a recompute over
    unchanged reads writes nothing (rule 6). Order kept, the given ids first.
    """
    given = [str(one) for one in account_ids if one]
    if not given:
        return given
    tenant_id = _tenant_id()
    assets = (
        _READ.objects.filter(tenant_id=tenant_id, account_id__in=given)
        .filter(superseded_by_id__isnull=True)
        .exclude(status="estimated")
        .values_list("asset_id", flat=True)
        .distinct()
    )
    others = (
        _READ.objects.filter(tenant_id=tenant_id, asset_id__in=assets, status="estimated")
        .filter(superseded_by_id__isnull=True)
        .exclude(account_id=None)
        .exclude(account_id__in=given)
        .values_list("account_id", flat=True)
        .distinct()
    )
    return list(dict.fromkeys([*given, *(str(one) for one in others)]))


#: The three columns `rules.covered_estimate_ids` needs from an actual reading.
_COVERAGE_FIELDS = ("period_start", "days_since_prior", "trues_up_read_ids")


def _coverage_of(
    status: Any, read_at: Any, period_start: Any, days_since_prior: Any, trues_up_read_ids: Any
) -> dict[str, Any]:
    """`measured_from` and `trues_up` for one row (DEF-MET-10163).

    The day an actual measures FROM is its stored `period_start` — the prior
    reading's date, which every read path writes. A row with no `period_start`
    falls back to `read_at − days_since_prior`; with neither, the row covers
    nothing, because an unknown interval is never assumed to span an estimate.
    An estimate gets neither field: it covers nothing.
    """
    if status == "estimated":
        return {}
    measured_from = period_start
    if measured_from is None and days_since_prior is not None:
        measured_from = read_at.date() - timedelta(days=int(days_since_prior))
    return {
        "measured_from": measured_from,
        "trues_up": frozenset(str(one) for one in (trues_up_read_ids or ())),
    }


def _covered_estimates(tenant_id: Any, facts: list[rules.ReadFact]) -> set[str]:
    """The ids among `facts` a later actual reading covers (DEF-MET-10163).

    ⚠ **THE COVERING ACTUALS ARE READ BY METER, NOT TAKEN FROM `facts`.**
    `facts` is one ACCOUNT's (or one meter's) reads, and the actual covering an
    estimate's days can sit under the next occupant's account on the same
    meter — those days are still counted once already. So ONE more query, and
    only when the set holds an estimate at all, reads every counted actual head
    on those meters dated after the earliest estimate. Tenant-scoped explicitly
    as well as by RLS (hard rule 1).
    """
    estimates = [fact for fact in facts if fact.is_estimate]
    if not estimates:
        return set()
    from apps.metering import counted_reading

    qs = (
        counted_reading.only_counted(
            _READ.objects.filter(tenant_id=tenant_id).filter(superseded_by_id__isnull=True)
        )
        .filter(
            asset_id__in=sorted({fact.asset_id for fact in estimates}),
            read_at__gt=min(fact.read_at for fact in estimates),
            consumption__isnull=False,
        )
        .exclude(status="estimated")
    )
    actuals = [
        rules.ReadFact(
            read_id=str(read_id),
            read_at=read_at,
            consumption=consumption,
            unit=unit,
            is_estimate=False,
            asset_id=str(asset_id),
            channel=channel,
            **_coverage_of(status, read_at, *coverage),
        )
        for read_id, read_at, consumption, unit, status, asset_id, channel, *coverage in (
            qs.values_list(
                "id", "read_at", "consumption", "unit", "status", "asset_id", "channel",
                *_COVERAGE_FIELDS,
            )
        )
    ]
    return rules.covered_estimate_ids(estimates, actuals)


def _read_facts(tenant_id: Any, account_id: Any) -> dict[Any, list[rules.ReadFact]]:
    """The ACCOUNT grain: the account's reads, bucketed by service id.

    ⚠ A read whose asset has no service point yields a NULL service and is
    DROPPED: it belongs to no service, so it can be in no service's month, and
    inventing a bucket for it would put an unattributed number on a customer's
    chart. The METER grain keeps that same read (see `asset_channel_facts`),
    because it still belongs to a meter — the divergence is deliberate and is
    the one place the two grains do not see the same set.
    """
    buckets: dict[Any, list[rules.ReadFact]] = {}
    for fact, service_id in _fact_rows(tenant_id, account_id=account_id):
        if service_id is None:
            continue
        buckets.setdefault(service_id, []).append(fact)
    # DEF-798 — the selection happens ONCE, here, on the way IN, so every
    # figure this module stores and every metric read off it is over the same
    # set. Doing it in `summarise` instead would leave `read_count` counting
    # rows the quantity did not include.
    return {
        service_id: rules.select_consumption_facts(
            facts,
            total_channel=models.CHANNEL_TOTAL,
            tou_windows=models.TOU_WINDOW_CHANNELS,
            never_consumption=NEVER_CONSUMPTION,
        )
        for service_id, facts in buckets.items()
    }


@dataclass(frozen=True)
class AssetChannelBucket:
    """One meter's ONE REGISTER, with the service it hangs off and its reads."""

    asset_id: str
    channel: str
    service_id: Any
    facts: list[rules.ReadFact]


def asset_channel_facts(
    *, account_id: Any = None, asset_id: Any = None
) -> dict[tuple[str, str], AssetChannelBucket]:
    """The METER grain: the same reads, bucketed by (asset, register).

    ⚠ **`select_consumption_facts` IS NOT APPLIED HERE, AND THE REASON IS THE
    OPPOSITE OF A SHORTCUT.** That function decides what a single SUM may
    contain — total OR the TOU windows, never both, and never a
    never-consumption register. **Nothing at this grain sums across registers
    at all**: the register is part of the key. So every register is published
    and stored on its own terms, and whether it counts as consumption is
    STATED beside it (derived from `NEVER_CONSUMPTION`) rather than used to
    hide it. A clerk looking at a demand meter must see its peak, clearly
    labelled — not an empty chart.

    That is also why DEF-798's measured 698 kWh is not representable at this
    grain: 684 (`total`) and 14 (`demand`) are two buckets and there is no code
    path that could add them.
    """
    tenant_id = _tenant_id()
    buckets: dict[tuple[str, str], AssetChannelBucket] = {}
    for fact, service_id in _fact_rows(tenant_id, account_id=account_id, asset_id=asset_id):
        key = (fact.asset_id, fact.channel)
        bucket = buckets.get(key)
        if bucket is None:
            bucket = AssetChannelBucket(
                asset_id=fact.asset_id, channel=fact.channel, service_id=service_id, facts=[]
            )
            buckets[key] = bucket
        bucket.facts.append(fact)
    return buckets


def _sample_flags(tenant_id: Any, account_id: Any) -> dict[str, bool]:
    """`read_id → is_sample`, so BR-TEN-057's tag can be inherited."""
    rows = _READ.objects.filter(tenant_id=tenant_id, account_id=account_id).values_list(
        "id", "is_sample"
    )
    return {str(read_id): bool(flag) for read_id, flag in rows}


# ── the writer ──────────────────────────────────────────────────────────────
@transaction.atomic
def recompute_account(
    account_id: Any,
    *,
    actor: Any = None,
    only_services: Iterable[Any] | None = None,
    problems: list[UnrestatedMonth] | None = None,
) -> dict[str, int]:
    """Restate every month this account's reads support. Idempotent.

    Returns the counts a caller can assert on: `{"stated", "restated",
    "unchanged", "withdrawn"}`. A second call over unchanged reads returns
    `unchanged` equal to the first call's `stated` and writes nothing.

    No `@require_role`: this is a DERIVATION over rows the caller can already
    read, it changes no money and grants nobody anything. The endpoint that
    triggers it is gated (`AnyTenantRole`), and the read model beside it serves
    only what `GET /accounts/{id}` already serves.
    """
    tenant_id = _tenant_id()
    now = timezone.now()
    wanted = {str(s) for s in only_services} if only_services is not None else None

    by_service = _read_facts(tenant_id, account_id)
    sample = _sample_flags(tenant_id, account_id)
    counts = {"stated": 0, "restated": 0, "unchanged": 0, "withdrawn": 0}

    # Every (service, month) that HAS reads …
    seen: set[tuple[Any, date]] = set()
    for service_id, facts in by_service.items():
        if wanted is not None and str(service_id) not in wanted:
            continue
        for period_month, month_reads in rules.group_by_month(facts).items():
            # ⚠ **`seen` IS ADDED TO BEFORE THE SUMMARY IS ATTEMPTED, AND THAT
            # ORDERING IS LOAD-BEARING FOR THE `OQ-358` CASE.** `seen` drives
            # the withdrawal sweep below — *"every head whose reads have GONE"*.
            # A month that cannot be summarised has NOT lost its reads; they are
            # on file and they disagree. Leaving it in `seen` is what makes the
            # month keep its previous statement instead of being withdrawn to
            # ABSENT, which would turn an unanswered question into a claim that
            # the customer was never read (BR-MET-106 reserves absence for
            # exactly one meaning).
            seen.add((service_id, period_month))
            try:
                figure = rules.summarise(period_month, month_reads)  # may raise OQ-358
            except rules.MixedUnitMonth as refusal:
                # `OQ-690` (CLOSED 2026-09-05): the month is left un-restated
                # and REPORTED, and every OTHER month of this account still
                # states. Before this, the exception escaped the loop and
                # `@transaction.atomic` rolled back the whole account.
                _hold_month(
                    problems,
                    refusal,
                    grain="account",
                    account_id=str(account_id),
                    service_id=str(service_id),
                    period_month=period_month,
                )
                continue
            if figure is None:
                continue
            outcome = _state_month(
                tenant_id,
                account_id,
                service_id,
                figure,
                actor=actor,
                now=now,
                is_sample=all(sample.get(rid, False) for rid in figure.source_read_ids),
            )
            counts[outcome] += 1

    # … and every head whose reads have GONE. BR-MET-106: the month becomes
    # ABSENT again, which means the head is superseded and NOT replaced.
    # ⚠ `superseded_at__isnull=True` as well as `superseded_by_id`: a month
    # already WITHDRAWN carries a NULL successor (there is no row to point at)
    # and must not be withdrawn a second time — without this clause every
    # recompute would re-withdraw it and write another audit row, which is
    # exactly the double-write rule 6 is here to stop.
    heads = _USAGE.objects.filter(
        tenant_id=tenant_id,
        account_id=account_id,
        superseded_by_id__isnull=True,
        superseded_at__isnull=True,
    )
    if wanted is not None:
        heads = heads.filter(service_id__in=list(wanted))
    for head in heads:
        if (head.service_id, head.period_month) in seen:
            continue
        _withdraw(head, actor=actor, now=now)
        counts["withdrawn"] += 1

    # ⚠ **THE METER GRAIN RIDES THE SAME TRIGGER, IN THE SAME TRANSACTION**
    # (BR-MET-141, OQ-421 ruled 2026-08-27). Not a second job and not a nightly
    # sweep: if the two grains could be recomputed independently they could be
    # stale relative to each other, and the S21 tab and the S50 strip would tell
    # one customer two different stories about one July. Its counts are NOT
    # merged into the returned dict — that dict is the account grain's and
    # `test_br_met_106_tc6` asserts it by equality; `recompute_account_assets`
    # returns its own and is separately callable.
    recompute_account_assets(account_id, actor=actor, problems=problems)

    return counts


def _state_month(
    tenant_id: Any,
    account_id: Any,
    service_id: Any,
    figure: rules.MonthFigure,
    *,
    actor: Any,
    now: Any,
    is_sample: bool,
) -> str:
    """Write, restate, or leave alone. Returns which of the three happened."""
    head = (
        _USAGE.objects.select_for_update()
        .filter(
            tenant_id=tenant_id,
            account_id=account_id,
            service_id=service_id,
            period_month=figure.period_month,
            superseded_by_id__isnull=True,
        )
        .first()
    )

    fingerprint = figure.fingerprint
    if head is not None and head.source_fingerprint == fingerprint:
        # CLAUDE.md rule 6. Nothing changed, so nothing is written — not even
        # `computed_at`, because a new timestamp on an unchanged figure is a
        # restatement that did not happen.
        return "unchanged"

    # ⚠ **THE SUCCESSOR'S ID IS ALLOCATED BEFORE EITHER WRITE, AND THE OLD HEAD
    # IS SUPERSEDED FIRST.** `uq_monthly_usage_head` is a PARTIAL unique over
    # the rows with a NULL successor, so inserting the new statement while the
    # old one is still a head puts two heads on one month for the length of one
    # statement — and the database refuses it. Found by TC-3 going RED with
    # `UNIQUE constraint failed: meter_read_monthly_usage.tenant_id, …` on the
    # first run; the ordering is what makes a RESTATEMENT legal where a second
    # simultaneous head is not.
    successor_id = uuid7()
    before = _snapshot(head) if head is not None else None
    if head is not None:
        # The ONE update B2 r8 permits on a committed row of this shape. The old
        # statement is NOT deleted and NOT edited: it keeps its quantity, its
        # unit and the read ids it was true for.
        _USAGE.objects.filter(pk=head.pk).update(
            superseded_by_id=successor_id, superseded_at=now, supersede_reason="reads_changed"
        )

    row = _USAGE.objects.create(
        id=successor_id,
        tenant_id=tenant_id,
        account_id=account_id,
        service_id=service_id,
        period_month=figure.period_month,
        quantity=figure.quantity,
        unit=figure.unit,
        read_count=figure.read_count,
        estimated_read_count=figure.estimated_read_count,
        source_read_ids=list(figure.source_read_ids),
        source_fingerprint=fingerprint,
        computed_at=now,
        is_sample=is_sample,
    )

    if head is None:
        _audit(actor, ACTION_STATED, row, after=_snapshot(row))
        return "stated"

    _audit(actor, ACTION_RESTATED, row, before=before, after=_snapshot(row))
    return "restated"


def _withdraw(head: models.MonthlyUsage, *, actor: Any, now: Any) -> None:
    """The month's reads are gone: the month goes back to being ABSENT.

    Superseded with no successor. `superseded_by_id` stays NULL — there is no
    row to point at — and `superseded_at` is what takes it out of the head set,
    which is why the partial unique is scoped on `superseded_by_id` while the
    read model filters on BOTH. Stated here because that asymmetry is the kind
    of thing a later lane 'tidies' into a bug.
    """
    before = _snapshot(head)
    _USAGE.objects.filter(pk=head.pk).update(superseded_at=now, supersede_reason="reads_withdrawn")
    _audit(actor, ACTION_WITHDRAWN, head, before=before)


# ═══════════════════════════════════════════════════════════════════════════
# THE METER GRAIN — BR-MET-141, OQ-421 as ruled 2026-08-27
# ═══════════════════════════════════════════════════════════════════════════
# PO verbatim: *"(b) Store it per meter too - otherwise we will ahve to
# calculate it again and again"*. The reason IS the requirement: recomputation
# cost. Everything below writes `meter_read_asset_monthly_usage` and NOTHING
# else in this repo may.
#
# ⚠ **THE SAME FUNCTIONS, NOT A SECOND IMPLEMENTATION.** The figure comes from
# `rules.group_by_month` + `rules.summarise` + `rules.fingerprint` — the exact
# three the account grain above calls and the S50 payload calls. The decision
# log makes that the one constraint on this build, because two derivations can
# disagree about one customer's number and no test could say which was right.


@transaction.atomic
def recompute_account_assets(
    account_id: Any,
    *,
    actor: Any = None,
    only_month: date | None = None,
    problems: list[UnrestatedMonth] | None = None,
) -> dict[str, int]:
    """Restate every (meter, register, month) this account's reads support.

    Same three-way outcome and the same content fingerprint as the account
    grain: `{"stated", "restated", "unchanged", "withdrawn"}`. Idempotent — a
    second call over unchanged reads writes nothing and audits nothing.

    Called by BOTH account-grain entry points so the two grains ALWAYS move
    together and can never be stale relative to each other, and exported so a
    test can prove the idempotency directly.

    ⚠ **`only_month` NARROWS THE WHOLE OPERATION, WITHDRAWALS INCLUDED**, and
    that is what makes it safe. `recompute_month` exists so a read correction
    can restate the month it touched without walking an account's whole
    history; a fan-out that ignored its scope would either walk everything
    anyway or — far worse — withdraw every OTHER month's heads as unseen. So
    the withdrawal sweep is filtered by the same value that filters the reads.
    """
    tenant_id = _tenant_id()
    now = timezone.now()
    sample = _sample_flags(tenant_id, account_id)
    counts = {"stated": 0, "restated": 0, "unchanged": 0, "withdrawn": 0}

    seen: set[tuple[str, str, date]] = set()
    for bucket in asset_channel_facts(account_id=account_id).values():
        for period_month, month_facts in rules.group_by_month(bucket.facts).items():
            if only_month is not None and period_month != only_month:
                continue
            # Same ordering, same reason as the account grain: a month that
            # cannot be summarised keeps its statement rather than being
            # withdrawn to ABSENT.
            seen.add((bucket.asset_id, bucket.channel, period_month))
            try:
                figure = rules.summarise(period_month, month_facts)  # may raise OQ-358
            except rules.MixedUnitMonth as refusal:
                # BR-MET-141's one constraint is that the two grains move
                # together. They still do: the SAME collector is threaded from
                # `recompute_account`, so a month held here is held there, and
                # the S21 tab and the S50 strip cannot tell one customer two
                # different stories about one July.
                _hold_month(
                    problems,
                    refusal,
                    grain="asset",
                    account_id=str(account_id),
                    asset_id=str(bucket.asset_id),
                    channel=bucket.channel,
                    period_month=period_month,
                )
                continue
            if figure is None:
                continue
            outcome = _state_asset_month(
                tenant_id,
                account_id,
                bucket,
                figure,
                actor=actor,
                now=now,
                is_sample=all(sample.get(rid, False) for rid in figure.source_read_ids),
            )
            counts[outcome] += 1

    # … and every head whose reads have GONE. BR-MET-106's *"an unread month is
    # ABSENT, never 0"* holds at this grain too: the head is superseded and NOT
    # replaced. `superseded_at__isnull=True` as well, so a month already
    # WITHDRAWN is not withdrawn a second time on every recompute.
    heads = _ASSET_USAGE.objects.filter(tenant_id=tenant_id, account_id=account_id, **HEAD_FILTER)
    if only_month is not None:
        heads = heads.filter(period_month=only_month)
    for head in heads:
        if (str(head.asset_id), head.channel, head.period_month) in seen:
            continue
        _withdraw_asset(head, actor=actor, now=now)
        counts["withdrawn"] += 1

    return counts


def _state_asset_month(
    tenant_id: Any,
    account_id: Any,
    bucket: AssetChannelBucket,
    figure: rules.MonthFigure,
    *,
    actor: Any,
    now: Any,
    is_sample: bool,
) -> str:
    """Write, restate, or leave alone. Returns which of the three happened."""
    head = (
        _ASSET_USAGE.objects.select_for_update()
        .filter(
            tenant_id=tenant_id,
            asset_id=bucket.asset_id,
            channel=bucket.channel,
            period_month=figure.period_month,
            superseded_by_id__isnull=True,
        )
        .first()
    )

    fingerprint = figure.fingerprint
    if head is not None and head.source_fingerprint == fingerprint:
        # CLAUDE.md rule 6. Nothing changed, so nothing is written — not even
        # `computed_at`, because a new timestamp on an unchanged figure is a
        # restatement that did not happen.
        return "unchanged"

    # ⚠ THE SUCCESSOR'S ID IS ALLOCATED BEFORE EITHER WRITE AND THE OLD HEAD IS
    # SUPERSEDED FIRST — `uq_asset_monthly_usage_head` is a PARTIAL unique over
    # the rows with a NULL successor, so inserting the new statement while the
    # old one is still a head puts two heads on one (meter, register, month)
    # and the database refuses it. The same ordering metering 0024's account
    # grain needed, for the same reason.
    successor_id = uuid7()
    before = _asset_snapshot(head) if head is not None else None
    if head is not None:
        _ASSET_USAGE.objects.filter(pk=head.pk).update(
            superseded_by_id=successor_id, superseded_at=now, supersede_reason="reads_changed"
        )

    row = _ASSET_USAGE.objects.create(
        id=successor_id,
        tenant_id=tenant_id,
        account_id=account_id,
        asset_id=bucket.asset_id,
        service_id=bucket.service_id,
        channel=bucket.channel,
        period_month=figure.period_month,
        quantity=figure.quantity,
        unit=figure.unit,
        read_count=figure.read_count,
        estimated_read_count=figure.estimated_read_count,
        source_read_ids=list(figure.source_read_ids),
        source_fingerprint=fingerprint,
        computed_at=now,
        is_sample=is_sample,
    )

    if head is None:
        _audit(
            actor,
            ASSET_ACTION_STATED,
            row,
            entity_type="asset_monthly_usage",
            after=_asset_snapshot(row),
        )
        return "stated"

    _audit(
        actor,
        ASSET_ACTION_RESTATED,
        row,
        entity_type="asset_monthly_usage",
        before=before,
        after=_asset_snapshot(row),
    )
    return "restated"


def _withdraw_asset(head: AssetMonthlyUsage, *, actor: Any, now: Any) -> None:
    """This register's reads for this month are gone: the month is ABSENT again.

    Superseded with NO successor — `superseded_by_id` stays NULL because there
    is no row to point at, and `superseded_at` is what takes it out of the head
    set. That asymmetry is why the partial unique is scoped on
    `superseded_by_id` while `HEAD_FILTER` names both.
    """
    before = _asset_snapshot(head)
    _ASSET_USAGE.objects.filter(pk=head.pk).update(
        superseded_at=now, supersede_reason="reads_withdrawn"
    )
    _audit(actor, ASSET_ACTION_WITHDRAWN, head, entity_type="asset_monthly_usage", before=before)


def asset_heads_for(
    asset_id: Any, *, channels: Sequence[str] | None = None
) -> list[AssetMonthlyUsage]:
    """The LIVE per-register statements for ONE METER — the S50 reader's query.

    Lives with the writer for the same reason `heads_for` does: the head
    predicate is the law this module enforces, and two copies of it is how the
    two halves start disagreeing about what "latest" means.
    """
    qs = _ASSET_USAGE.objects.filter(tenant_id=_tenant_id(), asset_id=asset_id, **HEAD_FILTER)
    if channels is not None:
        qs = qs.filter(channel__in=list(channels))
    return list(qs.order_by("channel", "period_month"))


@transaction.atomic
def recompute_month(
    account_id: Any,
    service_id: Any,
    period_month: date,
    *,
    actor: Any = None,
    problems: list[UnrestatedMonth] | None = None,
) -> str:
    """One month, for the callers that know exactly which one moved.

    Same idempotency and the same restatement discipline; it exists so a read
    correction can restate the month it touched without walking an account's
    whole history.
    """
    tenant_id = _tenant_id()
    facts = _read_facts(tenant_id, account_id).get(service_id, [])
    month_reads = [f for f in facts if rules.month_of(f.read_at) == period_month]
    try:
        figure = rules.summarise(period_month, month_reads)  # may raise OQ-358
    except rules.MixedUnitMonth as refusal:
        # `OQ-690`. On this NARROW path the held month is the only month there
        # is, so the outcome word has to say so: `"not_restated"` joins the four
        # `_state_month` already returns. ⚠ **It is NOT `"absent"`** — absent
        # means *nobody read this month*, and this month was read twice in two
        # units. Returning `"absent"` here would let a caller print the wrong
        # sentence to a customer, which is BR-MET-106's one reserved meaning
        # being spent on something else.
        _hold_month(
            problems,
            refusal,
            grain="account",
            account_id=str(account_id),
            service_id=str(service_id),
            period_month=period_month,
        )
        return "not_restated"
    now = timezone.now()

    if figure is None:
        head = (
            _USAGE.objects.filter(
                tenant_id=tenant_id,
                account_id=account_id,
                service_id=service_id,
                period_month=period_month,
                superseded_by_id__isnull=True,
                superseded_at__isnull=True,
            )
            .select_for_update()
            .first()
        )
        # The month is ABSENT at the account grain, so it is absent at the
        # meter grain too — `only_month` makes the withdrawal sweep see exactly
        # this month's heads and no others.
        recompute_account_assets(
            account_id, actor=actor, only_month=period_month, problems=problems
        )
        if head is None:
            return "absent"
        _withdraw(head, actor=actor, now=now)
        return "withdrawn"

    sample = _sample_flags(tenant_id, account_id)
    outcome = _state_month(
        tenant_id,
        account_id,
        service_id,
        figure,
        actor=actor,
        now=now,
        is_sample=all(sample.get(rid, False) for rid in figure.source_read_ids),
    )
    # BR-MET-141 — the meter grain moves with the account grain on the NARROW
    # path too, scoped to the one month this call is about. Without this a read
    # correction would restate the account's July and leave the meter's July
    # saying the old number, which is precisely the disagreement the ruling's
    # one constraint exists to prevent.
    recompute_account_assets(
        account_id, actor=actor, only_month=period_month, problems=problems
    )
    return outcome


class _DryRun(Exception):
    """Internal: unwinds `backfill_tenant`'s transaction after counting."""


def backfill_tenant(
    *,
    actor: Any = None,
    dry_run: bool = False,
    progress: Any = None,
) -> dict[str, Any]:
    """Restate every account in the CURRENT tenant that has any meter read.

    ── WHY A BACKFILL IS NEEDED AT ALL (`DEF-871`) ──────────────────────────
    Wiring the trigger into `commit_read_batch` fixes readings posted **from
    now on**. It does nothing for the readings already on file, and every
    existing tenant has months of them — so without this the Usage screens stay
    empty on exactly the customers who have been using the product longest,
    which is the opposite of the intended order.

    ⚠ **RUN IT ONCE PER TENANT AFTER DEPLOYING THE TRIGGER.** It is idempotent
    (CLAUDE.md rule 6 — the fingerprint means an unchanged month writes nothing
    and audits nothing), so running it twice is free and running it on a tenant
    that needs nothing produces `restated: 0` and no audit rows at all.

    ── WHAT IT DOES NOT DO ──────────────────────────────────────────────────
    It does not answer `OQ-358`. A month whose reads disagree about the unit is
    counted and NAMED in the report and left exactly as it was, the same as on
    the live path — so an operator running this on the PO's tenant learns how
    many such months exist, which is the number nobody has ever been able to
    see (the table was empty, so the case was unreachable).
    """
    tenant_id = _tenant_id()
    account_ids = list(
        _READ.objects.filter(tenant_id=tenant_id)
        .exclude(account_id=None)
        .values_list("account_id", flat=True)
        .distinct()
    )
    problems: list[UnrestatedMonth] = []
    faults: list[dict[str, Any]] = []
    totals = {"stated": 0, "restated": 0, "unchanged": 0, "withdrawn": 0}

    def _walk() -> None:
        for n, account_id in enumerate(account_ids, start=1):
            try:
                counts = recompute_account(account_id, actor=actor, problems=problems)
            except Exception as exc:  # noqa: BLE001 — reported, never silent
                # Same posture as the live path: each `recompute_account` is its
                # own atomic block, so a failure rolls back to ITS savepoint and
                # the connection is healthy for the next account. That is what
                # makes carrying on lawful on PostgreSQL (hard-won law 14) — it
                # is not a bare `except: continue` over a poisoned transaction.
                faults.append({"account_id": str(account_id), "reason": f"{exc.__class__.__name__}: {exc}"})
                continue
            for k in totals:
                totals[k] += counts[k]
            if progress is not None and n % 100 == 0:
                progress(n, len(account_ids))

    if dry_run:
        # ⚠ A dry run must not leave rows behind, and the only honest way to
        # count what WOULD be written is to write it and unwind. The sentinel
        # is raised AFTER the walk so the counts are real.
        try:
            with transaction.atomic():
                _walk()
                raise _DryRun
        except _DryRun:
            pass
    else:
        _walk()

    return {
        "accounts": len(account_ids),
        "dry_run": dry_run,
        **totals,
        "months_not_restated": len(problems),
        "months_not_restated_rows": [
            {
                "account_id": u.account_id,
                "service_id": u.service_id,
                "asset_id": u.asset_id,
                "register": u.channel,
                "grain": u.grain,
                "month": u.period_month.isoformat(),
                "question": u.question,
            }
            for u in problems
        ],
        "faults": faults,
    }


def heads_for(
    account_id: Any, *, service_ids: Sequence[Any] | None = None
) -> list[models.MonthlyUsage]:
    """The LIVE statements for one account — the read model's one query.

    Lives with the writer rather than in `selectors.py` because the head
    predicate (`superseded_by_id IS NULL AND superseded_at IS NULL`) is the
    same law the writer enforces, and two copies of it is how the two halves
    start disagreeing about what "latest" means.
    """
    tenant_id = _tenant_id()
    qs = _USAGE.objects.filter(
        tenant_id=tenant_id,
        account_id=account_id,
        superseded_by_id__isnull=True,
        superseded_at__isnull=True,
    )
    if service_ids is not None:
        qs = qs.filter(service_id__in=list(service_ids))
    return list(qs.order_by("period_month"))


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-011@a1fbf3f (the S21 operational tabs; BR-MET-106 snapshot 2026-08-24)
# generated: 2026-08-24 by the CR-030 W3 task 3.8 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the endpoint lives in apps/metering/api.py) E=deferred(no-frontend-half — AccountUsageTab.tsx is the same lane's separate file) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 idempotency key, HUMAN-REVIEW-PENDING; ledger row in this lane's scratchpad, REPORTED)
# gates: ruff✔ black✔ · pytest tests/test_br_met_106_monthly_usage.py · run_gates no new failure
# exceptions: E3 no `@require_role` — a derivation over rows the caller can already read, changing no money and granting nothing; the endpoint carries `AnyTenantRole` and the read model serves nothing `GET /accounts/{id}` does not · E3 `audit_log` is written although hard rule 7 names MONEY actions: a restated month changes a number a customer was already shown · E3 the service is resolved by the `asset → service_point → service` join rather than through a seam, matching `selectors.reads_list`'s existing filter; a read whose asset has no service point is DROPPED and belongs to no month
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Story:   US-RBS-010 · US-RBS-012 (EP-RBS-04) — CR-075 wave `M` task `M1`,
#          building the board wave `L` task `L9` describes and did not seed.
# Rules:   CLAUDE.md hard rule 1 (every write inside one tenant's context) ·
#          hard rule 2 (money to 4 decimals, never a float) · hard rule 8 (an
#          address lives on `premises` and nowhere else) · `BR-PAY-017` (the
#          ladder's rungs, read from payments and never restated here) ·
#          `BR-TEN-043` (the business day is an argument, never a clock) ·
#          hard-won law 7 ("reporting zero over a scope it silently excludes")
# Tests:   the cycle itself — 10-scripts/render-checks/rbs_m_dry_cycle.py
# ───────────────────────────────────────────────────────
"""L9's ladder set, on a real tenant — 1,004 accounts past due.

WHY THIS EXISTS, AND WHY IT IS WAVE `M`'s WORK RATHER THAN A PREREQUISITE
--------------------------------------------------------------------------
Wave `L` built runbook 8 and its own report says the fixture `L9` describes was
never seeded. Measured on the seeded demo tenant on 2026-09-06: **72 accounts,
100 invoices, and `collections_ladder` resolves ZERO subjects.** A month of dry
runs over an empty board is evidence of nothing at all — hard-won law 7's
*"reporting zero over a scope it silently excludes"*, with the scope being the
whole product. So the board is built here, and every figure wave `M` reports is
read off it.

WHAT IS ON THE BOARD, AND WHY EACH GROUP IS THERE
--------------------------------------------------
`L9` asks for *"1,004 past due — 812 notice · 43 plan in good standing · 31
protected · 23 undeliverable · 95 over the fee limit"*. The composition below
keeps `L9`'s two headline figures — **1,004 in scope and 812 with a rung due** —
and maps its five groups onto the branches the runbook AS BUILT can actually
reach. Where a group has no reachable branch that is a finding for `M3`, not a
reason to reshape the fixture until the numbers agree:

    group                          n     what the built runbook should say
    ─────────────────────────────────────────────────────────────────────────
    reminder due                 300     queued  (dry: `planned`)
    10-day notice due            250     queued
    5-day notice due             170     queued
    final certified letter due    92     queued
                                 ───
                                 812     `L9`'s "812 notice"
    payment plan, good standing   43     skipped · a plan in good standing
    protected  26 medical
               ·2 dispute
               ·3 sample          31     GUARDED — counted, no record row
    bad address on file           23     `L9`'s "23 undeliverable"
    under the $25.00 floor        95     skipped · under the collection floor
    ─────────────────────────────────────────────────────────────────────────
                               1,004

⚠ **THE 95 ARE UNDER THE FLOOR AND NOT "OVER THE FEE LIMIT", AND THAT IS A
DELIBERATE SUBSTITUTION.** `L9`'s fifth group and wave `L`'s launch sentence
("95 needing a person") describe an outcome the built runbook has no branch
for: `failed` is written only when a BOUND writer raises, and no runbook is on
`acts.LIVE_ENABLED_RUNBOOKS`, so **"needing a person" is unreachable in a dry
run by construction** — it is `L11`'s PostgreSQL case, not a dry cycle's. The
95 therefore exercise `payments`' own balance floor instead, which is a real
skip on a real rule, and the absence is reported rather than faked.

⚠ **THE 23 ARE THE POINT OF THE FIXTURE AND ARE EXPECTED TO COME BACK WRONG.**
`step_deliverable` derives *"the address works"* from `customers_seam.
account_anchors()`, which lists EVERY account of the tenant — so the lookup can
never miss and `undeliverable` can never be reached. `accounts.bad_address`
(r12 #8 / `BR-PAY-018`) is the column that records the fact and nothing reads
it. These 23 accounts carry the flag; what the run says about them is `M3`'s
evidence.

DATES ARE ANCHORED TO THE CYCLE'S FIRST MONDAY, MONEY IS NOT
-------------------------------------------------------------
Every due date is `--first-monday` minus a fixed number of days, so the rung
each account is owed is the same whichever day the fixture is built. The
amounts are literals. `BR-TEN-043`: no wall clock is read anywhere here, and
`--first-monday` is required for exactly that reason.

⚠ **THE RUNG IS NOT AGE, IT IS `account_collection_state.tier`.**
`ladder.next_rung(current)` walks the rungs in order from whatever has already
been sent, so an account 30 days late with no state is due the REMINDER, not
the certified letter. That is why each of the four queued groups carries a
seeded state row as well as an old bill, and why a fixture that only aged the
invoices would produce 812 reminders and prove nothing about the other three
rungs.

IDEMPOTENT, AND IT REFUSES RATHER THAN DOUBLING
------------------------------------------------
Every row it writes is keyed by an account number beginning `LM-`. A second run
finds them and adds nothing. It will NOT move an invoice that is already on the
database (hard rule 4 — an issued invoice cannot be edited or deleted), and it
says so and stops rather than writing a second bill that would silently double
a balance the board then reports as real.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/sbh_clone_rbsm" \\
      python3.12 10-scripts/render-checks/rbs_m_seed_ladder.py \\
        --tenant brazosbend --first-monday 2026-09-07
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import sys
from decimal import Decimal

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import connection, transaction  # noqa: E402

from apps.customers import disconnects as customers_disconnects  # noqa: E402
from apps.customers import models as customer_models  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.payments import collections_models  # noqa: E402
from apps.billing import models as billing_models  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

PREFIX = "LM-"

#: ⚠ **THE RUNG WORDS ARE PAYMENTS' AND ARE IMPORTED, NEVER TYPED.** A fixture
#: that spelled `"first_10_day"` as a literal would seed a tier the ladder does
#: not recognise, `next_rung` would raise `ValueError` deep inside a run, and
#: the failure would read like a broken engine rather than a broken fixture.
from apps.payments.ladder import LADDER_RUNGS  # noqa: E402

TIER_FRIENDLY, TIER_FIRST_10, TIER_SECOND_5, TIER_FINAL_48 = LADDER_RUNGS

#: group → (how many, the tier already sent, days since the oldest bill fell
#: due, the balance). The day offsets put each group's NEXT rung in the past on
#: the first Monday: reminder at due+3, 10-day at due+13, 5-day at due+18,
#: certified at due+21 (`ladder.rung_due_on`, this tenant's own intervals).
QUEUE_GROUPS = (
    ("reminder", 300, None, 20, Decimal("184.2000")),
    ("10-day notice", 250, TIER_FRIENDLY, 30, Decimal("242.6500")),
    ("5-day notice", 170, TIER_FIRST_10, 40, Decimal("318.4000")),
    ("final certified letter", 92, TIER_SECOND_5, 50, Decimal("406.7500")),
)
PLAN_COUNT = 43
MEDICAL_COUNT = 26
DISPUTE_COUNT = 2
SAMPLE_COUNT = 3
BAD_ADDRESS_COUNT = 23
UNDER_FLOOR_COUNT = 95

#: Over the $5.00 scope threshold `resolve()` applies and under payments' own
#: $25.00 collection floor — so the account IS in scope and IS skipped, which
#: is the branch this group exists to walk.
UNDER_FLOOR_BALANCE = Decimal("12.5000")
ORDINARY_BALANCE = Decimal("184.2000")


def _fail(message: str) -> None:
    print(f"⛔ {message}", file=sys.stderr)
    raise SystemExit(2)


def _lookups(tenant):
    """The status and type every account row needs, taken from the seed.

    ⚠ **CHOSEN BY BEHAVIOUR CLASS, NOT BY LABEL.** `BR-CUS-055` — billing keys
    off the CLASS — and a tenant that renamed "Active" would otherwise get a
    fixture of closed accounts that no bill run and no ladder would ever look
    at, silently.
    """
    status = (
        customer_models.AccountStatus.objects.filter(
            tenant_id=tenant.id, behavior_class="billable"
        )
        .order_by("id")
        .first()
    )
    if status is None:
        _fail(
            "this tenant has no account status in the 'billable' class, so every account this "
            "fixture wrote would be invisible to the ladder. Seed the platform lookups first."
        )
    account_type = customer_models.AccountType.objects.order_by("id").first()
    if account_type is None:
        _fail("no account types exist — the platform catalog has not been seeded.")
    return status, account_type


def _premises(tenant, seq: int):
    """One premises per account — hard rule 8, the ONE home of an address."""
    return metering_models.Premises.objects.create(
        tenant=tenant,
        premise_no=f"{PREFIX}P{seq:04d}",
        address_line=f"{1000 + seq} Sabine Street",
        city="Brazos Bend",
        state="TX",
        postal_code="77469",
    )


def _unit(tenant, premises, seq: int):
    return metering_models.Unit.objects.create(
        tenant=tenant,
        premises=premises,
        unit_no=f"{PREFIX}U{seq:04d}",
        label="1",
        unit_type="residential",
    )


def _account(tenant, *, seq, status, account_type, unit, premises, bad_address, is_sample):
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit=unit,
        premises_id=premises.id,
        account_no=f"{PREFIX}{seq:04d}",
        status=status,
        account_type=account_type,
        kind="regular",
        currency="USD",
        bad_address=bad_address,
        is_sample=is_sample,
        opened_at=None,
    )


def _bill(tenant, account, *, seq, total: Decimal, due_on: dt.date):
    """One open bill, dated so the ladder can place it.

    Money is a `Decimal` from a string literal and never a float (hard rule 2);
    the column is `NUMERIC(18,6)`, a lawful container for a 4-decimal value.
    """
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=f"{PREFIX}B{seq:05d}",
        status=billing_models.INVOICE_ISSUED,
        service_date=due_on - dt.timedelta(days=20),
        period_start=(due_on - dt.timedelta(days=50)),
        period_end=(due_on - dt.timedelta(days=20)),
        due_date=due_on,
        subtotal=total,
        tax_total=Decimal("0"),
        total=total,
        issued_at=dt.datetime(
            due_on.year, due_on.month, due_on.day, 9, 0, tzinfo=dt.timezone.utc
        )
        - dt.timedelta(days=20),
    )


def _state(tenant, account, *, tier, sent_on):
    collections_models.AccountCollectionState.objects.create(
        tenant=tenant,
        account=account,
        tier=tier,
        tier_sent_on=sent_on,
        # ⚠ STRICTLY BEFORE the first Monday. `ladder.decide` compares
        # `last_notice_on >= as_of` and stops the pass — hard rule 6's same-day
        # guard. A fixture that stamped the run's own day would seed 812
        # accounts that skip for a reason the fixture invented.
        last_notice_on=sent_on,
    )


def _plan(tenant, account, *, first_monday: dt.date):
    """An ACTIVE plan whose instalments are all in the future — so it is CURRENT.

    `dunning.plan_is_current` is *"every instalment due by `as_of` was met"*,
    and `outstanding_installments` compares `due_date < as_of`. Nothing here is
    due yet, so nothing is missed and `BR-CUS-043`'s pause applies.
    """
    plan = collections_models.PaymentPlan.objects.create(
        tenant=tenant,
        account=account,
        total_amount=Decimal("184.2000"),
        down_payment=Decimal("0"),
        currency="USD",
        installment_count=3,
        cadence="monthly",
        status=collections_models.PLAN_ACTIVE,
        proposed_on=first_monday - dt.timedelta(days=14),
        signed_on=first_monday - dt.timedelta(days=13),
    )
    for seq in range(1, 4):
        collections_models.PaymentPlanInstallment.objects.create(
            tenant=tenant,
            plan=plan,
            seq=seq,
            due_date=first_monday + dt.timedelta(days=20 * seq),
            amount=Decimal("61.4000"),
            currency="USD",
        )
    return plan


def _medical(tenant, account, *, first_monday: dt.date):
    """A certificate in force on the first Monday. `expires_on` is NOT NULL —
    `ck_protection_lifetime` refuses a medical hold with no end date, because a
    certificate with no end date is a permanent exemption nobody signed."""
    customers_disconnects.AccountProtection.objects.create(
        tenant=tenant,
        account=account,
        kind=customers_disconnects.PROTECTION_MEDICAL,
        effective_from=first_monday - dt.timedelta(days=60),
        expires_on=first_monday + dt.timedelta(days=60),
        set_by="tenant",
        note="wave M ladder fixture",
    )


def _dispute_units(tenant, wanted: int) -> list:
    """Units that already carry an UNCLEARED dispute — reused, never invented.

    ⚠ **THE GUARD READS METERING'S OWN FACT AND THE FIXTURE MUST NOT FORGE
    ONE.** `metering.selectors.dispute_holds_for_unit` walks unit → service
    point → asset → read head and asks for `disputed_at` set with
    `dispute_cleared_at` null. Building that chain from nothing would seed four
    tables in another module and would prove the fixture works rather than that
    the guard does. So this marks an EXISTING seeded read as disputed and hands
    back the unit it hangs on.

    Returns fewer than `wanted` when the seed has fewer meters, and the caller
    PRINTS the shortfall — a guard exercised over an empty set is a guard not
    exercised at all, and a silent zero here would read exactly like a pass.
    """
    from apps.metering import selectors as metering_selectors

    units: list = []
    heads = (
        metering_models.MeterRead.objects.filter(
            tenant_id=tenant.id, superseded_by_id__isnull=True
        )
        .select_related("asset")
        .order_by("id")
    )
    for read in heads:
        if len(units) >= wanted:
            break
        service_point_id = getattr(read.asset, "service_point_id", None)
        if not service_point_id:
            continue
        point = metering_models.ServicePoint.objects.filter(
            tenant_id=tenant.id, pk=service_point_id, deleted_at__isnull=True
        ).first()
        if point is None or point.unit_id is None:
            continue
        if any(unit.pk == point.unit_id for unit in units):
            continue
        read.disputed_at = read.read_at
        read.dispute_reason = "wave M ladder fixture — the dispute guard"
        read.dispute_cleared_at = None
        read.save(update_fields=["disputed_at", "dispute_reason", "dispute_cleared_at"])
        unit = metering_models.Unit.objects.filter(tenant_id=tenant.id, pk=point.unit_id).first()
        if unit is None:
            continue
        if not metering_selectors.dispute_holds_for_unit(unit.pk):
            # The guard read it back and saw nothing. Say so rather than
            # counting a dispute that does not exist (hard-won law 7).
            continue
        units.append(unit)
    return units


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend")
    parser.add_argument(
        "--first-monday",
        required=True,
        help="the cycle's first business day, ISO. Required: BR-TEN-043 — no clock is read.",
    )
    args = parser.parse_args()

    if connection.vendor != "postgresql":
        _fail(
            f"this is running on {connection.vendor!r}. The board this seeds is read under "
            "row-level security, which does not exist on SQLite, so nothing built here would "
            "mean anything (hard-won law 7 — G5 once called 192 skips a pass)."
        )

    first_monday = dt.date.fromisoformat(args.first_monday)
    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        _fail(f"no tenant with subdomain {args.tenant!r} — seed_demo first.")

    with core_tenancy.tenant_context(tenant.id):
        existing = customer_models.Account.objects.filter(
            tenant_id=tenant.id, account_no__startswith=PREFIX
        ).count()
        if existing:
            print(f"── {existing} ladder accounts are already on this database; adding none.")
            _summary(tenant, first_monday)
            return 0

        status, account_type = _lookups(tenant)
        dispute_units = _dispute_units(tenant, DISPUTE_COUNT)
        if len(dispute_units) < DISPUTE_COUNT:
            print(
                f"⚠ only {len(dispute_units)} of {DISPUTE_COUNT} dispute accounts could be "
                "built: the seed has that many units with a meter read to dispute. The "
                "shortfall is REPORTED rather than made up, and the dispute guard is "
                "exercised over that many accounts and no more.",
                file=sys.stderr,
            )

        seq = 0
        built: dict[str, int] = {}

        def make(
            label: str,
            *,
            tier=None,
            days_late: int,
            balance: Decimal,
            bad_address: bool = False,
            is_sample: bool = False,
            on_unit=None,
        ):
            nonlocal seq
            seq += 1
            due_on = first_monday - dt.timedelta(days=days_late)
            if on_unit is not None:
                unit = on_unit
                premises = unit.premises
            else:
                premises = _premises(tenant, seq)
                unit = _unit(tenant, premises, seq)
            account = _account(
                tenant,
                seq=seq,
                status=status,
                account_type=account_type,
                unit=unit,
                premises=premises,
                bad_address=bad_address,
                is_sample=is_sample,
            )
            _bill(tenant, account, seq=seq, total=balance, due_on=due_on)
            if tier is not None:
                _state(tenant, account, tier=tier, sent_on=due_on + dt.timedelta(days=3))
            built[label] = built.get(label, 0) + 1
            return account

        # ⚠ ONE TRANSACTION FOR THE WHOLE BOARD. A half-built board is worse
        # than none: the run would report a real-looking figure over a set
        # nobody designed, which is the exact failure this fixture exists to
        # prevent for the runbook.
        with transaction.atomic():
            for label, count, tier, days_late, balance in QUEUE_GROUPS:
                for _ in range(count):
                    make(label, tier=tier, days_late=days_late, balance=balance)

            for _ in range(PLAN_COUNT):
                account = make("payment plan", days_late=20, balance=ORDINARY_BALANCE)
                _plan(tenant, account, first_monday=first_monday)

            for _ in range(MEDICAL_COUNT):
                account = make("protected · medical", days_late=20, balance=ORDINARY_BALANCE)
                _medical(tenant, account, first_monday=first_monday)

            for unit in dispute_units:
                make("protected · dispute", days_late=20, balance=ORDINARY_BALANCE, on_unit=unit)

            for _ in range(SAMPLE_COUNT):
                make(
                    "protected · sample",
                    days_late=20,
                    balance=ORDINARY_BALANCE,
                    is_sample=True,
                )

            for _ in range(BAD_ADDRESS_COUNT):
                make("bad address", days_late=20, balance=ORDINARY_BALANCE, bad_address=True)

            for _ in range(UNDER_FLOOR_COUNT):
                make("under the floor", days_late=20, balance=UNDER_FLOOR_BALANCE)

        print(f"── built {seq} accounts on {tenant.subdomain}, all past due on {first_monday}")
        for label in sorted(built):
            print(f"   · {built[label]:>4}  {label}")
        _summary(tenant, first_monday)
    return 0


def _summary(tenant, first_monday: dt.date) -> None:
    """Read the board BACK through payments' own seam and print what it says.

    ⚠ **THE FIXTURE DOES NOT GET TO ASSERT ITS OWN SUCCESS.** What matters is
    what `payments` decides about these rows, not what this file intended, so
    the closing figure is a read of `collections_ladder_board` rather than a
    count of the inserts above.
    """
    from apps.runbooks.seams import payments_seam

    board = payments_seam.collections_ladder_board(as_of=first_monday)
    rows = list(board.get("rows", ()))
    print(f"\n── the board on {first_monday}: {len(rows)} accounts with an outstanding position")
    print(f"   next_step_available: {board.get('next_step_available')}")
    if not board.get("next_step_available"):
        print(
            "   ⚠ this tenant's collection floor and intervals are unset, so the board can "
            "decide NOTHING and every account would come back 'not set up'.",
            file=sys.stderr,
        )
    by_rung: dict[str, int] = {}
    by_skip: dict[str, int] = {}
    for row in rows:
        if row.get("runs"):
            key = str(row.get("next_rung") or "?")
            by_rung[key] = by_rung.get(key, 0) + 1
        else:
            key = str(row.get("skip_reason") or "(no reason)")
            by_skip[key] = by_skip.get(key, 0) + 1
    print(f"   would run   : {sum(by_rung.values())}")
    for key in sorted(by_rung):
        print(f"      · {by_rung[key]:>4}  {key}")
    print(f"   would skip  : {sum(by_skip.values())}")
    for key in sorted(by_skip):
        print(f"      · {by_skip[key]:>4}  {key}")


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Give runbooks 12 and 16 something REAL to look at on the seeded utility.

`CR-075` wave S. `03-seed_demo.py` leaves this tenant with two disconnect cases
at the last tier and **both are on sample accounts**, and with one draft rate
schedule whose tariff has no activated version behind it. So both Checks run
correctly and conclude nothing:

  * runbook 12's guard removes 100% of its scope — which is right, and a run
    over an empty scope proves nothing about a build (`rbs_s_seed_checks.py`
    reports that as INCONCLUSIVE rather than as a pass);
  * runbook 16 finds no COMPARABLE draft, because `_baseline_version` refuses to
    compare a version with itself — *"that is the one answer this analysis must
    never invent"*.

This adds one of each, on rows a real utility would have:

  1. a NON-sample account with a real outstanding balance, at TIER 3, with a
     certified letter and a recorded PROOF OF SERVICE dated three days ago;
  2. a DRAFT version of the tenant's real *Residential Water — Inclining tiers*
     schedule, every block priced **+8%** and a new top block above the ladder's
     current ceiling — so the preview has both a price move and a structural one
     to attribute.

⚠ **IT IS IDEMPOTENT AND IT SAYS WHAT IT FOUND.** Run twice and the second run
reports what already exists rather than opening a second case — which
`uq_one_open_disconnect_case_per_account` would refuse anyway — or a second
draft, which `uq_tariff_versions_one_draft` would.

⚠ **IT WRITES THROUGH `customers`' OWN SERVICE FUNCTIONS WHERE THEY EXIST**, so
the case, the notice and the proof are the same rows a clerk's screen would
write and are subject to the same rules. The one direct write is the tier: this
product advances a case with `advance()`, which walks the ladder a rung at a
time against a live balance and a scheduler that does not exist (`DEF-320`), and
a fixture that drove it would be testing the ladder rather than seeding it.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/smartbillhub" \\
      python3 10-scripts/render-checks/rbs_s_fixture.py --tenant brazosbend
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

from apps.customers import disconnects  # noqa: E402
from apps.customers import selectors as customers_selectors  # noqa: E402
from apps.identity import models as identity_models  # noqa: E402
from apps.payments import collections_read  # noqa: E402
from apps.rating import models as rating_models  # noqa: E402
from apps.rating import selectors as rating_selectors  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: The draft raises every block by this much. A round `+8%` so the preview's own
#: revenue percentage is a number a reader can check by hand against the tiles.
RAISE = Decimal("1.08")


def _actor(tenant):
    """A real staff user of this tenant, wearing the role the guards read.

    ⚠ **`users` HAS NO `role` COLUMN AND `@require_role` READS `actor.role`**
    (`core/permissions.require_role`: *"the actor's `.role` attribute is
    checked"*). The test suite's own `staff_actor` answers the same shape — a
    `SimpleNamespace` over a REAL user row — and the row has to be real because
    `disconnect_notices.proof_recorded_by_id` is a foreign key into `users`.
    """
    from types import SimpleNamespace

    user = (
        identity_models.User.objects.filter(tenant=tenant)
        .exclude(email__endswith="@sample.test")
        .order_by("created_at")
        .first()
    )
    if user is None:
        return None
    return SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)


def seed_a_real_disconnect_case(tenant, actor, as_of: dt.date) -> str:
    """One NON-sample account at TIER 3 with its letter served three days ago."""
    existing = [
        case
        for case in disconnects.DisconnectCase.objects.filter(
            tenant=tenant, tier=disconnects.TIER_3
        ).exclude(state__in=disconnects.CLOSED_CASE_STATES)
        if not customers_selectors.account_queryset()
        .filter(id=case.account_id, is_sample=True)
        .exists()
    ]
    if existing:
        case = existing[0]
        # ⚠ **IDEMPOTENT ON THE WHOLE FIXTURE, NOT ON ITS FIRST STEP.** An
        # earlier attempt left a case with no notice behind it, and a check that
        # stopped at *"a case exists"* would have reported *already there* over a
        # subject runbook 12 correctly removes for having no served letter —
        # which is a fixture that cannot tell a working build from a broken one
        # (hard-won law 2's 2026-09-05 note).
        proof = disconnects.service_proof_for(case, tier=disconnects.TIER_3)
        if proof["recorded"]:
            return f"already there: {case.case_no} with its proof of service"
        served_on = as_of - dt.timedelta(days=3)
        _serve_a_certified_letter(tenant, actor, case, served_on)
        return f"{case.case_no} had no served letter; certified notice served {served_on}"

    board = collections_read.ladder_board(as_of=as_of)
    sample_ids = {str(one) for one in customers_selectors.account_queryset().filter(is_sample=True).values_list("id", flat=True)}
    candidates = [
        row
        for row in board["rows"]
        if str(row["account_id"]) not in sample_ids
        and Decimal(row["balance"]) >= Decimal("50")
        and not disconnects.open_case_for(row["account_id"])
    ]
    if not candidates:
        return "⛔ no non-sample account with a balance over $50 and no open case"

    # ⚠ **EVERY ATTEMPT GETS ITS OWN SAVEPOINT (CLAUDE.md hard-won law 14).**
    # On PostgreSQL a refused statement poisons the whole transaction, so a bare
    # `except …: continue` would lose every later write at COMMIT. The nested
    # `transaction.atomic()` is the only thing that makes this loop work and it
    # must not be "simplified" away.
    chosen = None
    refusals: list[str] = []
    for candidate in candidates:
        try:
            with transaction.atomic():
                disconnects.open_case(actor, candidate["account_id"], as_of=as_of)
        except disconnects.DisconnectRuleError as refusal:
            refusals.append(getattr(refusal, "code", "") or "refused")
            continue
        chosen = candidate
        break

    if chosen is None:
        # ⚠ **`DEF-CUS-4396` — THE LADDER REFUSES ALL THREE, AND IT IS NOT WRONG
        # TO.** `open_case` reads `disconnects._balance_for`, which is the
        # LEDGER's position; `ladder_board` reads BILLING's open invoices. On
        # this utility they disagree on four accounts by `$850.54` — `R-0003` is
        # `$368.40` on the collections board and `$0.00` to the disconnect
        # ladder — so every non-sample candidate is refused *"this account owes
        # nothing"*. That is a real defect and it is FILED rather than worked
        # around silently.
        #
        # The case is written directly here, and the reason is exactly the one
        # given for the tier above: this fixture's job is to give runbook 12 a
        # subject, not to prove the ladder. **What the runbook then reads is
        # still every real rule** — the certified notice, its proof of service,
        # the notice period from Settings, the protections and the payments are
        # all written and read through their owning modules.
        chosen = candidates[0]
        # `_allocate_case_no` takes a row lock, so it needs a transaction.
        with transaction.atomic():
            case = disconnects.DisconnectCase.objects.create(
                tenant=tenant,
                account_id=chosen["account_id"],
                case_no=disconnects._allocate_case_no(),
                sequence=disconnects.SEQ_SERVICE,
                state=disconnects.STATE_NOTICE_SENT,
                tier=disconnects.TIER_1,
                opened_on=as_of,
                # What the household owed when the case opened — BILLING's
                # figure, which is the one the collections board showed and the
                # one `DEF-CUS-4396` says the ledger does not agree with.
                amount_owed_at_open=Decimal(chosen["balance"]),
            )
        print(
            f"   ⚠ the ladder refused all {len(candidates)} candidates "
            f"({sorted(set(refusals))}) — DEF-CUS-4396; writing the case directly"
        )
    case = disconnects.open_case_for(chosen["account_id"])
    # ⚠ THE ONE DIRECT WRITE, AND IT IS THE TIER. `advance()` walks the ladder a
    # rung at a time against a live balance and a scheduler nothing runs
    # (`DEF-320`); driving it here would be testing the ladder rather than
    # seeding it.
    case.tier = disconnects.TIER_3
    case.state = disconnects.STATE_NOTICE_SENT
    case.save(update_fields=["tier", "state", "updated_at"])

    served_on = as_of - dt.timedelta(days=3)
    _serve_a_certified_letter(tenant, actor, case, served_on)
    return (
        f"opened {case.case_no} on account {chosen['account_no']} "
        f"(balance {Decimal(chosen['balance']):.2f}), certified letter served {served_on}"
    )


def _serve_a_certified_letter(tenant, actor, case, served_on: dt.date) -> None:
    """One TIER 3 certified notice with its proof of service recorded.

    ⚠ **THE NOTICE IS WRITTEN DIRECTLY FOR THE SAME REASON THE CASE WAS —
    `DEF-CUS-4396`.** `record_notice` calls `_require_running` too, so the
    ledger's `$0.00` refuses it as well. `delivery_state` is left NULL with its
    reason, exactly as `record_notice` writes it: task 7.10, *never a fabricated
    `emailed`*.

    ⚠ **AND THE PROOF GOES THROUGH THE MODULE'S OWN SERVICE FUNCTION**, because
    it is the thing runbook 12's step 2 actually reads: `BR-CUS-100`'s channel,
    reference and served date, attested by a named person and role-gated.
    """
    with transaction.atomic():
        notice = disconnects.DisconnectNotice.objects.create(
            tenant=tenant,
            case=case,
            tier=disconnects.TIER_3,
            delivery_state=None,
            delivery_unavailable_reason=disconnects.DELIVERY_UNAVAILABLE["code"],
            issued_on=served_on,
            actor_id=getattr(actor, "id", None),
            detail={"sequence": case.sequence},
        )
    disconnects.record_proof_of_service(
        actor,
        notice.pk,
        channel=disconnects.TIER_3_REQUIRED_CHANNEL,
        reference="7012 3456 0000 1111",
        served_on=served_on,
        signed_for_on=served_on,
    )


def _tariff_that_priced_the_cycle(tenant):
    """The schedule the most recent issued cycle was actually billed on.

    ⚠ **DRAFTING ANY OTHER SCHEDULE MAKES THE WALKTHROUGH PROVE NOTHING —
    `DEF-RBS-4407`.** A preview only reaches the bills its own schedule priced,
    read off `invoice_lines.tariff_version_id`, which is stamped at issue and
    frozen. Drafting the utility's own tariff while its cycle was billed on the
    sample one produced *49 bills · nothing changes*, which is TRUE and proves
    only the scoping. So the fixture asks the bills which ladder priced them.
    """
    from apps.runbooks.seams import billing_seam

    for run in billing_seam.bill_runs(limit=25):
        cycle = billing_seam.issued_bills_for_run(
            run.get("id") or run.get("run_id"), service_code="water"
        )
        counted: dict[str, int] = {}
        for bill in cycle.get("bills") or []:
            for line in bill.get("lines") or []:
                if str(line.get("kind")) == "usage" and line.get("tariff_version_id"):
                    key = str(line["tariff_version_id"])
                    counted[key] = counted.get(key, 0) + 1
        if not counted:
            continue
        version_id = max(counted, key=lambda one: counted[one])
        version = rating_models.TariffVersion.objects.filter(
            tenant=tenant, id=version_id
        ).select_related("tariff").first()
        if version is not None and version.tariff is not None:
            return version.tariff, counted[version_id]
    return None, 0


def seed_a_draft_schedule(tenant) -> str:
    """A `+8%` draft of the schedule the last issued cycle was billed on."""
    tariff, lines = _tariff_that_priced_the_cycle(tenant)
    if tariff is None:
        tariff = (
            rating_models.Tariff.objects.filter(tenant=tenant, deleted_at__isnull=True)
            .filter(service__code="water")
            .order_by("name")
            .first()
        )
    if tariff is None:
        return "⛔ this tenant has no water schedule to draft against"
    live = rating_selectors.latest_version(tariff)
    if live is None:
        return f"⛔ {tariff.name} has no activated version to compare a draft against"
    existing = rating_selectors.draft_version(tariff)
    if existing is not None:
        return f"already there: a draft of {tariff.name} ({lines} usage lines of the cycle)"

    draft = rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=tariff,
        model=live.model,
        base_charge=live.base_charge,
        minimum_bill=live.minimum_bill,
        currency=live.currency,
        uom=live.uom,
        percent=live.percent,
        basis_service_id=live.basis_service_id,
        effective_from=None,  # BR-RAT-031 — a NULL effective_from IS the draft
        version_label="2027 filing",
        change_reason="CR-075 wave S walkthrough fixture",
    )
    tiers = list(
        rating_models.RateTier.objects.filter(tenant=tenant, tariff_version=live).order_by(
            "seq", "id"
        )
    )
    top = None
    for tier in tiers:
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=draft,
            season_id=tier.season_id,
            size_class=tier.size_class,
            seq=tier.seq,
            from_qty=tier.from_qty,
            to_qty=tier.to_qty,
            unit_price=(tier.unit_price * RAISE).quantize(Decimal("0.000001")),
        )
        top = tier
    if top is not None and top.to_qty is None:
        # ⚠ THE LAST BLOCK IS `0 → ∞` (`BR-RAT-032`), so a NEW top block means
        # CLOSING it and adding one above — which is exactly the structural
        # change `RB-116`'s *New top block above 20,000 gal* is about.
        # On the ladder's OWN scale, not a fixed 10,000: a water schedule in
        # kgal and one in gallons are three orders of magnitude apart, and a new
        # "top block above 10,015 kgal" is a block no customer could ever reach.
        floor = top.from_qty or Decimal("0")
        ceiling = (floor * 2) if floor > 0 else Decimal("10000")
        rating_models.RateTier.objects.filter(
            tenant=tenant, tariff_version=draft, seq=top.seq
        ).update(to_qty=ceiling)
        rating_models.RateTier.objects.create(
            tenant=tenant,
            tariff_version=draft,
            size_class=top.size_class,
            seq=top.seq + 1,
            from_qty=ceiling,
            to_qty=None,
            unit_price=(top.unit_price * RAISE * Decimal("1.25")).quantize(Decimal("0.000001")),
        )
        return (
            f"drafted {tariff.name} ({lines} usage lines of the last cycle): "
            f"{len(tiers)} blocks at +8% plus a new top block above "
            f"{ceiling:.0f} {live.uom or ''}".strip()
        )
    return f"drafted {tariff.name}: {len(tiers)} blocks at +8%"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend")
    args = parser.parse_args()

    if connection.vendor != "postgresql":
        print("⛔ REFUSED: PostgreSQL only — the tenant policies do not exist on SQLite", file=sys.stderr)
        return 2
    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        print(f"⛔ no tenant {args.tenant!r} — seed_demo first", file=sys.stderr)
        return 2

    with core_tenancy.tenant_context(tenant.id):
        actor = _actor(tenant)
        if actor is None:
            print("⛔ no staff user on this tenant", file=sys.stderr)
            return 2
        as_of = dt.date.today()
        print("── case  :", seed_a_real_disconnect_case(tenant, actor, as_of))
        print("── draft :", seed_a_draft_schedule(tenant))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

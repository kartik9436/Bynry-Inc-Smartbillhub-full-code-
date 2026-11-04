#!/usr/bin/env python3
# ── Trace ──────────────────────────────────────────────
# Change:  CR-094-BRC01 step 2 wave B — `DEF-CUS-5005`, *Close out renders live
#          on a pending-activation account and is switched off on the one
#          status it is for*.
# Rules:   BR-CUS-430 (a close-out is for an account whose service was CUT) ·
#          BR-CUS-082 (a closed account cannot be escalated) · BR-CUS-100
#          (a tier-3 cut needs recorded proof of service) · BR-CUS-107
#          (the cut account's status is `disconnected`).
# ───────────────────────────────────────────────────────
# WHY THIS SCRIPT EXISTS
# ─────────────────────
# The blueprint's own `ACC-A05` truth table has six rows and the last one reads
# **"Disconnected · none · the one status it is for, and it has no account"**.
# Step 1 measured the same thing and had to write NOT CONFIRMED against the one
# row that matters: the fixture seeds 69 active, 1 closed, 1 marked_disconnect,
# 1 pending_activation and 1 vacation_hold, and NO disconnected account.
#
# So a fix to the Close out gate could be proved to REFUSE and could not be
# proved to ALLOW — half a proof, and the wrong half: a gate that refuses
# everything passes every "is it disabled here" check ever written.
#
# This drives the product's OWN disconnect services end to end, never writing a
# status code into a row: the ladder is opened, advanced to tier 3, the tier-3
# notice's certified-mail service is attested by a person, the cut is scheduled
# and then committed.
#
# ⚠⚠ WHAT IT ACTUALLY ACHIEVES, AND WHERE IT STOPS — READ THIS BEFORE RE-RUNNING
# ─────────────────────────────────────────────────────────────────────────────
# It reaches a REAL `cut` disconnect case with a real `cut_on`. It does NOT
# reach a `disconnected` ACCOUNT, and that is the product refusing rather than
# this script failing. `commit_cut` writes BR-CUS-107's status only when the
# days up to the cut were billed — *"writing it over a bill billing REFUSED
# would leave those days billed by nobody"* (`OQ-1170`'s $23.23) — and the cut
# bill is refused on this fixture:
#
#   cut_bill.outcome = "blocked" · reason "cut_bill_refused"
#   "service 'electric' has no connection size RECORDED on this connection …
#    a size may not be guessed — `resolve_size_row` refuses a size the schedule
#    does not price rather than charging $0.00 for it."
#
# The tenant holds **8 connections against 73 accounts**, so this is not one
# unlucky account: essentially no account in this fixture can be cut. Building
# the missing connection/asset data is its own piece of work and is NOT done
# here — inventing a meter size to get a screen to light up would be a fixture
# lying about a household's plumbing.
#
# So the ALLOW half of the `DEF-CUS-5005` gate is proved by a component test
# rendering a `disconnected` detail (`AccountDetailPage.test.tsx`), and the
# REFUSE half is proved in a browser on the real `pending_activation` account.
#
# THREE BLOCKERS IT MET, ALL THREE REAL AND NONE OF THEM THIS SCRIPT'S FAULT
# ─────────────────────────────────────────────────────────────────────────
#  1 · `CC-RECON` is configured on NO tenant — the demo seed spells its
#      reconnection fee `RECON` — so `commit_cut` refuses every cut in this
#      tree. `disconnects.py` reports the mismatch itself and says a ruling is
#      owed; this script does what the refusal instructs and configures the
#      code, mirroring the tenant's own `RECON` row. It decides nothing.
#  2 · The API's actor shape could not commit a cut at all — `DEF-BIL-5090`,
#      filed by this lane and **FIXED 2026-09-12** by one resolver,
#      `core.audit.actor_user_id`. See the comment at `actor =` below.
#  3 · The cut bill refusal above.
#
# WHAT IT SEEDS, AND ON WHICH ACCOUNT
# ───────────────────────────────────
# It deliberately avoids every account the blueprint and the step-1 lanes walk
# — `A-11812`, `A-12048`, `A-10432`, `AC-2026-00043`, `AC-2026-00052` — so a
# sibling lane re-running their measurements reads the same product they did.
# It takes the lowest-balance ACTIVE account that OWES SOMETHING and is none of
# those, so the cut bills the least and the settlement figure stays small. The
# debt is not a tidiness choice: `_require_running` refuses to open a ladder on
# an account that owes nothing — *"there is nothing to chase"* — so a zero
# balance cannot be walked to a cut at all.
#
# IDEMPOTENT, in both directions: a `disconnected` account already present, or a
# case already in state `cut`, and it prints what it found and stops. Re-running
# over a committed cut would hit billing's `DuplicateRun` on the reconnection
# fee, which is BR-BIL-005 working.
#
# HOW TO RUN IT
#   cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
#     DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \
#     JOBS_EAGER=false python3 ../10-scripts/cr094_wave_b_seed_cut_account.py
from __future__ import annotations

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "06-backend"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402

from types import SimpleNamespace  # noqa: E402

from apps.customers import disconnects  # noqa: E402
from apps.identity.models import User  # noqa: E402
from apps.tenancy.models import Tenant  # noqa: E402
from core.permissions import SYSTEM_ADMIN  # noqa: E402
from core.tenancy import tenant_context  # noqa: E402

TENANT = os.environ.get("TENANT", "brazosbend")
# The accounts the blueprint and the step-1 lanes walk. Never cut one of these.
RESERVED = {"A-11812", "A-12048", "A-10432", "AC-2026-00043", "AC-2026-00052"}

Account = apps.get_model("customers", "Account")
DisconnectCase = apps.get_model("customers", "DisconnectCase")


def main() -> int:
    tenant = Tenant.objects.get(subdomain=TENANT)
    with tenant_context(tenant.id):
        already = Account.objects.filter(
            tenant_id=tenant.id, status__code=disconnects.CUT_STATUS_CODE
        ).first()
        if already is not None:
            print(f"ALREADY SEEDED: {already.account_no} is `disconnected` — nothing to do")
            return 0

        # The B12 §6a service shape: `id` from the user, `role` ATTACHED BY THE
        # SERVER (`api._actor` reads `request.tenant_role`). `User` carries no
        # role column, so a bare model instance is refused AUTH-002 by every
        # `@require_role` below — which is the guard working, not a fixture
        # problem.
        user = User.objects.filter(email="dana@brazosbendutilities.com").first()
        if user is None:
            print("NO ACTOR: no staff user to attribute the cut to")
            return 1
        # ⚠ **THIS LINE CARRIED A `pk=` UNTIL `DEF-BIL-5090` WAS FIXED ON
        # 2026-09-12, AND IT IS THE PRODUCTION SHAPE AGAIN NOW.**
        # `transfer_disconnect_api._actor` builds `SimpleNamespace(id=…,
        # role=…)` — no `pk` — and `billing/one_time.create_one_time_run` wrote
        # `run_by_id=getattr(run_by, "pk", run_by)`, so the whole namespace went
        # into a UUID column and Django refused it:
        #   ValidationError: "namespace(id=UUID('…'), role='system_admin')" is
        #   not a valid UUID
        # Every cut test passed because `tests/test_us_met_helpers.staff_actor`
        # returns `SimpleNamespace(id=…, pk=…, role=…, user=…)` — a FIXTURE
        # SHAPE WIDER THAN THE PRODUCTION ONE, which is hard-won law 7's
        # "structurally incapable of failing". `core.audit.actor_user_id` is the
        # one resolver now, and **this script deliberately stops widening the
        # actor**: a seed that keeps a fix's workaround is a seed that no longer
        # exercises the shape the product actually builds, and the next lane
        # reading this comment would think the defect was still live.
        actor = SimpleNamespace(id=user.pk, role=SYSTEM_ADMIN, user=user)

        candidate = (
            Account.objects.filter(tenant_id=tenant.id, status__code="active", balance__gt=0)
            .exclude(account_no__in=RESERVED)
            .order_by("balance", "account_no")
            .first()
        )
        if candidate is None:
            print("NO CANDIDATE: no active account outside the reserved set")
            return 1

        today = date.today()
        print(f"cutting {candidate.account_no} (balance {candidate.balance} {candidate.currency})")

        # ⚠ **AMENDED 2026-09-25 — THIS SAID A SCHEDULED CASE WITH NO
        # PER-SERVICE DECISIONS IS *"a dead end by design"*, AND IT IS NOT.**
        # The case-record lane disproved it by DOING it: re-running the
        # scheduling wizard on such a case re-schedules it and the services
        # land. The old sentence was an inference from `_require_running`
        # refusing `advance`, never checked against a run — hard-won law 1, a
        # comment claiming a guarantee is not the guarantee, pointing the other
        # way: a comment claiming an impossibility that is merely untried.
        #
        # **THE REPAIR HAS A DOOR NOW**: the case record page offers
        # *Choose the services* on exactly this case, pointing at the wizard
        # (`DisconnectRecordPage.tsx`, `data-testid=disconnect-record-reschedule`).
        # A seed script may drop a case IT made; nothing else here may.
        stuck = disconnects.open_case_for(candidate.pk)
        if stuck is not None and stuck.state == disconnects.STATE_CUT:
            print(
                f"ALREADY CUT: {candidate.account_no} carries case "
                f"{stuck.case_no} in state {stuck.state!r}, cut_on={stuck.cut_on}, "
                f"and the account status is {candidate.status.code!r} — the cut bill was "
                "refused, so BR-CUS-107's status was HELD. See this file's header."
            )
            return 0
        if stuck is not None and stuck.state != disconnects.STATE_NOTICE_SENT:
            if os.environ.get("RESET") != "1":
                print(
                    f"HALF-MADE CASE: {candidate.account_no} carries a case in state "
                    f"{stuck.state!r} that this script cannot advance. Re-run with RESET=1 "
                    "to drop it and start the ladder again."
                )
                return 1
            apps.get_model("customers", "DisconnectNotice").objects.filter(
                case_id=stuck.pk
            ).delete()
            DisconnectCase.objects.filter(pk=stuck.pk).delete()
            print(f"  RESET: dropped the half-made case in state {stuck.state!r}")

        # 0 · ⚠ NO TENANT IN THIS TREE CAN COMMIT A CUT UNTIL THIS ROW EXISTS,
        # AND THAT IS A REPORTED PRODUCT GAP RATHER THAN A FIXTURE ONE.
        # `commit_cut` prices the reconnection from the tenant's `CC-RECON`
        # charge code (BR-BIL-007: *"NSF/reconnect fees are tenant-configured
        # charge codes, never hardcoded"*) and refuses without it — *"A cut
        # nobody can price is a cut the customer cannot undo. Configure the
        # reconnection charge code, then cut."* The demo seed spells its
        # reconnection fee `RECON`, so `CC-RECON` resolves on NO tenant and
        # every cut in this tree refuses. `disconnects.py` already reports the
        # mismatch in its own words and says a ruling is owed; nothing here
        # decides it. This does what the refusal instructs: it CONFIGURES the
        # code the product asks for, mirroring the tenant's own `RECON` row so
        # the figure is the utility's and not this script's.
        Charge = apps.get_model("rating", "Charge")
        recon = Charge.objects.filter(
            tenant_id=tenant.id, code=disconnects.RECONNECT_CHARGE_CODE, deleted_at__isnull=True
        ).first()
        if recon is None:
            seeded = Charge.objects.filter(
                tenant_id=tenant.id, code="RECON", deleted_at__isnull=True
            ).first()
            if seeded is None:
                print("NO RECON CHARGE: the tenant has no reconnection fee to mirror")
                return 1
            recon = Charge.objects.create(
                tenant_id=tenant.id,
                code=disconnects.RECONNECT_CHARGE_CODE,
                name=seeded.name,
                charge_type=seeded.charge_type,
                amount_rule=seeded.amount_rule,
                amount=seeded.amount,
                gl_account_id=seeded.gl_account_id,
                taxable_default=seeded.taxable_default,
            )
            print(
                f"  configured {recon.code} at {recon.amount} {candidate.currency}, "
                f"mirroring the tenant's own RECON row"
            )
        else:
            print(f"  {recon.code} already configured at {recon.amount}")

        # 1 · the ladder, opened and walked to tier 3 — three `advance` calls.
        disconnects.open_case(actor, candidate.pk, as_of=today - timedelta(days=30))
        for step, day in enumerate((30, 20, 10), start=1):
            case = disconnects.open_case_for(candidate.pk)
            print(f"  before advance {step}: tier={case.tier} state={case.state}")
            if case.tier == disconnects.TIER_3:
                break
            disconnects.advance(actor, candidate.pk, as_of=today - timedelta(days=day))
        case = disconnects.open_case_for(candidate.pk)
        print(f"  ladder at tier={case.tier} state={case.state}")

        # 2 · BR-CUS-100 — a person attests how the tier-3 notice was served.
        notice = disconnects.latest_notice_at_tier(case, disconnects.TIER_3)
        if notice is None:
            print("NO TIER-3 NOTICE: the ladder did not reach tier 3")
            return 1
        # Already-recorded proof is NOT re-pointed — the product refuses it by
        # name, because *"the record a utility shows a regulator … cannot be
        # edited afterwards"*. So this asks before it writes.
        if disconnects.service_proof_for(case, tier=disconnects.TIER_3)["recorded"]:
            print("  tier-3 proof of service already on file — not re-pointed")
        else:
            disconnects.record_proof_of_service(
                actor,
                notice.pk,
                channel=disconnects.TIER_3_REQUIRED_CHANNEL,
                reference="CR094-WAVEB-SEED-0001",
                served_on=today - timedelta(days=9),
                signed_for_on=today - timedelta(days=8),
            )
            print("  tier-3 proof of service recorded (certified mail)")

        # 3 · schedule, then commit. The cut date is in the past so the account
        #     is cut NOW rather than pending — `close_out` needs `cut_on`.
        cut_on = today - timedelta(days=5)
        # `DSC-02.1` — ONE DECISION PER SERVICE, and `commit_cut` refuses a case
        # that names none: *"a cut that names no service cannot fall back on
        # cutting everything"*. So every service on the account is named
        # explicitly, which is what the wizard's step-1 table collects.
        from apps.customers import selectors as customer_selectors

        codes = sorted(set(customer_selectors.service_codes_for(candidate)))
        services = {code: disconnects.TREATMENT_FULL for code in codes} or None
        disconnects.schedule_cut(
            actor,
            candidate.pk,
            cut_on=cut_on,
            as_of=today - timedelta(days=6),
            reason=None,
            services=services,
        )
        print(f"  services marked for full disconnection: {sorted(services or [])}")
        print(f"  cut scheduled for {cut_on}")
        # ⚠ THE STATUS IS WRITTEN ONLY IF THE CUT BILL BILLED. `commit_cut`
        # holds BR-CUS-107's `Disconnected` when billing refused the days up to
        # the cut (`CUT_BILL_BLOCKED_SO_STATUS_HELD`) — *"writing it over a bill
        # billing REFUSED would leave those days billed by nobody"*. So the
        # result is PRINTED rather than assumed: a seed that silently produced a
        # `cut` case on an `active` account would be a fixture that looks right
        # and proves nothing.
        result = disconnects.commit_cut(actor, candidate.pk, cut_on=cut_on, as_of=today)
        print(f"  commit_cut → {result.get('cut_bill') or result}")

        candidate.refresh_from_db()
        case = DisconnectCase.objects.filter(account_id=candidate.pk).order_by("-opened_on").first()
        print(
            f"SEEDED: {candidate.account_no} status={candidate.status.code} "
            f"case={getattr(case, 'case_no', None)} state={getattr(case, 'state', None)} "
            f"cut_on={getattr(case, 'cut_on', None)}"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

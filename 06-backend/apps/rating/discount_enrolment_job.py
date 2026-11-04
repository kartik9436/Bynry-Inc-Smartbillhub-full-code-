# ── Trace ──────────────────────────────────────────────
# Change:  CR-166-BRC10 round 2 task 3 — ruling 3, automatic enrolment.
# Defects: DEF-RAT-9295 (an Automatic discount enrols nobody)
# Rules:   PO 2026-10-03 ruling 3 · BR-RAT-069 (NARROWED for Automatic only) ·
#          BR-RAT-110 (the plan gate) · BR-RAT-076 (Automatic + proof refused) ·
#          CLAUDE.md hard rules 1 (tenant context per utility), 6 (idempotent),
#          7 (a money action writes audit_log)
# Tests:   06-backend/tests/test_cr166_discounts_round2.py ·
#          06-backend/tests/test_cr166_discounts_round2_pg.py
# ───────────────────────────────────────────────────────
"""Automatic enrolment — who gets an Automatic discount, kept current by a job.

HUMAN-OWNED 🔒 · HUMAN-REVIEW-PENDING — AI-authored 2026-10-03 under the PO
ruling of 2026-08-09. It decides which accounts are GRANTED a subsidy, which is
🔒 rating math. Row in `12-governance/09-human-review-ledger.md` (CR-166-BRC10
r2 t3); not RATIFIED without a recorded human sign-off.

THE RULING
----------
PO 2026-10-03 (3), as put and accepted (*"all as recommended"*): **"Automatic"
enrols every account on a plan carrying it that meets a condition the system
can check** — Everyone on the plan · Autopay is on · Paperless billing is on ·
Government or municipal account. A *customer shows proof* condition cannot be
Automatic. `DEF-RAT-9295` reproduced the gap: AUTOPAY and PAPERLESS offered to
75 units, 6 accounts with autopay on, **0 enrolled** — nothing in the code read
`enrolment_mode = automatic` except validation.

`BR-RAT-069` (*"a plan attachment discounts NOBODY … the bill run reads
enrolments"*) is NARROWED, not broken: the bill still reads ENROLMENTS and a
plan attachment still grants nothing by itself. What changes is that for an
Automatic discount the product WRITES the enrolment for every qualifying
account, and ENDS it when the account stops qualifying.

WHAT ONE SYNC DOES, FOR ONE DISCOUNT
------------------------------------
1. The version that decides: the one in force today, or — when the discount
   was approved with a later start — the next one. `enrolment_mode` must be
   `automatic` and its who-qualifies value a SYSTEM check (`check_key`);
   otherwise the sync does nothing.
2. The population: open accounts on units whose plan carries the discount on
   that day (the binding window, ruling 2), meeting the check
   (`seams.accounts_meeting` — autopay is the ELECTION and not the NSF
   sanction, the pair `payments.autopay.is_enrolled` reads).
3. ENROL every qualifying account not already enrolled — `enrolled_on` = that
   day, `verification_status = not_required` (the system checked it).
   Idempotent by `uq_discount_enrolments_current`; computed as a set
   difference in SQL, so a re-run writes nothing (hard rule 6).
4. END every open enrolment of the discount whose account no longer qualifies
   — **from the next bill** (`CR-166` §7 item 7): `ended_on` is the day BEFORE
   the sync, never earlier than the enrolment itself, reason
   `no_longer_qualifies`. A bill for a service date before today keeps it.

   ⚖️ **AMENDED 2026-10-06 FOR AUTOPAY AND PAPERLESS (`DEF-RAT-9833`).** PO D2
   (b), verbatim: *"Offer Autopay and Paperless at move-in as drawn … Clark has
   to add those discounts. clark can add it later also on account"*; ruling 4,
   verbatim: *"so when clark make it on or adds it you ahve to set it up so
   that next billing cycle pick it"* (read as (b): kept matched to the setting).
   A clerk may now add either by hand, which switches the setting On; so for
   those two checks an enrolment is KEPT while the setting is On — an account
   still pending activation counted — and ended only when the setting goes
   Off, the account closes or its plan stops carrying it. Switching the setting
   On enrols at once (`discount_services.enrol_for_settings`), not tonight.
   Municipal account and *Everyone on the plan* keep the rule above exactly.

⚠ **ONE AUDIT ROW PER SYNC THAT CHANGED SOMETHING, NAMING EVERY ACCOUNT BY
NUMBER** (hard rule 7, B14 rule 31). Not one row per enrolment: at T5 a first
sync of *Everyone on the plan* is 40,000 enrolments, and 40,000 audit inserts in
an approval request would outlive the web worker's sixty seconds
(`GUNICORN_TIMEOUT`). The enrolments themselves are ONE `bulk_create`.

WHEN IT RUNS
------------
On approval (`approve_discount_version`), when a live discount's who-qualifies
or enrolment mode changes (`update_discount_details`), when a plan's discounts
are saved (`services._apply_plan_children`), and **every night for every
utility** (`install()` below; `manage.py sync_discount_enrolments` is the same
sweep by hand) — which is what catches an account turning autopay on or off,
moving plan, or closing: those are customers' writes, and customers does not
call rating on each of them.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from importlib import import_module
from typing import Any

from django.db import transaction
from django.db.models import Q

from apps.rating import discount_lists
from apps.rating import discounts as discount_models
from apps.rating import models as rating_models
from apps.rating import seams
from core import audit as core_audit
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.rating")

END_REASON = "no_longer_qualifies"

#: `DEF-RAT-9833` (PO D2 (b) and ruling 4, 2026-10-06) — the two checks that
#: mirror a setting on the account; `discount_services.SETTING_CHECKS` is the
#: same pair (named here from the model's constants to keep this module free of
#: an import cycle with `discount_services`).
SETTING_CHECKS = (discount_models.CHECK_AUTOPAY, discount_models.CHECK_PAPERLESS)

BEAT_ENTRY = "rating.discount_enrolment_sync"
SYNC_TASK = "smartbillhub.rating.discount_enrolment_sync"
SYNC_ONE_TASK = "smartbillhub.rating.discount_enrolment_sync_one"
SYNC_HOUR = 2
SYNC_MINUTE = 40
_SYNC_TASK: Any = None
_SYNC_ONE_TASK: Any = None


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _deciding_version(discount: Any, today: date) -> Any:
    """The version in force today, else the next approved one, else None."""
    from apps.rating import discount_services

    version = discount_services.active_version(discount, today)
    if version is not None:
        return version
    return (
        discount_models.DiscountVersion.objects.filter(
            tenant_id=_tenant_id(),
            discount=discount,
            status=discount_models.VERSION_ACTIVE,
            effective_from__gt=today,
        )
        .order_by("effective_from", "version_no")
        .first()
    )


def _units_on_carrying_plans(discount: Any, day: date) -> Any:
    """Unit ids whose plan offers this discount on `day` — a subquery."""
    plan_ids = (
        discount_models.PlanDiscountRule.objects.filter(tenant_id=_tenant_id(), discount=discount)
        .filter(Q(available_from__isnull=True) | Q(available_from__lte=day))
        .filter(Q(available_to__isnull=True) | Q(available_to__gte=day))
        .values("rate_plan_id")
    )
    return (
        rating_models.UnitPlanAssignment.objects.filter(
            tenant_id=_tenant_id(), rate_plan_id__in=plan_ids, assigned_from__lte=day
        )
        .filter(Q(assigned_to__isnull=True) | Q(assigned_to__gte=day))
        .values("unit_id")
    )


def sync_discount(discount: Any, *, actor: Any = None, today: date | None = None) -> dict[str, Any]:
    """Bring ONE Automatic discount's enrolments in line with who qualifies.

    Returns `{enrolled, ended, check}` — zeros and `check: None` for a discount
    that is not Automatic or whose who-qualifies is not a system check."""
    today = today or seams.tenant_today()
    out: dict[str, Any] = {"discount": discount.code, "enrolled": 0, "ended": 0, "check": None}
    if discount.status == discount_models.DISCOUNT_DRAFT:
        return out
    if discount.retire_on is not None and discount.retire_on < today:
        return out
    version = _deciding_version(discount, today)
    if version is None or version.enrolment_mode != discount_models.ENROLMENT_AUTOMATIC:
        return out
    check = discount_lists.check_key_for(version.eligibility_code)
    out["check"] = check
    if check is None:
        return out
    day = max(today, version.effective_from)
    qualifying = seams.accounts_meeting(_units_on_carrying_plans(discount, day), check)
    open_rows = discount_models.DiscountEnrolment.objects.filter(
        tenant_id=_tenant_id(), discount=discount, ended_on__isnull=True
    )
    with transaction.atomic():
        enrolled_ids = list(
            qualifying.exclude(id__in=open_rows.values("account_id")).values_list("id", flat=True)
        )
        discount_models.DiscountEnrolment.objects.bulk_create(
            [
                discount_models.DiscountEnrolment(
                    tenant_id=_tenant_id(),
                    discount=discount,
                    account_id=account_id,
                    enrolled_on=day,
                    enrolled_by_id=core_audit.actor_user_id(actor) if actor else None,
                    verification_status=discount_models.VERIFICATION_NOT_REQUIRED,
                    currency=version.currency,
                )
                for account_id in enrolled_ids
            ]
        )
        # ⚖️ PO ruling 4, 2026-10-06 (reading (b), `DEF-RAT-9833`): for
        # Autopay and Paperless the discount is KEPT MATCHED to the setting and
        # a clerk's add is never undone while the setting is On — so the set an
        # enrolment survives in counts an account still pending activation (a
        # move-in that has not started). It still ends when the setting goes
        # Off, the account closes, or its plan stops carrying the discount
        # (BR-RAT-110). The other checks keep today's rule exactly.
        keeping = (
            seams.accounts_meeting(_units_on_carrying_plans(discount, day), check, include_pending=True)
            if check in SETTING_CHECKS
            else qualifying
        )
        leaving = list(
            open_rows.exclude(account_id__in=keeping).values_list(
                "id", "account_id", "enrolled_on"
            )
        )
        yesterday = today - timedelta(days=1)
        for enrolment_id, _account_id, enrolled_on in leaving:
            discount_models.DiscountEnrolment.objects.filter(pk=enrolment_id).update(
                ended_on=max(enrolled_on, yesterday), end_reason=END_REASON
            )
        out["enrolled"] = len(enrolled_ids)
        out["ended"] = len(leaving)
        if enrolled_ids or leaving:
            numbers = seams.account_numbers(
                [*enrolled_ids, *[row[1] for row in leaving]]
            )
            core_audit.write_row(
                action="discount.automatic_enrolments_synced",
                entity_type="discount",
                entity_id=discount.id,
                actor_user_id=core_audit.actor_user_id(actor) if actor else None,
                before=None,
                after={
                    "discount": discount.code,
                    "check": check,
                    "on_day": str(day),
                    "enrolled": sorted(numbers.get(str(one), str(one)) for one in enrolled_ids),
                    "ended": sorted(numbers.get(str(row[1]), str(row[1])) for row in leaving),
                    "ended_on": str(yesterday) if leaving else None,
                },
            )
    return out


def sync_tenant(*, actor: Any = None, today: date | None = None) -> list[dict[str, Any]]:
    """Every Automatic discount of the CURRENT utility (context already set)."""
    results = []
    automatic_ids = (
        discount_models.DiscountVersion.objects.filter(
            tenant_id=_tenant_id(),
            status=discount_models.VERSION_ACTIVE,
            enrolment_mode=discount_models.ENROLMENT_AUTOMATIC,
        )
        .values_list("discount_id", flat=True)
        .distinct()
    )
    for discount in discount_models.Discount.objects.filter(
        tenant_id=_tenant_id(), pk__in=list(automatic_ids)
    ).order_by("code"):
        results.append(sync_discount(discount, actor=actor, today=today))
    return results


def sync_one(subdomain: str) -> dict[str, Any]:
    """One utility's nightly sweep, inside its own tenant context (rule 1)."""
    tenant_id = core_tenancy.tenant_id_for_slug(subdomain)
    if tenant_id is None:
        return {"subdomain": subdomain, "swept": False, "reason": "no such utility"}
    with core_tenancy.tenant_context(tenant_id):
        results = sync_tenant()
    return {"subdomain": subdomain, "swept": True, "discounts": results}


def _live_subdomains() -> tuple[str, ...]:
    try:
        found = getattr(import_module("apps.tenancy.selectors"), "live_tenant_subdomains", None)
    except ImportError:  # pragma: no cover
        return ()
    if not callable(found):
        return ()
    try:
        return tuple(str(entry) for entry in (found() or ()))
    except Exception:  # noqa: BLE001 — a broken read must not stop the beat
        logger.exception("the live-utility read failed; this firing synced nobody")
        return ()


def sync_all() -> dict[str, Any]:
    """ONE firing: hand every live utility its own sweep (a fan-out, so one
    utility's slow sync cannot delay another's — `session_cleanup`'s shape)."""
    subdomains = _live_subdomains()
    if _SYNC_ONE_TASK is None:
        return {
            "utilities": len(subdomains),
            "fanned_out": False,
            "results": [sync_one(subdomain) for subdomain in subdomains],
        }
    for subdomain in subdomains:
        _SYNC_ONE_TASK.delay(subdomain)
    return {"utilities": len(subdomains), "fanned_out": True}


def beat_schedule() -> dict[str, dict[str, Any]]:
    """The beat entry as DATA (asserted without a broker)."""
    try:
        from celery.schedules import crontab

        when: Any = crontab(hour=SYNC_HOUR, minute=SYNC_MINUTE)
    except Exception:  # noqa: BLE001 — celery absent; see install()
        when = {"hour": SYNC_HOUR, "minute": SYNC_MINUTE}
    return {BEAT_ENTRY: {"task": SYNC_TASK, "schedule": when, "args": (), "options": {}}}


def install(app: Any = None) -> dict[str, Any]:
    """Register the nightly sweep on the celery app. Idempotent; a missing
    celery is not an error (`identity.session_cleanup.install`'s posture)."""
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001
            logger.info("discount enrolment sync not scheduled: celery unavailable (%s)", problem)
            return {"installed": False, "reason": str(problem)}
        app = celery_app
    global _SYNC_TASK, _SYNC_ONE_TASK
    _SYNC_ONE_TASK = app.task(name=SYNC_ONE_TASK, bind=False)(sync_one)
    _SYNC_TASK = app.task(name=SYNC_TASK, bind=False)(sync_all)
    schedule = beat_schedule()
    existing = dict(getattr(app.conf, "beat_schedule", None) or {})
    existing.update(schedule)
    app.conf.beat_schedule = existing
    return {"installed": True, "entry": BEAT_ENTRY, "schedule": schedule}

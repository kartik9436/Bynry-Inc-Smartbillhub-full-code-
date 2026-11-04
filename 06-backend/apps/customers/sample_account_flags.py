# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-011 (account notes) · CR-089 wave I task I6
#           Screens: S15 (PRM-03, Account tab) · S21 (the account's own page)
# Rules:    BR-PAY-013 (N bounces → cash-only / no autopay) · BR-CUS-059
#           (autopay is the customer's election) · BR-CUS-028 / BR-BIL-036
#           (paperless and SMS ADD a channel; print is the floor) ·
#           BR-CUS-064 (preferred language) · BR-PAY-018 (bad address) ·
#           BR-CUS-058 (credit tier is a COMPUTED cache) · BR-CUS-172
#           (the utility's own legacy account reference) · BR-CUS-035 (notes) ·
#           BR-TEN-057 (`is_sample` is a column on the OWNING row) ·
#           BR-TEN-063 (a seeder is idempotent) · CLAUDE.md law 14 (a failed
#           statement poisons the whole PostgreSQL transaction — SAVEPOINTS)
# Tests:    06-backend/tests/test_cr089_i_unit_account_facts.py
# Impacts:  apps/customers/sample_data.py (`seed_sample_records` calls this
#           last) · apps/customers/unit_account_facts.py (what reads them)
# ───────────────────────────────────────────────────────
"""**`DEF-CUS-4692` — NINE ACCOUNT COLUMNS POPULATED ON ZERO ROWS.**

Measured 2026-09-08 on both demo utilities, 78 accounts on `brazosbend` and 73
on `pine-hill`: `cash_only_no_autopay`, `bad_address`, `nsf_count`,
`tax_exempt`, `paperless`, `sms_reminders`, `preferred_language`, `credit_tier`
and `external_ref` were **zero everywhere**. The columns exist, the migrations
pass, the models pass — and a screen that reads one cannot be tested at all,
because there is no true case to render.

⚠ **DRAWING THEM IS NOT THE FIX; SOMETHING HAS TO WRITE THEM.** That is the CR's
own sentence and it is the whole of this file. Without it `I3` (*autopay is read
together with cash-only*) and `I4` (*five money states are stated*) would each
have one branch that no walkthrough could ever reach — which is a screen proved
green over a state nobody has seen.

**IT WRITES THROUGH THE PRODUCT'S OWN DOORS WHEREVER ONE EXISTS.**
The cash-only sanction is not stamped on: `services.record_nsf` is called
`nsf_privilege_n` times and **BR-PAY-013 trips the flag itself**, with its own
audit row. So the fixture is also a proof that the rule works, and if the rule
ever stops working the fixture stops producing the case.

**TWO OF THE NINE HAVE NO DOOR AT ALL, AND THAT IS REPORTED RATHER THAN
WORKED AROUND** (see `NO_DOOR` below): `external_ref` (writable only inside an
import, `IMPORT_ACCOUNT_FIELDS`), and `credit_tier` (`BR-CUS-058`: *"COMPUTED
from payment history — there is no input path"*, and `credit_tier_rules` is
unbuilt). Those two are written directly, each with its reason, and
`credit_tier` is deliberately **not rendered on any screen** — a grade nobody
computed must not appear as one.

⚠ **`bad_address` WAS THE THIRD, AND IT WAS STAMPED ON HERE UNTIL 2026-09-23
(`DEF-PAY-6342`) — WHICH IS HOW THE DEFECT HID.** The seed set the column
directly, so a demo account read **Bad address: Yes** and anybody checking the
feature on sample data saw it working — while in the product nothing wrote the
column at all. A seed must never set a flag that only a workflow is supposed to
set. It now marks a piece of post returned through payments' own writer
(`returned_mail.mark_returned`), which records the event, audits it and asks
customers to raise the flag — the same three acts a clerk's *Mark returned*
performs. ⚠ **The piece names no queued letter**: this seeder runs before
billing has queued any, so the demo return's *went to* is unknown, which is the
third branch of the clear step and a real one (a letter queued before the
service-address fallback carried no address).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from django.db import transaction

from core import tenancy as core_tenancy

from . import models, seams, services

logger = logging.getLogger(__name__)

#: The columns with no writing door in the product today. Named as data so the
#: next reader meets the list rather than reconstructing it from comments.
#: `bad_address` LEFT this map on 2026-09-23 — it has a door now (see above).
NO_DOOR: dict[str, str] = {
    "external_ref": (
        "BR-CUS-172 — the utility's own account number in the system they migrated off. "
        "IMPORT_ACCOUNT_FIELDS accepts it and no counter-facing path does, which is "
        "correct: a legacy id is a fact about a migration, not something a clerk types."
    ),
    "credit_tier": (
        "BR-CUS-058 — a COMPUTED cache whose rules live in the unbuilt "
        "`credit_tier_rules`. REFUSED_FIELDS says it outright: 'COMPUTED from payment "
        "history — there is no input path'. Seeded so the column is not empty on every "
        "row in the product, and DELIBERATELY NOT RENDERED: nothing computes it, so a "
        "value on screen would read as a grade this utility awarded."
    ),
}

#: What each seeded account demonstrates. One row per seat, in the order they are
#: taken, so a reader can go and look at the demo and find them.
#:
#: ⚠ **THE SEATS ARE CHOSEN BY ROLE AND NOT BY ACCOUNT NUMBER.** The two demo
#: utilities number their accounts differently (`A-11902` on one, `AC-2026-…`
#: and `R-000n` alongside), so a hard-coded list would populate one tenant and
#: silently populate nothing on the other — which is `DEF-CUS-4692`'s own shape
#: repeated. Seat 1 is found by its PROTECTION, the rest by a stable ordering.
SEAT_MEDICAL = "the protected one"
SEAT_SANCTIONED = "the sanctioned one"
SEAT_REACH = "the reachable one"
SEAT_EXEMPT = "the exempt one"
SEAT_MIGRATED = "the migrated one"

#: `I5`'s two notes, on the account whose protection `I1` puts in the banner —
#: so the pin and the banner say the same thing about the same customer.
PINNED_NOTE_TITLE = "Medical protection"
VISIBLE_NOTE_TITLE = "Meter access"
NOTES: tuple[dict[str, Any], ...] = (
    {
        "title": PINNED_NOTE_TITLE,
        "body": (
            "A medical certificate is on file. Do not arrange a disconnection for this "
            "address without speaking to a supervisor first."
        ),
        "pinned": True,
        "customer_visible": False,
    },
    {
        "title": VISIBLE_NOTE_TITLE,
        "body": "Dog in the side yard — ring first.",
        "pinned": False,
        # BR-CUS-035: CAPTURED and INERT in v1. It is stored because what a clerk
        # marked customer-visible in June is a fact about what they intended, and
        # nothing in this repo may read it as a portal permission.
        "customer_visible": True,
    },
)

#: `BR-CUS-064`. `es-MX` rather than `es`, because the two are different
#: catalogues in this product and a demo that cannot tell them apart teaches the
#: wrong thing. Validated against `seams.tenant_languages()` before it is used —
#: a tenant that does not offer it gets no language rather than a refusal.
PREFERRED_LANGUAGE = "es-MX"

#: `BR-CUS-172` — shaped like a real legacy id and obviously not one of ours.
LEGACY_REF = "LEG-88214"

#: `BR-CUS-058`'s vocabulary is unbuilt, so this is a plain letter and it is
#: written for the column's sake alone. See `NO_DOOR`.
CREDIT_TIER = "B"

#: `BR-CUS-042`/`B4.2` — a tax exemption needs a reference and an end date, or it
#: is a permanent exemption nobody signed (the same reasoning
#: `ck_protection_lifetime` applies to a medical certificate).
TAX_EXEMPT_REF = "TX-EX-4471"
TAX_EXEMPT_EXPIRES = date(2027, 6, 30)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _medical_seat() -> models.Account | None:
    """The account `I1`'s banner is about — found by its protection, not by id."""
    from .disconnects import PROTECTION_MEDICAL, AccountProtection

    row = (
        AccountProtection.objects.filter(
            tenant_id=_tenant_id(), kind=PROTECTION_MEDICAL, lifted_on__isnull=True
        )
        .order_by("effective_from", "id")
        .first()
    )
    if row is None:
        return None
    return models.Account.objects.filter(tenant_id=_tenant_id(), pk=row.account_id).first()


def _seats() -> dict[str, models.Account]:
    """One account per role, chosen deterministically and never overlapping.

    Everything is ordered by `account_no` so a replay picks the same rows, and
    every seat is an account that OCCUPIES a unit — the tab this fixture exists
    for is reached from a unit, so an account with no unit could never be seen.
    """
    seats: dict[str, models.Account] = {}
    taken: set[Any] = set()

    medical = _medical_seat()
    if medical is not None:
        seats[SEAT_MEDICAL] = medical
        taken.add(medical.pk)

    # The sanctioned seat must be an account the customer ELECTED autopay on:
    # `I3`'s whole point is that *autopay on* alone is the wrong answer, and an
    # account with autopay off would demonstrate nothing.
    pool = models.Account.objects.filter(
        tenant_id=_tenant_id(), unit_id__isnull=False, closed_at__isnull=True
    ).order_by("account_no", "id")
    for account in pool.filter(autopay=True):
        if account.pk not in taken:
            seats[SEAT_SANCTIONED] = account
            taken.add(account.pk)
            break

    for role in (SEAT_REACH, SEAT_EXEMPT, SEAT_MIGRATED):
        for account in pool:
            if account.pk not in taken:
                seats[role] = account
                taken.add(account.pk)
                break
    return seats


def _patch(actor: Any, account: models.Account, changes: dict[str, Any], *, what: str) -> int:
    """One `PATCH /accounts/{id}` through the product's own door, in a SAVEPOINT.

    ⚠ **THE SAVEPOINT IS NOT TIDINESS — CLAUDE.md law 14.** On PostgreSQL one
    failed statement aborts the WHOLE transaction, so a plain `try/except
    continue` would lose every later seat at COMMIT while passing the entire
    suite on SQLite, which has no aborted-transaction state at all.
    """
    try:
        with transaction.atomic():
            services.update_account(actor, str(account.pk), changes)
    except Exception as exc:  # noqa: BLE001 — named, never swallowed
        logger.info(
            "sample data (CR-089 I6): %s kept no %s — %s: %s",
            account.account_no,
            what,
            type(exc).__name__,
            exc,
        )
        return 0
    return 1


def _seed_user(actor: Any) -> Any:
    """The REAL user behind the orchestrator's stand-in, carrying its role.

    ⚠ `DEF-CUS-9080` — the orchestrator passes `SimpleNamespace(id, pk, role,
    user)`, and `update_account` writes account history whose `recorded_by` is a
    foreign key into `users`. The stand-in was refused (*"must be a User
    instance"*), so the delivery election and the tax exemption were never
    stored on any seeded tenant. The seed now acts as the user the stand-in
    names, with the stand-in's role attached the way sign-in attaches it, so
    the history says who seeded the change. An actor that already IS a model
    row, or names no user, is used as it is.
    """
    if getattr(actor, "_meta", None) is not None:
        return actor
    user = getattr(actor, "user", None)
    if user is None or getattr(user, "_meta", None) is None:
        return actor
    user.role = getattr(actor, "role", None) or getattr(user, "role", None)
    return user


def seed_account_flags(actor: Any) -> int:
    """`I6` — after this runs, at least one account carries each of the nine.

    Idempotent (`BR-TEN-063`): every seat is skipped when it already carries its
    mark, so a replay writes nothing and a re-run after a partial failure
    finishes the job rather than doubling it.
    """
    actor = _seed_user(actor)
    written = 0
    seats = _seats()

    # ── seat 1 · the protected one — `I5`'s two notes ───────────────────────
    medical = seats.get(SEAT_MEDICAL)
    if medical is not None:
        for note in NOTES:
            if models.AccountNote.objects.filter(
                tenant_id=_tenant_id(), account=medical, title=note["title"]
            ).exists():
                continue
            try:
                with transaction.atomic():  # law 14 — see `_patch`
                    services.create_account_note(actor, str(medical.pk), dict(note))
            except Exception as exc:  # noqa: BLE001 — named, never swallowed
                logger.info(
                    "sample data (CR-089 I6): %s kept no note %r — %s: %s",
                    medical.account_no,
                    note["title"],
                    type(exc).__name__,
                    exc,
                )
                continue
            written += 1

    # ── seat 2 · the sanctioned one — `I3`'s negative case ──────────────────
    #
    # ⚠ **THE FLAG IS NOT SET HERE. THE RULE SETS IT.** `services.record_nsf`
    # increments the count and BR-PAY-013 decides; calling it N times is a
    # PROOF that the sanction trips, and the day the rule stops tripping this
    # fixture stops producing the case rather than papering over it.
    sanctioned = seats.get(SEAT_SANCTIONED)
    if sanctioned is not None and not sanctioned.cash_only_no_autopay:
        threshold = seams.nsf_privilege_threshold()
        if threshold is None:
            # The threshold lives once, in the tenant's settings, and this file
            # does not carry a copy of the ratified default — `record_nsf` takes
            # exactly the same posture and says why at length.
            logger.info(
                "sample data (CR-089 I6): %s kept no cash-only sanction — the tenant's "
                "nsf_privilege_n could not be read, and the shipped default of 2 is not "
                "substituted here (BR-PAY-013).",
                sanctioned.account_no,
            )
        else:
            for _ in range(max(int(threshold), 1) - int(sanctioned.nsf_count or 0)):
                try:
                    with transaction.atomic():  # law 14
                        services.record_nsf(str(sanctioned.pk), actor=actor)
                except Exception as exc:  # noqa: BLE001
                    logger.info(
                        "sample data (CR-089 I6): %s kept no bounce — %s: %s",
                        sanctioned.account_no,
                        type(exc).__name__,
                        exc,
                    )
                    break
            else:
                written += 1

    # ── seat 3 · the reachable one — the delivery election ──────────────────
    reach = seats.get(SEAT_REACH)
    if reach is not None and not (reach.paperless or reach.sms_reminders):
        changes: dict[str, Any] = {"paperless": True, "sms_reminders": True}
        # A language the tenant does not offer is refused by `_validate_account`,
        # so it is checked here rather than caught: an offered language is a
        # tenant setting and a demo must not depend on one being present.
        if PREFERRED_LANGUAGE in (seams.tenant_languages() or ()):
            changes["preferred_language"] = PREFERRED_LANGUAGE
        written += _patch(actor, reach, changes, what="delivery election")

    # ── seat 4 · the exempt one — `I4`'s tax row ────────────────────────────
    exempt = seats.get(SEAT_EXEMPT)
    if exempt is not None and not exempt.tax_exempt:
        written += _patch(
            actor,
            exempt,
            {
                "tax_exempt": True,
                "tax_exempt_ref": TAX_EXEMPT_REF,
                "tax_exempt_expires": TAX_EXEMPT_EXPIRES.isoformat(),
            },
            what="tax exemption",
        )

    # ── seat 5 · the migrated one — the two with no door ────────────────────
    #
    # ⚠ **A DIRECT WRITE, AND EACH COLUMN'S REASON IS IN `NO_DOOR` ABOVE.**
    # This is NOT a seeder reaching past a validated write path: there is no
    # write path to reach past. Neither is a 🔒 sensitive column — no money, no
    # ledger, no RLS policy, no idempotency key — and the money columns beside
    # them (`balance`, `deposit_on_file`) are deliberately not touched, because
    # those DO have doors and a seeder must use them.
    migrated = seats.get(SEAT_MIGRATED)
    if migrated is not None and migrated.external_ref is None:
        try:
            with transaction.atomic():  # law 14
                models.Account.objects.filter(tenant_id=_tenant_id(), pk=migrated.pk).update(
                    external_ref=LEGACY_REF,
                    credit_tier=CREDIT_TIER,
                )
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "sample data (CR-089 I6): %s kept neither door-less column — %s: %s",
                migrated.account_no,
                type(exc).__name__,
                exc,
            )
        else:
            written += 1

    # ── seat 5 again · its post came back — THROUGH THE DOOR (`DEF-PAY-6342`) ─
    #
    # ⚠ **THE FLAG IS NOT SET HERE. MARKING THE POST RETURNED SETS IT** — the
    # seat-2 posture (`record_nsf` trips cash-only; this trips bad address). The
    # day returned-mail handling stops raising the flag, this fixture stops
    # producing the case instead of papering over it, which is exactly what the
    # old direct write did for six weeks.
    if migrated is not None and not migrated.bad_address:
        written += _mark_sample_return(actor, migrated)
    return written


def _mark_sample_return(actor: Any, account: models.Account) -> int:
    """One piece of post returned for `account`, through payments' writer.

    In a SAVEPOINT for law 14's reason (see `_patch`). Idempotent by the flag:
    the caller skips an account already flagged, so a replay marks nothing.
    """
    from . import payments_seam

    try:
        with transaction.atomic():  # law 14
            result = payments_seam.mark_returned(
                account_id=account.pk,
                returned_on=seams.tenant_today(),
                source_type="invoice",
                reason="sample data",
                actor=actor,
            )
    except Exception as exc:  # noqa: BLE001 — named, never swallowed
        logger.info(
            "sample data (DEF-PAY-6342): %s kept no returned post — %s: %s",
            account.account_no,
            type(exc).__name__,
            exc,
        )
        return 0
    if result is None or not getattr(result, "flag_raised", False):
        logger.info(
            "sample data (DEF-PAY-6342): %s — the return was not recorded or did not raise "
            "the flag (%s). Nothing is stamped in its place.",
            account.account_no,
            getattr(result, "detail", None) or "payments publishes no returned-mail writer",
        )
        return 0
    return 1


def flag_coverage() -> dict[str, int]:
    """How many accounts carry each of the nine — the figure `DEF-CUS-4692` is.

    Published so a check can assert it rather than a person counting: **a column
    with no value is invisible to every check this repo has**, which is that
    defect's own escape reason. `tests/test_cr089_i_unit_account_facts.py` reads
    this, and so does the lane's walkthrough.
    """
    rows = models.Account.objects.filter(tenant_id=_tenant_id())
    return {
        "cash_only_no_autopay": rows.filter(cash_only_no_autopay=True).count(),
        "bad_address": rows.filter(bad_address=True).count(),
        "nsf_count": rows.filter(nsf_count__gt=0).count(),
        "tax_exempt": rows.filter(tax_exempt=True).count(),
        "paperless": rows.filter(paperless=True).count(),
        "sms_reminders": rows.filter(sms_reminders=True).count(),
        "preferred_language": rows.exclude(preferred_language__isnull=True).count(),
        "credit_tier": rows.exclude(credit_tier__isnull=True).count(),
        "external_ref": rows.exclude(external_ref__isnull=True).count(),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-089 wave I task I6 · DEF-CUS-4692 · PUJ-41
# generated: 2026-09-08 by the CR-089 wave I build lane
# checklist: A✔ B=n/a C✔ D=n/a E✔(called last by seed_sample_records) F✔ G✔ H=n/a
# gates: pytest 06-backend/tests/test_cr089_i_unit_account_facts.py · law 14 (every write in its own SAVEPOINT)
# amended: 2026-09-23 (DEF-PAY-6342) — `bad_address` is no longer stamped: seat 5's post is marked returned through payments' writer and the flag follows. The return event carries no `is_sample` (payments' table has none), exactly like the notes below
# exceptions: E3 `account_notes` carries NO `is_sample` column, so the two notes are NOT tagged and `--remove` cannot sweep them — BR-TEN-057 working rather than a gap papered over, exactly as `_seed_cr030_demo_notes` records for its three · E3 two columns are written directly because no door exists; each reason is in `NO_DOOR` and each is REPORTED · E3 `credit_tier` is populated and rendered NOWHERE
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

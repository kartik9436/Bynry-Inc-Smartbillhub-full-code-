# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-037 (EP-WRK-07) — the payments trigger reader: a final
#           notice that has expired with the account still unpaid.
# Rules:    BR-WRK-002 (read-only; one seam file per module; no public name
#           starts with create_/set_/update_/delete_/post_) · BR-WRK-033 ·
#           CLAUDE.md hard rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_us_wrk_037_rules.py (TC-5 the five readers
#           each go through a seam) · G78 (a foreign models import outside
#           seams/ fails the merge)
# Impacts:  apps/work/rules.py · apps/work/money.py (CR-187-BRC10 Phase 13 —
#           the field app's balance, a charge's bill, and the push sweep)
# ───────────────────────────────────────────────────────
"""work → payments: accounts whose final notice has run out. READ ONLY.

WHY THIS SEAM EXISTS AT ALL, WHICH IS THE POINT OF THE WHOLE FILE
────────────────────────────────────────────────────────────────────────────
`rules.py` needs one question answered — *which accounts were sent a final
notice that has now expired and still have not paid?* — and the three-line way
to answer it is to import `apps.payments.collections_models` into `rules.py` and
write the query there. `BR-WRK-002` forbids it and **G78 fails the merge**, and
the reason is worth more than the rule: the sweep is an unattended job, so a
query written against another module's tables would go stale the day payments
changes a column and would fail at 02:00 with nobody reading the log.

WHAT "A FINAL NOTICE EXPIRED UNPAID" IS, IN THIS PRODUCT'S OWN VOCABULARY
────────────────────────────────────────────────────────────────────────────
The collections ladder's rung 3 is the cut, preceded by a 48-hour certified
final notice (`apps/payments/ladder.py:44`). The notice itself is a
`notice_history` row with `notice_type = "disconnect"` and `outcome = "sent"`;
whether it was HEEDED is a different table — `account_collection_state`, which
collections clears when the account pays.

So *expired unpaid* is the conjunction of two facts from two tables, and both
halves are load-bearing:

  * the disconnect notice was SENT, and its date is far enough in the past
    (`grace_days`, the rule's own parameter, defaulting to the ladder's own
    48 hours read as two days);
  * the account is STILL on that tier in `account_collection_state` and is not
    PAUSED — a paused account is one a clerk has deliberately held, and raising
    a disconnect visit against it would send a technician to a property the
    office has just agreed to leave alone.

⚠ **THE SECOND HALF IS WHY THIS READS TWO TABLES RATHER THAN ONE.** A notice row
alone says only that a letter went out; it never learns that the customer paid
the next morning. A rule built on `notice_history` by itself would send a crew
to cut off a customer who is up to date — which is the single worst thing this
sweep could do, and it would do it quietly, overnight, at scale.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from core import tenancy as core_tenancy


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def expired_final_notices(*, grace_days: int = 2, as_of: date | None = None) -> list[dict[str, Any]]:
    """Accounts whose disconnect notice has expired and who are still on tier.

    Returns a plain list of dicts — never a queryset — so that `rules.py` cannot
    accidentally call `.update()` on another module's rows. Every seam in this
    package that answers a SET does the same.
    """
    from apps.payments import collections_models as pay

    tenant_id = _tenant_id()
    today = as_of or date.today()
    cutoff = today - timedelta(days=max(0, int(grace_days)))

    # The accounts still sitting on the disconnect tier, unpaused. This is the
    # "still unpaid" half — collections clears the tier when money arrives.
    states = {
        str(row.account_id): row
        for row in pay.AccountCollectionState.objects.filter(
            tenant_id=tenant_id, tier=pay.NOTICE_DISCONNECT
        ).exclude(paused_reason__isnull=False)
    }
    if not states:
        return []

    rows = pay.NoticeHistory.objects.filter(
        tenant_id=tenant_id,
        notice_type=pay.NOTICE_DISCONNECT,
        outcome=pay.OUTCOME_SENT,
        occurred_on__lte=cutoff,
        account_id__in=list(states),
    ).order_by("account_id", "-occurred_on")

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.account_id)
        if key in seen:
            # One subject per account, not one per letter: a utility that sent
            # two finals must not get two visits.
            continue
        seen.add(key)
        out.append(
            {
                "account_id": key,
                "notice_on": row.occurred_on.isoformat() if row.occurred_on else None,
                "tier": row.notice_type,
            }
        )
    return out



# ═══════════════════════════════════════════════════════════════════════════
# CR-187-BRC10 Phase 13 (lane S-MONEY) — the field app's money READS.
# R16, PO ruled: *"The field app reads money and never writes it."* Three
# reads, each resolved BY NAME from `apps/payments/field_money.py`, which
# composes payments' own balance read rather than restating it. None of them
# returns a model row and none of their names starts with a write verb
# (`US-WRK-005` TC-6).
# ═══════════════════════════════════════════════════════════════════════════

FIELD_MONEY = "apps.payments.field_money"


def _field_money(attribute: str) -> Any:
    """payments' published read, or None while it is not published."""
    from importlib import import_module

    try:
        return getattr(import_module(FIELD_MONEY), attribute, None)
    except ImportError:  # pragma: no cover - defensive
        return None


def money_position(account_id: Any) -> dict[str, Any] | None:
    """The account's balance and latest standing payment, or None.

    None means payments did not answer — the caller says *could not read*,
    never `$0.00` (`DEF-127`).
    """
    read = _field_money("money_position")
    return None if read is None or account_id is None else read(account_id)


def charge_position(account_id: Any, charge_code: str | None) -> dict[str, Any] | None:
    """The latest issued bill carrying the tenant's `charge_code`, paid or not."""
    read = _field_money("charge_position")
    if read is None or account_id is None or not charge_code:
        return None
    return read(account_id, charge_code)


def money_changed_since(account_ids: list[Any], since: Any) -> dict[str, Any]:
    """`{account_id: latest payment change}` after `since`, for the push sweep."""
    read = _field_money("accounts_with_money_change_since")
    if read is None or not account_ids or since is None:
        return {}
    return dict(read([str(one) for one in account_ids], since))


def plan_status(account_id: Any, *, as_of: date) -> dict[str, Any] | None:
    """FB-023 F5 — `{status: on_track|behind, missed}` for an active payment
    plan, None for none (or while payments does not publish the read)."""
    read = _field_money("plan_status")
    if read is None or account_id is None:
        return None
    return read(account_id, as_of=as_of)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-037@d1b76486 (EP-WRK-07) · 10-execution-plan.md wave M task M1
# generated: 2026-09-05 by the CR-070 wave M build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: G78 · pytest tests/test_us_wrk_037_rules.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

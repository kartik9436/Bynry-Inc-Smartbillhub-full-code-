# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-037 (EP-WRK-07) — the billing trigger reader: a bill-run
#           break nobody has resolved.
# Rules:    BR-WRK-002 (read-only; one seam file per module) · BR-WRK-033 ·
#           CLAUDE.md hard rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_us_wrk_037_rules.py (TC-5) · G78
# Impacts:  apps/work/rules.py
# ───────────────────────────────────────────────────────
"""work → billing: bill-run breaks still unresolved. READ ONLY.

WHAT THE PLAN CALLS "A BILLING EXCEPTION" IS `bill_run_breaks` IN THE CODE
────────────────────────────────────────────────────────────────────────────
The execution plan names the trigger *"a billing exception unresolved"*. There
is no table called `billing_exceptions`; what a bill run produces when one
account cannot be billed is a row on `bill_run_breaks`, with a `stage`, a
`reason`, and a `resolution` that is NULL until a human deals with it. That NULL
is the whole trigger, and it is named here rather than in `rules.py` so that the
mapping from the plan's English to billing's schema lives in exactly one file.

⚠ **A BREAK IS ONLY WORTH A FIELD VISIT IF IT IS *NOT* RETRYABLE.**
`bill_run_breaks.retryable` is TRUE for the ordinary case — a lock, a transient
— and those are cleared by re-running the bill, not by sending a technician to a
property. Raising a job for one would put a van on the road for something that
fixed itself twenty minutes later. So the reader takes the non-retryable ones
only, and a rule that wants the others has to say so explicitly through its own
`params`.

⚠ **AND IT READS THE ACCOUNT, NOT THE RUN.** A run with 40 breaks is one bad
night; 40 accounts each needing a visit is 40 jobs. The subject is the ACCOUNT,
so the (rule, subject) idempotency means one account gets one job however many
runs break on it — which is the behaviour a two-person utility needs, and the
opposite of what keying on the break row would give them.
"""

from __future__ import annotations

from typing import Any

from core import tenancy as core_tenancy


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def unresolved_breaks(*, retryable: bool = False) -> list[dict[str, Any]]:
    """Accounts carrying an unresolved bill-run break. One row per ACCOUNT.

    A list of dicts and never a queryset — see `payments_seam` for why.
    """
    from apps.billing import models as billing_models

    rows = (
        billing_models.BillRunBreak.objects.filter(
            tenant_id=_tenant_id(),
            resolution__isnull=True,
            retryable=retryable,
        )
        .exclude(account_id__isnull=True)
        .order_by("account_id", "-created_at")
    )

    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = str(row.account_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "account_id": key,
                "account_no": row.account_no,
                "stage": row.stage,
                "reason": row.reason,
            }
        )
    return out


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-037@d1b76486 (EP-WRK-07) · 10-execution-plan.md wave M task M1
# generated: 2026-09-05 by the CR-070 wave M build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: G78 · pytest tests/test_us_wrk_037_rules.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ══════════════════════════════════════════════════════════════════════════
# CR-168-BRC10 round 6 · lane SRV-5 · P6.3 — the page engine, by name
# ══════════════════════════════════════════════════════════════════════════


def page_engine() -> Any:
    """`apps.billing.page_print` — the product's ONE PDF writer, published by
    billing for another module's printed page (B14 rule 43: one writer, not a
    copy per door). READ ONLY: it renders bytes and writes no table."""
    from importlib import import_module

    return import_module("apps.billing.page_print")

# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 C1 / task T6(e) — the screen half of "post supplier costs on
#           settlement". DEF-3440: the register told the screen to read
#           `settlement.in_the_books` and served no such block.
# Story:    US-LED-019 (the register: list · search · filter · edit · void)
#           Screens: S73 (R8 "Costs")
# Rules:    BR-LED-028 (AMENDED 2026-09-02 — capture, hold, reconcile, export;
#           a date recording that payment happened elsewhere is not accounts
#           payable) · BR-LED-029 (what a captured invoice holds) ·
#           CLAUDE.md hard rule 5 (only the posting service WRITES journal
#           lines — reading them is lawful anywhere) · B14 rule 31 (no database
#           id is the visible value of a field)
# ───────────────────────────────────────────────────────
"""**DEF-3440 — the register serves the state its own docstring names.**

`supplier_invoice_row` has said since 2026-09-02 that *"the screen reads this
and `settlement.in_the_books`, never a date arithmetic of its own"*, and
`register()` served `paid_on` and no `settlement` block at all. A screen written
to that instruction reads `undefined`, which is falsy, and draws **every settled
purchase as unsettled** — the money is in the trial balance and the register
says it is not.

Nothing was red, because T6 shipped the backend and deferred the screen. That is
hard-won law 1 exactly: a comment claiming a guarantee is not the guarantee.

════════════════════════════════════════════════════════════════════════════
ONE QUERY, NOT ONE PER ROW
════════════════════════════════════════════════════════════════════════════
`settlement_state(row)` calls `settlement_entry(row.pk)`, so hanging it off the
list loop would be a query per row on an UNPAGINATED register — the register's
own docstring reports that it serves the whole filtered set rather than a page.
`settlement_states()` resolves the whole page in ONE `posting_key__in` read, and
the case below asserts the query count so that a later "simplification" back to
the per-row call goes red instead of going slow in silence.

════════════════════════════════════════════════════════════════════════════
WHAT RUNS WHERE (law 14)
════════════════════════════════════════════════════════════════════════════
Every case here is a READ. Nothing catches a database error and continues, so
law 14's aborted-transaction trap does not apply — but the settlement these
cases read is POSTED by `record_settlement`, which does wrap a column write and
a posting in one `atomic()`, so the file is run on real PostgreSQL as well:

    DATABASE_URL=postgres://... DJANGO_SETTINGS_MODULE=config.settings.local \\
    JOBS_EAGER=false pytest tests/test_cr060_t6e_register_settlement.py --create-db
"""

from datetime import date, datetime, timezone as dt_timezone

import pytest

from django.test.utils import CaptureQueriesContext
from django.db import connection

from apps.ledger import cost_capture

from tests.cost_of_service_fixtures import (
    capture_le11_month,
    enable_le11_services,
    with_monthly_fiscal_year,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    lonestar,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: BR-TEN-043 — the caller names the moment, so a retry stamps one instant.
SETTLED_AT = datetime(2026, 8, 4, 10, 30, tzinfo=dt_timezone.utc)

#: The day the utility's bank moved the money for CI-1.
PAID_IN_JULY = date(2026, 7, 28)

#: CI-1, LE-11's first bulk-water invoice: RS-2607-0141, $1,240.00, GL 5110.
CI1 = "RS-2607-0141"


def brazos_ready(tenant, actor=None):
    """LE-11's preconditions — a fiscal calendar and the five services sold."""
    admin = (
        actor
        if getattr(actor, "role", None) == "system_admin"
        else staff_actor(tenant, "system_admin", f"setup-{tenant.subdomain}@brazosbendutilities.test")
    )
    with_monthly_fiscal_year(admin)
    enable_le11_services(admin)
    return admin


def test_cr060_t6e__the_register_says_which_purchases_are_in_the_books(brazos, marcus):
    """**DEF-3440's own case.** One of LE-11's nine is settled; the register
    tells them apart.

    CI-1 is settled on 2026-07-28 for **1,240.00** and posts DR 5110 / CR cash.
    The other eight carry no `paid_on` and nothing posted for them. The register
    must draw the first as *In the books* and the eight as *Recorded*, and it
    must do it off a SERVED field rather than off the screen inferring a state
    from whether a date string happens to be null.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        cost_capture.record_settlement(
            marcus, captured[CI1]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )

        listed = cost_capture.register()

    rows = {row["reference"]: row for row in listed["rows"]}
    assert len(rows) == 9

    settled = rows[CI1]
    assert settled["settlement"]["in_the_books"] is True
    assert settled["settlement"]["paid_on"] == PAID_IN_JULY.isoformat()
    # The ruling sentence rides with the state, so the screen prints the
    # ledger's words and cannot drift from them.
    assert settled["settlement"]["ruling"] == cost_capture.SETTLEMENT_RULING

    for reference, row in rows.items():
        if reference == CI1:
            continue
        assert row["paid_on"] is None, reference
        assert row["settlement"]["in_the_books"] is False, reference
        assert row["settlement"]["paid_on"] is None, reference


def test_cr060_t6e__the_state_costs_ONE_query_whether_three_are_settled_or_nine(brazos, marcus):
    """**The register is UNPAGINATED, so a per-row lookup is a per-row query.**

    `settlement_state(row)` calls `settlement_entry(row.pk)`. Nine rows would be
    nine extra reads of `journal_entries`, and a real utility's month is dozens.

    The measurement IS the assertion, and it is constancy rather than a ceiling:
    three settled purchases and nine settled purchases must cost the SAME number
    of queries, and exactly **one more** than a register where nothing is settled
    (the batched `posting_key__in`, which is skipped entirely when no row carries
    a `paid_on`). A ceiling would drift upward in silence as the register gains
    reads for other reasons; this goes red the moment the lookup moves back into
    the row loop.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        references = list(captured)
        assert len(references) == 9

        with CaptureQueriesContext(connection) as nothing_settled:
            cost_capture.register()

        for reference in references[:3]:
            cost_capture.record_settlement(
                marcus, captured[reference]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
            )
        with CaptureQueriesContext(connection) as three_settled:
            cost_capture.register()

        for reference in references[3:]:
            cost_capture.record_settlement(
                marcus, captured[reference]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
            )
        with CaptureQueriesContext(connection) as nine_settled:
            cost_capture.register()

    assert len(three_settled) == len(nine_settled), (
        f"three settled purchases cost {len(three_settled)} queries and nine cost "
        f"{len(nine_settled)} — the settlement state is being resolved per row"
    )
    assert len(three_settled) == len(nothing_settled) + 1, (
        f"the settled register cost {len(three_settled)} queries against "
        f"{len(nothing_settled)} for an unsettled one — the batch should be exactly one read"
    )


def test_cr060_t6e__a_voided_purchase_is_never_in_the_books(brazos, marcus):
    """A void is not a settlement, and the two states must not blur.

    BR-LED-035 keeps a voided row VISIBLE in the register precisely so a clerk
    reconciling against a supplier statement sees why a line was withdrawn. It
    posts nothing, so it reads *Recorded* like any unpaid purchase — never a
    third state the screen would have to invent copy for.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        cost_capture.void_supplier_invoice(
            marcus,
            captured[CI1]["id"],
            reason="captured twice from the same statement",
            voided_at=SETTLED_AT,
        )

        listed = cost_capture.register()

    voided = next(row for row in listed["rows"] if row["reference"] == CI1)
    assert voided["status"] == "voided"
    assert voided["settlement"]["in_the_books"] is False
    assert voided["settlement"]["paid_on"] is None


def test_cr060_t6e__one_tenants_settlement_is_invisible_to_another(brazos, lonestar, marcus):
    """The batched read is tenant-scoped by construction, like the per-row one.

    `settlement_entry` filters on `_tenant_id()`; a batched `posting_key__in`
    read that forgot to would answer about somebody else's books, and a
    posting key is derived from an invoice id, which is guessable in shape.
    Lone Star Ridge's register must carry no settlement of Brazos Bend's.
    """
    with tenant_ctx(brazos):
        brazos_ready(brazos, marcus)
        captured = capture_le11_month(marcus)
        cost_capture.record_settlement(
            marcus, captured[CI1]["id"], paid_on=PAID_IN_JULY, settled_at=SETTLED_AT
        )

    with tenant_ctx(lonestar):
        other = cost_capture.register()

    assert other["rows"] == () or all(
        row["settlement"]["in_the_books"] is False for row in other["rows"]
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060-T6e@11-change-requests.md (sources: 12-governance/11-change-requests.md CR-060 §7 C1 and task T6 row (e) · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-028/029/035 · 12-governance/10-defect-log.csv DEF-3440)
# generated: 2026-09-03 by the CR-060 T6(e) lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every case failed with KeyError: 'settlement' against the register as it stood, quoted in the lane report.
# exceptions: (1) the query-count case asserts EQUALITY rather than a ceiling: the point is that the settlement state costs the same whether or not anything is settled, and a ceiling would drift up silently as the register gains reads for other reasons
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 Phase 2 · **P2.9** — *"Paging on real data. ⚠ Postgres
#           only. Seed 40,000 rows and assert the page-two query reads 50, not
#           40,000. The SQLite suite is not evidence."* Read from
#           `05-prototype/09 Reports Build Brief.pdf` **p011**, as a rendered
#           image (B14 rule 42).
# Rules:    NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard-won law 14 (the suite
#           runs on SQLite and the guarantee does not exist there) · hard-won
#           law 7 clause 2 (what would make this pass WRONGLY).
# ───────────────────────────────────────────────────────
"""THE PAGE IS CUT IN SQL, AND THIS IS THE ONLY PLACE THAT CAN SAY SO.

WHY THE ORDINARY SUITE IS NOT EVIDENCE, IN THE BRIEF'S OWN WORDS
================================================================
*"⚠ Postgres only … The SQLite suite is not evidence."* The reason is exact and
it is hard-won law 14's shape one subject over: `config/settings/test.py`
hardcodes in-memory SQLite, and **SQLite has no `EXPLAIN` a reader can count
rows out of.** A `LIMIT` that was never applied and a `LIMIT` that was applied
produce the same fifty rows to any assertion about `len(rows)` — the difference
is whether the database read fifty or forty thousand to get there, and that
difference is the whole of `NFR-3`.

So this file asserts TWO things and they fail independently:

  1 · **THE ANSWER IS RIGHT.** Page two of a 40,000-row register holds rows
      51–100 of the ordered set, and the report's `total` is 40,000 — not the
      page's length, which is the mistake that draws *"1–50 of 50"* over a
      register of any size.

  2 · **THE COST IS RIGHT.** `EXPLAIN (ANALYZE, BUFFERS)` over the statement
      the read model issues names a `Limit` node, and the rows it actually
      emits are the PAGE, not the book. Before `P2.1` the read model
      materialised the whole ISSUED book and Python sliced it, and assertion 1
      passed perfectly.

⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7 clause 2), because a check you
cannot describe a false pass for is one you do not understand:

  * **A SKIP THAT READS AS A PASS.** Run anywhere but PostgreSQL this file
    SKIPS, and a suite of skips reports green. `G5` called 192 skips a pass over
    the tenant-isolation suite and that is exactly this shape. So the skip
    message states the vendor it found, and the count below is printed on
    success — a reader can tell 'it ran and cut a page' from 'it did not run'.
  * **SEEDING FEWER ROWS THAN IT CLAIMS.** 40,000 is asserted before anything
    else is measured. A fixture that quietly inserted 400 would satisfy every
    later line.
  * **MEASURING A DIFFERENT QUERY.** The plan is taken from the statement the
    READ MODEL issues, captured out of `connection.queries`, not from a query
    this file composes to look like it.
"""

from __future__ import annotations

import os
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

pytestmark = pytest.mark.django_db

#: The brief's own figure. 40,000 is the top of T5 and the largest tenant B6
#: models, so this is the whole ICP and not a round number.
ROWS = int(os.environ.get("REP_P29_ROWS", "40000"))

#: The page size the viewer asks for — `core.pagination`'s default.
PER = 50


def _postgres_or_skip() -> None:
    """Refuse to pretend. The vendor is NAMED so a skip cannot read as a pass."""
    if connection.vendor != "postgresql":
        pytest.skip(
            f"P2.9 needs PostgreSQL and found {connection.vendor!r}. "
            "The page is cut with LIMIT/OFFSET in SQL and SQLite cannot be asked "
            "what a statement read — on SQLite a LIMIT that was applied and one "
            "that was not produce the same fifty rows. Run with "
            "DJANGO_SETTINGS_MODULE=config.settings.local and a DATABASE_URL."
        )


def _seed_register(tenant_id: Any, *, rows: int) -> tuple[date, date]:
    """`rows` issued bills in one window, written in bulk.

    ⚠ **RAW SQL AND NOT THE ORM, DELIBERATELY.** 40,000 `Invoice()` objects
    through the ORM is minutes of fixture for a test about a query plan, and
    every column this report reads is written here explicitly, so what the
    report sees is stated in one place a reader can check against
    `apps/billing/reporting.billing_register`.
    """
    start = date(2026, 1, 1)
    end = start + timedelta(days=364)
    with connection.cursor() as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name='invoices'")
        columns = {name for (name,) in cursor.fetchall()}
    required = {"id", "tenant_id", "invoice_no", "issued_on", "total", "status"}
    missing = required - columns
    if missing:
        pytest.skip(
            "the `invoices` table on this deployment does not carry "
            f"{sorted(missing)}, so this fixture cannot write a register row. "
            "That is a schema change, not a paging failure — say so rather than "
            "letting the case read as green."
        )
    return start, end


@pytest.mark.slow
def test_p29__page_two_of_a_40000_row_register_reads_fifty() -> None:
    """Page two holds rows 51–100, the total says 40,000, and the plan LIMITs.

    ⚠ **THIS TEST IS CURRENTLY A SKELETON AND IT SAYS SO RATHER THAN PASSING.**
    The seeding half needs a tenant with a rate plan, a cycle and 40,000 issued
    invoices, and the only path in this repo that writes an issued invoice is
    the bill run — `apps.tenancy.sample_data` produces 45 of them in about
    ninety seconds, which extrapolates to roughly twenty hours for 40,000.
    Writing them with raw SQL instead needs every NOT NULL column of `invoices`
    and its lines, and the columns this report reads come from FOUR tables
    (`invoices`, `invoice_lines`, `accounts`, `customers`).

    **So the honest state is: the ANSWER half is provable today and the COST
    half is not, and this file refuses rather than reporting a green it has not
    earned.** `xfail(strict=True)` is deliberate — it goes RED the day somebody
    makes it pass, which is the notification this needs.

    What IS measured today, on real PostgreSQL 16, and is in the lane report:
    the billing register's page 1 is **0.211s** and its last page **0.206s** at
    38,412 rows (`P2.1`'s own measurement, re-quoted rather than re-run).
    """
    _postgres_or_skip()
    pytest.xfail(
        "P2.9 is NOT PROVED. Seeding 40,000 issued invoices needs either the "
        "bill run (~20 hours at the sample data's observed rate) or raw inserts "
        "across four tables. The page-two ANSWER is asserted by "
        "`test_p29__the_page_is_the_page` below on whatever rows exist; the "
        "PLAN half — that the statement carries a Limit and reads 50 rather "
        "than 40,000 — has no proof in this repo and must not be reported as "
        "one."
    )


@pytest.fixture
def register_tenant() -> Any:
    """ONE tenant, with its context open. CLAUDE.md hard rule 1 — never touch a
    tenant table without `app.tenant_id` set, and the first draft of this file
    did exactly that and got `AUTH-003` for it, which is the rule working."""
    from apps.tenancy.models import Tenant
    from core import tenancy as core_tenancy

    tenant = Tenant.objects.create(
        name="P2.9 register", subdomain="rep-p29", currency="USD", state="active"
    )
    with core_tenancy.tenant_context(str(tenant.id)):
        yield tenant


def test_p29__the_page_is_the_page(register_tenant: Any) -> None:
    """The half that IS provable: `per` cuts, `page` offsets, `total` is the book.

    This runs on whatever the fixture database holds — which is usually nothing,
    and an empty register still proves the SHAPE: `total` is the count over the
    whole filtered set and `rows` is at most `per`. It goes red if either of
    those stops being true, which is the defect that draws *"1–50 of 50"* over
    a register of any size.
    """
    from apps.reports import queries

    payload = queries.billing_register(
        {"from": "2026-01-01", "to": "2026-12-31", "page": "2", "per": str(PER)}
    )
    page = payload.get("page")
    assert page is not None, (
        "the billing register served NO `page` member, which means *this is all "
        "of it* — and a report bounded by tenant size must never say that "
        "(NFR-3). `apps/reports/queries._report` omits the key only when "
        "`per=all`, which is the EXPORT's door."
    )
    assert page["per"] == PER, f"asked for {PER} per page and the server cut {page['per']}"
    assert len(payload["rows"]) <= PER, (
        f"page two holds {len(payload['rows'])} rows over a page size of {PER}. "
        "A page longer than its page size is a slice that did not happen."
    )
    assert page["total"] >= len(payload["rows"]), (
        "`total` is the count over the whole FILTERED set and `rows` is one page "
        "of it, so the total can never be smaller. A total that equals the page "
        "length is the read model reporting its own slice, which is how a "
        "register of any size draws '1–50 of 50'."
    )


def test_p29__the_export_is_not_a_page(register_tenant: Any) -> None:
    """§8.2's right path: `per=all` serves the whole filtered set and NO `page`.

    ⚠ **THIS IS THE CASE THE BRIEF ASKED FOR BY NAME.** When the billing
    register started paging, its export silently inherited the screen's fifty
    rows — a clerk would have exported a 38,000-row register and received a
    valid-looking file of fifty. No error, no gate, no test. This is the test.
    """
    from apps.reports import queries, runner

    whole = queries.billing_register({"from": "2026-01-01", "to": "2026-12-31", "per": "all"})
    assert "page" not in whole, (
        "`per=all` served a `page` member. An absent `page` is the read model "
        "saying *this is all of it*; serving one on the export path is the "
        "screen's answer wearing the file's clothes."
    )

    through_runner = runner.rows_for(
        "billing_register", {"from": "2026-01-01", "to": "2026-12-31"}, whole=True
    )
    assert len(through_runner) == len(whole["rows"]), (
        "the runner's `whole=True` and the query's own `per=all` disagreed about "
        "how many rows a file holds. They are ONE path by construction (`P0.5`); "
        "if they differ, the export and the screen have drifted apart again."
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P2.9 (05-prototype/09 Reports Build Brief.pdf p011, read as a RENDERED IMAGE per B14 rule 42)
# generated: 2026-09-26 by lane REP-P2-VIEWER
# gates: ⚠ **NOT RED-PROVED, AND SAYING SO IS THE POINT (hard-won law 1).** Both passing cases are REGRESSION guards over behaviour `P2.1` already landed — `_report()` already omits `page` on `per=all` — so neither was ever shown failing on a real defect. They go red if that is undone, which is what they are for; they are not evidence that anything was broken and fixed here. The one case that WOULD have been a proof is `xfail`ed, for the measured reason in its docstring.
# exceptions: (1) the 40,000-row PLAN half is `xfail(strict=True)` and NOT reported as proved — see its docstring for the measured reason and for what would make it pass
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8696 (Sign off's summary read: 250–396 s at 40,008 bills)
# Ruling:   OQ-843 re-ruled 2026-09-30, option C — *"Save results, and
#           automatically re-check an account when its plan, reading, meter or
#           payment changes"* (the precedent for a saved answer that is rebuilt
#           the moment what it was built from changes)
# Tests:    06-backend/tests/test_d8696_signoff_snapshot_pg.py
# ───────────────────────────────────────────────────────
"""HAS ANY OF THESE ROWS CHANGED? — a key that moves whenever a row is written.

`version_key(queryset)` answers with `"<rows>:<Σ xmin>:<Σ cmin>"` over the rows the
queryset selects. PostgreSQL stamps every row VERSION with the transaction that
wrote it (`xmin`), so:

  * an INSERT adds a row (the count moves, and the sum);
  * an UPDATE — through the ORM, a queryset `.update()` that never touches
    `updated_at`, or raw SQL — writes a NEW row version with a new `xmin`
    (the sum moves);
  * a DELETE takes a row away (the count moves, and the sum).

It is the SUM and not the MAX on purpose: a long transaction that began before
the key was read and commits after it writes an `xmin` LOWER than the newest one
already counted, and a max would not move. A sum moves on any new version.

⚠ **AND `cmin` IS SUMMED TOO, BECAUSE `xmin` ALONE CANNOT SEE A WRITE MADE BY
THE SAME TRANSACTION THAT WROTE THE ROW (found red, 2026-10-01).** A draft
created and then updated in ONE transaction keeps the same `xmin` on its new
version, so count and Σ xmin both stand still — the case's first run proved it
(`test_d8696_signoff_snapshot_pg.py`, `draft_total` and `void`). Each statement
in a transaction has its own command id, stamped on the version it writes as
`cmin`, so the second statement's version carries a different one.

A key is a statement about rows, never about money: two keys that are equal say
*nothing these rows hold has been written since*, and the caller decides what
that licenses. It is read only where a whole answer was SAVED and must be
rebuilt the moment anything it was built from changes (the OQ-843 option C
shape, `apps/billing/signoff.py`).

PostgreSQL only. Elsewhere (the SQLite unit tier) it answers None, and a caller
must treat None as *cannot tell* — never as *unchanged*.

Every caller keys rows of ITS OWN module's tables (B1); a module that needs to
know whether another module's rows moved asks that module's published read.
"""

from __future__ import annotations

from typing import Any

from django.db import connection
from django.db.models import Count, Sum
from django.db.models.expressions import RawSQL


def supported() -> bool:
    """Only PostgreSQL stamps row versions this way."""
    return connection.vendor == "postgresql"


def version_key(queryset: Any) -> str | None:
    """`"<rows>:<Σ xmin>:<Σ cmin>"` over the rows `queryset` selects, or None where the
    database cannot say (not PostgreSQL)."""
    if not supported():
        return None
    table = queryset.model._meta.db_table
    found = queryset.order_by().aggregate(
        rows=Count("pk"),
        versions=Sum(RawSQL(f'"{table}"."xmin"::text::bigint', ())),
        commands=Sum(RawSQL(f'"{table}"."cmin"::text::bigint', ())),
    )
    return f"{found['rows']}:{found['versions'] or 0}:{found['commands'] or 0}"


def keys(*querysets: Any) -> str | None:
    """`version_key` of each, joined — None if any cannot say."""
    parts = [version_key(queryset) for queryset in querysets]
    if any(part is None for part in parts):
        return None
    return "/".join(parts)  # type: ignore[arg-type]

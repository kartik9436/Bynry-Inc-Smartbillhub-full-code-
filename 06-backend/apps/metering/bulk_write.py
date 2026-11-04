# ── Trace ──────────────────────────────────────────────
# Component: the import runner's row writer — CR-036 (e), the MEASURED half.
# Change:   CR-036 · AMENDMENT 1 (e) (PO 2026-08-26 — *"It is taking almost
#           30 -40 seconds from upload to Transform and transform to
#           Validate."*, 9,881 premises then 9,881 units)
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — see the RLS note below) ·
#           BR-MET-090 (the run's record is what it DID)
# ───────────────────────────────────────────────────────
"""ONE `UPDATE … FROM (VALUES …)` PER BATCH, INSTEAD OF DJANGO'S `CASE WHEN`.

**WHY THIS FILE EXISTS, WITH THE NUMBER THAT PUT IT HERE.** `QuerySet.
bulk_update` writes a batch as `UPDATE … SET col = CASE WHEN id=… THEN …
END` — one `When` object per row per column, each resolved and copied in
Python before a single byte reaches Postgres. Measured on this container,
9,881 import rows x 6 columns:

    django bulk_update      12.68s
    UPDATE FROM (VALUES)     1.15s      (11.0x)

and a profile says why: 692,526 `resolve_expression` calls and 692,548
`copy.copy` calls against **5.3s of actual database time**. The work was never
in the database. Batch size does not help — Django's own cost is flat from 100
to 2,000 rows a batch (12.6s / 11.5s / 12.2s / 13.7s / 14.3s).

⚠ **IT WRITES EXACTLY WHAT `bulk_update` WROTE.** Same rows, same columns, same
values, keyed on the same primary key; an A/B on one staged file compared
`mapped`, `source_key` and `outcome` row by row and found them identical. This
is a statement-shape change and nothing else — no rule is relaxed, no column
is skipped, no row is left unwritten.

⚠ **RLS IS UNAFFECTED, AND THAT IS NOT AN ASSUMPTION.** The statement runs on
the SAME connection, inside the SAME transaction, with the same `app.tenant_id`
GUC the ORM would have used — a Postgres row-security policy is a property of
the TABLE, not of the client library, so `FORCE` applies to this UPDATE exactly
as it applies to Django's. The tenant and run are ALSO named in the predicate
rather than left to the policy alone: a writer that is correct only because RLS
caught it is a writer one `SET ROLE` away from being wrong.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from django.db import connection
from psycopg import sql
from psycopg.types.json import Jsonb

#: The columns this writer knows how to send, and the type each VALUES cell is
#: cast to. A cast is REQUIRED: a bare `%s` inside `VALUES` gives Postgres no
#: type to infer from, and an unknown-typed NULL column fails outright.
#: Anything not listed here is refused rather than guessed at — a column added
#: to `import_run_rows` must be added here deliberately.
_CASTS: dict[str, tuple[str, Any]] = {
    "raw": ("jsonb", lambda value: Jsonb(value) if value is not None else None),
    "mapped": ("jsonb", lambda value: Jsonb(value) if value is not None else None),
    "source_key": ("text", lambda value: value),
    "outcome": ("text", lambda value: value),
    "problem": ("text", lambda value: value),
    "fix_hint": ("text", lambda value: value),
    "created_record_id": ("uuid", lambda value: value),
    "updated_at": ("timestamptz", lambda value: value),
    "is_sample": ("boolean", lambda value: value),
}


class UnknownImportRowColumn(RuntimeError):
    """A column nobody has declared a cast for. Refuse, never guess."""


def update_import_rows(
    objs: Iterable[Any],
    fields: Sequence[str],
    *,
    tenant_id: Any,
    run_id: Any,
    batch_size: int = 1000,
) -> int:
    """Write `fields` of every row in `objs`. Returns the rows actually updated.

    `tenant_id` and `run_id` are required and are part of the predicate — see
    the RLS note in this module's docstring.
    """
    rows = list(objs)
    columns = list(fields)
    if not rows or not columns:
        return 0
    unknown = [name for name in columns if name not in _CASTS]
    if unknown:
        raise UnknownImportRowColumn(
            f"no VALUES cast declared for import_run_rows column(s) {unknown!r} — "
            "add one to bulk_write._CASTS rather than letting the write fall back"
        )

    set_clause = sql.SQL(", ").join(
        sql.SQL("{col} = v.{col}").format(col=sql.Identifier(name)) for name in columns
    )
    value_names = sql.SQL(", ").join(sql.Identifier(name) for name in ["id", *columns])
    row_template = sql.SQL("({})").format(
        sql.SQL(", ").join(
            [sql.SQL("%s::uuid")] + [sql.SQL("%s::" + _CASTS[name][0]) for name in columns]
        )
    )

    if connection.vendor != "postgresql":
        # ⚠ **THE DEFAULT TEST RUN IS SQLITE, AND IT DOES NOT COME DOWN THIS
        # PATH — SAY SO RATHER THAN LET A GREEN SUITE IMPLY OTHERWISE
        # (hard-won law 1).** `pyproject.toml` pins
        # `DJANGO_SETTINGS_MODULE=config.settings.test`, whose database is
        # sqlite in memory; `VALUES` casts, `jsonb` and `uuid` are Postgres
        # types. So on sqlite this falls back to the ORM writer that was here
        # before — same rows, same columns, just slowly — and the fast path is
        # proved by a `-m isolation` case that runs on real Postgres. A fast
        # path with no test on the database that runs it is DEF-101's shape.
        from apps.metering import models as metering_models

        metering_models.ImportRunRow.objects.filter(tenant_id=tenant_id, run_id=run_id).bulk_update(
            rows, columns, batch_size=batch_size
        )
        return len(rows)

    written = 0
    with connection.cursor() as cursor:
        driver = cursor.cursor  # the psycopg cursor under Django's wrapper
        for start in range(0, len(rows), batch_size):
            chunk = rows[start : start + batch_size]
            params: list[Any] = []
            for obj in chunk:
                params.append(obj.pk)
                for name in columns:
                    params.append(_CASTS[name][1](getattr(obj, name)))
            params.append(tenant_id)
            params.append(run_id)
            statement = sql.SQL(
                "UPDATE {table} AS t SET {set_clause} "
                "FROM (VALUES {values}) AS v({value_names}) "
                "WHERE t.id = v.id AND t.tenant_id = %s::uuid AND t.run_id = %s::uuid"
            ).format(
                table=sql.Identifier("import_run_rows"),
                set_clause=set_clause,
                values=sql.SQL(", ").join([row_template] * len(chunk)),
                value_names=value_names,
            )
            driver.execute(statement, params)
            written += driver.rowcount
    return written

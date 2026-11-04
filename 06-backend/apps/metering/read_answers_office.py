# ── Trace ──────────────────────────────────────────────
# Change:   CR-192-BRC10 — MQ-033 task 13 of 13: SEEING the read-format
#           answers in the office. Decision log 2026-10-24, *"SUMMARY
#           CONFIRMED"* (*"shown on the reading, filterable in Reads lists and
#           exported"*) and the task-13 row of the same day.
# Rules:    BR-MET-1218 (shown, filterable, exported) · BR-WRK-008 (a version
#           is stamped, so a column's words are the words the answer was asked
#           under) · B14 rule 31 (no id is a visible value) · NFR-3 (the
#           database pages and filters; nothing here lists a whole table) ·
#           NFR-5 (no cap) · CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_mq033_read_answers_office.py
# Impacts:  apps/metering/read_formats_api.py (two office routes) ·
#           apps/metering/exports.py (the Reads export's answer columns) ·
#           apps/tenancy/exports.py (`ExportResource.extra_columns`)
# ───────────────────────────────────────────────────────
"""The office's three reads of the answers a reader gave.

`read_formats.py` is the format ENGINE and the reads door; this file is what
a clerk on the Reads screens needs from what that engine stored, and nothing
else. It writes nothing.

1. **The question vocabulary the Reads list's Answer filter picks from** —
   `answer_questions_queryset`. Settings → Reads is System Admin / Executive
   (`read_formats_api`), and a Billing Clerk filters Reads, so the filter
   cannot borrow that list; it gets its own read-only, server-paged one over
   PUBLISHED formats' current versions (*"pick a published format's
   question"*). A retired format's answers are still stored and still
   exported; it is simply not offered as a new filter.

2. **The Reads export's answer columns** — `export_answer_columns` +
   `AnswerEnrichedSelection`. One column per (format, question key) that the
   EXPORTED rows carry, headed *"<format> · <question label>"*. Which
   questions those are is asked of the database as one semi-join over the
   selection (never by listing it), and the answers themselves are read ONE
   QUERY PER CHUNK of the stream, never one per row (DEF-324's shape) — so
   the file still streams exactly as it did.

3. **A photograph answer's bytes** — `photo_bytes`, so the reading's page can
   draw the thumbnail. Served through the API for `DEF-WRK-9594`'s reason (the
   page policy draws images only from itself).

JUDGMENTS (law 13 — ours, not put to the PO), each with its worked case:

* **The label on a column is the NEWEST version's label among the rows
  exported.** *Electric walk* v1 asked *"Seal intact?"* and v2 re-worded it
  *"Seal OK?"* under the same key: a file holding both is one column,
  *"Electric walk · Seal OK?"*, because the key — not the words — is the
  answer's identity (the custom field's BR-TEN-049 reason).
* **A cell is the answer AS STORED, as text** — yes/no as `true`/`false`
  (the export kernel's BOOLEAN words), a list as the kernel's multi-value
  separator, a photograph as its reference id (*"photo → the photo
  reference"*), a FLAGGED answer as the value that was sent (a flagged answer
  is kept, never dropped — `BR-MET-1216` — so the file must not hide it).
* **The filter key is format-blind**, as the server's `answer[<key>]` already
  is (task 10): two formats that share a key are filtered together. The
  vocabulary row carries the format's name so a clerk can see which format a
  question belongs to.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from django.db.models import F, Q, QuerySet

from apps.metering.read_format_models import (
    FORMAT_PUBLISHED,
    PHOTO,
    ReadAnswer,
    ReadFormatQuestion,
)
from apps.tenancy import exports as export_kernel
from apps.tenancy.exports import ExportColumn
from core import errors
from core import tenancy as core_tenancy

#: The cells a serialized export row carries its answers under. Underscored:
#: it is the export's own plumbing, never an API field.
ANSWER_CELLS = "_answer_cells"


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:  # hard rule 1 — never a cross-tenant read
        raise errors.deny_as_not_found("BR-TEN-003")
    return tenant_id


def _field_read_model() -> Any:
    from apps.metering.field_read_models import FieldRead

    return FieldRead


# ══════════════════════════════════════════════════════════════════════════
# 1 · The Answer filter's vocabulary
# ══════════════════════════════════════════════════════════════════════════
def answer_questions_queryset(*, q: Any = None, keys: list[str] | None = None) -> QuerySet:
    """Every question of every PUBLISHED format's current version, ordered by
    format then the question's own order. A QUERYSET — the API pages it
    (NFR-3). `q` matches the format's name OR the question's label; `keys`
    narrows to named keys (what a reloaded chip needs to say its label). A
    PHOTO question is not offered: a photograph has no value to match."""
    qs = ReadFormatQuestion.objects.filter(
        tenant_id=_tenant_id(),
        version__read_format__status=FORMAT_PUBLISHED,
        version__read_format__current_version_id=F("version_id"),
    ).exclude(data_type=PHOTO).select_related("version", "version__read_format")
    term = str(q or "").strip()[:120]
    if term:
        qs = qs.filter(Q(label__icontains=term) | Q(version__read_format__name__icontains=term))
    wanted = [k for k in (keys or []) if k]
    if wanted:
        qs = qs.filter(key__in=wanted[:50])
    return qs.order_by("version__read_format__name", "seq", "key", "id")


def answer_question_rows(page: list[ReadFormatQuestion]) -> list[dict[str, Any]]:
    """One page. `read_format_id` rides for `title` and React keys only —
    never a visible value (B14 rule 31)."""
    return [
        {
            "read_format_id": str(row.version.read_format_id),
            "format_name": row.version.read_format.name,
            "version_no": row.version.version_no,
            "key": row.key,
            "label": row.label,
            "data_type": row.data_type,
            "options": list(row.options or []),
        }
        for row in page
    ]


# ══════════════════════════════════════════════════════════════════════════
# 2 · The Reads export's answer columns
# ══════════════════════════════════════════════════════════════════════════
def answer_text(value: Any) -> str:
    """One stored answer as a cell. See the module docstring's second
    judgment: the kernel's own words for a yes/no and for a list."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return export_kernel.format_boolean(value)
    if isinstance(value, list):
        return export_kernel.MULTI_VALUE_SEPARATOR.join(str(v) for v in value)
    if isinstance(value, dict):
        return ""
    return str(value)


def _meter_read_ids(selection: Any) -> Any:
    """The selection's meter-read ids as a SUBQUERY (ordering dropped, so the
    database plans a semi-join rather than a sort)."""
    return selection.order_by().values("id")


def export_answer_columns(selection: Any) -> tuple[ExportColumn, ...]:
    """One column per (format, question key) the selection's rows answered
    under, in format-name then question order; headed *"<format> · <label>"*
    with the newest present version's label."""
    if not isinstance(selection, QuerySet):
        return ()
    FieldRead = _field_read_model()
    version_ids = (
        FieldRead.objects.filter(
            tenant_id=_tenant_id(),
            meter_read_id__in=_meter_read_ids(selection),
            read_format_version_id__isnull=False,
        )
        .order_by()
        .values("read_format_version_id")
    )
    questions = (
        ReadFormatQuestion.objects.filter(tenant_id=_tenant_id(), version_id__in=version_ids)
        .select_related("version", "version__read_format")
        .order_by("version__read_format__name", "version__read_format_id", "-version__version_no", "seq")
    )
    columns: list[ExportColumn] = []
    seen: set[tuple[str, str]] = set()
    for question in questions:
        ident = (str(question.version.read_format_id), question.key)
        if ident in seen:
            continue  # the newest version came first — its words win
        seen.add(ident)
        header = f"{question.version.read_format.name} · {question.label}"
        columns.append(ExportColumn(header, _cell_reader(ident), export_kernel.TEXT))
    return tuple(columns)


def _cell_reader(ident: tuple[str, str]) -> Any:
    def read(row: Any) -> str:
        return (row.get(ANSWER_CELLS) or {}).get(ident, "")

    return read


def answer_cells_for(meter_read_ids: list[Any]) -> dict[str, dict[tuple[str, str], str]]:
    """`{meter_read_id: {(format_id, key): cell}}` for ONE chunk, in one
    query. A read with no field reading or no answers is simply absent."""
    if not meter_read_ids:
        return {}
    rows = (
        ReadAnswer.objects.filter(
            tenant_id=_tenant_id(), field_read__meter_read_id__in=meter_read_ids
        )
        .order_by()
        .values(
            "field_read__meter_read_id",
            "field_read__read_format_version__read_format_id",
            "version__read_format_id",
            "question_key",
            "value",
        )
    )
    out: dict[str, dict[tuple[str, str], str]] = {}
    for row in rows:
        format_id = (
            row["version__read_format_id"]
            or row["field_read__read_format_version__read_format_id"]
        )
        if format_id is None:
            continue  # `version_unknown`: no format to put a column under
        cells = out.setdefault(str(row["field_read__meter_read_id"]), {})
        cells[(str(format_id), row["question_key"])] = answer_text(row["value"])
    return out


class AnswerEnrichedSelection:
    """The Reads export's selection, streamed in chunks with each chunk's
    answers read in ONE query and hung on its rows. Not a QuerySet, so the
    kernel iterates it as given (`selection_iter`); `queryset` is what
    `export_answer_columns` asks its question of."""

    def __init__(self, queryset: QuerySet, chunk: int = export_kernel.CHUNK) -> None:
        self.queryset = queryset
        self.chunk = chunk

    def __iter__(self) -> Iterator[Any]:
        buffer: list[Any] = []
        for row in self.queryset.iterator(chunk_size=self.chunk):
            buffer.append(row)
            if len(buffer) >= self.chunk:
                yield from self._flush(buffer)
                buffer = []
        if buffer:
            yield from self._flush(buffer)

    @staticmethod
    def _flush(rows: list[Any]) -> Iterator[Any]:
        cells = answer_cells_for([row.id for row in rows])
        for row in rows:
            setattr(row, ANSWER_CELLS, cells.get(str(row.id), {}))
            yield row


# ══════════════════════════════════════════════════════════════════════════
# 3 · A photograph answer's bytes
# ══════════════════════════════════════════════════════════════════════════
def photo_bytes(photo_id: Any) -> tuple[bytes, str]:
    """A LANDED route photograph's bytes and type. Resolved under this tenant
    first, so a neighbour's photograph is the same 404 as none (HR-1). The
    bytes were checked to be an image when they landed (`_probe`); a type the
    phone named that is not an image is served as JPEG under `nosniff`."""
    from apps.metering.field_read_models import FieldReadPhoto

    link = (
        FieldReadPhoto.objects.filter(
            tenant_id=_tenant_id(), photo_id=photo_id, state=FieldReadPhoto.STATE_LANDED
        )
        .only("data", "content_type")
        .first()
    )
    if link is None or link.data is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    content_type = str(link.content_type or "")
    if not content_type.startswith("image/"):
        content_type = "image/jpeg"
    return bytes(link.data), content_type


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-192-BRC10 (MQ-033 task 13 — answers in Reads lists and export; decision log 2026-10-24)
# generated: 2026-10-24 by lane MQ033-OFFICE
# checklist: A✔ B✔ C✔ D✔ E✔(ReadDetailPage · ReadsListPage) F✔ G✔ H=n/a(no 🔒 path)
# gates: see the lane report
# exceptions: the three judgments in the module docstring · Reads-list answer COLUMNS not built (the list rows carry no answers; reported)
# status: VERIFIED-UNRATIFIED

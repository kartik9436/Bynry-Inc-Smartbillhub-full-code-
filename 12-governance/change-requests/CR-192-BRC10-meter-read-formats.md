# CR-192-BRC10 · Utility-defined meter-read formats (MQ-033), kept in Settings → Reads

**Raised:** 2026-10-24 by the Product Owner, in chat, answering MQ-033 (put with two options, A and B).

**Requester's words, verbatim:**
1. *"B. Reading templates, like work templates - we understand your recommendation , but utility users want customizations they wantt to collect various data during meter reads hence we need to create meter read format templates so that the customization can be handled"*
2. *"3. Settings → Reads; The template is chosen automatically: route → cycle → service. A route can override its cycle, and a cycle its service. we can set it once or we can create another format for same service and replace it later"*
3. *"this is all user defined we dont have to provide anything readymade , this will be similar to custom fields"*
4. *"this is correct"* — to the summary: asked when (every reading · out of range · can't read · once per stop), follow-ups, raise a work order, all in the first release; answers inside the reading's own item, checked on the server, never causing a reading to be dropped (stored and flagged), shown on the reading, filterable and exported.

**Rulings:** decision log 2026-10-24, the three rows headed *"MQ-033"*; build judgments in *"MQ-033 read formats, the server: how it is built"* (same day).

**Classification:** CHANGE (a new capability). A utility cannot collect anything beyond the figure, the can't-read reason, a remark and photos today; nothing could configure extra questions (`sync/routes.ts`: *"the `photo_required` prompt … stays empty"*).

**Signed statement reversed:** none for formats. Our recommendation (A, one rule set per service) was declined. The reader-assignment half of MQ-033 (supersedes `CR-029` D6 / `OQ-343` for the cycle's Routes tab) is task 9's, not this CR's server work.

## The plan the PO was shown — five tasks in three rounds

| Task | What | Round |
|---|---|---|
| 9 | Route assignment on the cycle's Routes tab + one read window | 1 |
| **10** | **Read formats — the server (this lane)** | 1 |
| 11 | Settings → Reads screens | 2 |
| 12 | The phone: download, ask, answer, send | 2 |
| 13 | Answers in Reads lists (columns) and export | 3 |

## Task 10 — what is built (server only)

| Surface | Change |
|---|---|
| Tables (`metering/0080`, RLS FORCE on all five) | `read_formats`, `read_format_versions`, `read_format_questions`, `read_format_defaults`, `read_answers`; `routes.read_format_id`, `cycles.read_format_id`; `field_reads.read_format_version_id`, `field_reads.answers_need_review`. Nothing seeded. |
| Work (`work/0050`) | A route finding may be of kind `read_answer`, converted `by_read_format` — the raise path a matching answer uses. |
| Settings → Reads API | List (paged), create, get, edit, questions add/edit/reorder/delete on the draft, publish, new draft, retire, versions; service defaults; cycle and route pointers; what a route resolves to. |
| Phone | `GET work/mobile/routes` and `…/routes/{id}` carry `read_formats` per service (version id); the route page carries the versions with their questions; `GET work/mobile/read-formats/versions/{id}`. |
| Sync | Each reading item may carry `read_format_version_id` and `answers`; stored and stamped; checked against that version; flagged, never refused; a matching answer raises one job through Work. |
| Reads | The reading detail carries `read_format_answers`; the reads list takes `answer[<key>]=<value>`. |

## Task 12 — what is built (the phone, `field-app/`)

| Surface | Change |
|---|---|
| Handset DB (migration `0004_read_formats`) | `read_format_version` (published versions kept by id, shared on the handset); `route.read_formats` (resolved version per service); `route_read.read_format_version_id` + `answers` (what the reading was taken under, and the answers). |
| Download (`sync/routes.ts`) | Stores each route's `read_formats` and every version on `read_format_versions`; a named version not carried is fetched once from `GET work/mobile/read-formats/versions/{id}`. Offline after that. |
| Asking (`screens/reads/ReadQuestions.tsx`, `readFormat.ts`) | One sheet at save time from RW-09/10/15/16/17: asked when (every reading · out of range · can't read · once per stop), `show_if` follow-ups, kit inputs per type (text, number, date, yes/no, one of a list, several, photo over the camera port). Required answers block *Save reading* with one warning sentence (the `DEF-FLD-10583` pattern). The utility's words verbatim. |
| Sending (`sync/routeReads.ts`, `acts.saveReading`) | The reading item carries `read_format_version_id` and `answers` (`{question_key, value}` / `{question_key, photo_id}`); a photo answer is a photo of the reading, declared on the route-photo path. Batches of 50 unchanged. The receipt's `answers` block is kept; `needs_review` shows on RW-13 and blocks nothing. |
| No format | Saves straight through, exactly as before; the item carries neither key. |
| Shape lock | `field-app/tests/sync/support/serverReadFormat.json` ↔ `06-backend/tests/test_mq033_phone_shape.py` (key sets of the route format, the version and its questions; the phone's `reading_item` goes through the real door with no issue). |

Judgments: decision log 2026-10-24, *"MQ-033 read formats, the phone: how it is built"*. Status: BUILT (2026-10-24), lane MQ033-PHONE, in a worktree; not pushed.

## Not in task 10
Export columns and Reads-list answer columns (task 13 — built, below, except the list-table columns). The screens (11) and the phone (12). Re-running a raise when the office later accepts a field-added meter (judgment 6 in `apps/metering/read_formats.py`).

## Task 13 — what is built (the office sees the answers)

Judgments: decision log 2026-10-24, *"MQ-033 task (13) BUILT"*.

| Surface | Change |
|---|---|
| Reading detail (S29) | A *Read format* panel: format + version, *Needs review*, each question in the utility's words with its answer, the flag on a flagged answer, a photo thumbnail that opens the picture, the raised job by its order number. Nothing for a reading with no format. |
| Reads list (S25) | `+ Answer`: a published format's question (server search), then a value; `answer[<key>]=<value>`, AND-ed, removable chips, kept in the URL; server-paged as before. |
| Export (`POST /exports {resource: reads}`) | One column per (format, question key) the exported rows carry, headed *"<format> · <question label>"*; the list's answer filters narrow the file; still streamed (one answers query per chunk). Kernel: `ExportResource.extra_columns`, `None` for every other list. |
| Server | `GET reads/answer-questions` (paged; published formats; no photo questions) · `GET reads/photos/{id}/content`. |

**Not built:** answer columns inside the Reads list table — list rows carry no answers and the column chooser has no per-tenant dynamic columns (judgment 6). Reported, not forced.

**Rollback (task 13):** revert the commit. No migration, no data written; the export returns to the capability row's columns.

## Task 11 — what is built (the Settings screens)

Judgments: decision log 2026-10-24, *"MQ-033 read formats, the Settings screens: how they are built"*.

| Surface | Change |
|---|---|
| Settings → Configure → Reference data, READS | New card **Read formats** → `/settings/reference-data/read-formats` |
| Read formats list | Paged server table (Name · Service · Status · Version · Used by · Updated), service and status filters, search, Open / Retire row actions, *+ New format* dialog (name + service → opens the builder), *Defaults by service* panel (`PUT …/defaults/{service}`) |
| One format | Header (service, name, status, version line), Publish (optional *What changed*), New draft, Retire; Questions tab (add / edit / move up / move down / delete, refusals inline) and Versions tab (paged) |
| Question editor | Imports `DefinitionTypeFields` from the custom-field editor (extracted, B14 rule 43) plus Photo; Asked when; Show only if (earlier questions only); Raise a job (on answer + a published Work template, `PublishedTemplateField`) |
| Settings cycle page | *Read format* panel (`GET`/`PUT cycles/{id}/read-format`) |
| Settings route page | *Read format* panel — the route's pointer and the resolved format per service with its source |
| Settings → Routes list | Select column + selection row *Set read format* (`PUT routes/read-format`, many routes) |
| Server | `GET cycles/{id}/read-format` added (the only server change); schema regenerated |
| Catalogues | 110 keys under `settings.readFormats.*` and the card's two, in all eleven |

## Rollback
Revert the commit; `metering/0080` and `work/0050` reverse cleanly (no data migration; the new columns are nullable or default false). A format and its answers would be lost on reverse — say so before rolling back a tenant that has used it.

## Version
Not bumped by the lane (the coordinator releases).

## Status
BUILT (2026-10-24), lane MQ033-SERVER, in a worktree; not pushed — the coordinator merges.

# CR-194-BRC10 · Refused field work is kept on BOTH the phone and the server, for the office to review

**Raised:** 2026-10-26 by the Product Owner, in chat, answering the A/B question the MQ-027 lane (`DEF-FLD-10612`) put after declining to print *"The office will review this."* on the phone because it was false.

**Requester's words, verbatim:** *"store on both"* — and, approving the plan, *"start this"*.

**Ruling record:** decision log 2026-10-26, *"Refused field work is kept on BOTH the phone and the server (amends 2026-10-21 item 4, "back to the technician")"* — the section this CR was raised from. Worked example shown: D. Ortiz's three readings on WO-0028, captured offline after the job was reassigned to M. Chen — saved and listed for the office (A) versus only on Ortiz's phone and lost if the phone is lost (B). The PO chose both.

## 1 · Classification (step 1 of `13-change-process.md`)
A **change**: it amends a signed ruling of the PO's own (2026-10-21 item 4, *"back to the technician"*, which made a refused item store NOTHING on the server). Not a defect — the server did exactly what 2026-10-21 said.

## 2 · What signed statement moves, and what stands
**Superseded (in part):** `BR-WRK-063` as amended 2026-10-21 — *"Nothing is stored that could later post (no receipt, no `field_reads` row, no proposal)"* and `apps/work/sync.py`'s *"NOTHING STORED"*. The server now ALSO stores a **copy** of every refused field item.

**Stands, unchanged:** the item is answered `refused` with its reason, NOT acknowledged; the phone keeps it and shows it to fix and resend; **no receipt is written**, so the key is not spent and a fixed resend posts exactly once. The copy is never a receipt and can never make a resend a duplicate.

## 3 · Our judgments where the ruling ran out (law 13 — recorded, not re-asked)
1. **One copy per key** (`work_refused_items`, unique `(tenant, key)`). A resend refused again updates the same copy — `last_refused_at`, `refusal_count`, the newest reason and payload — and does not reopen a copy the office already marked reviewed.
2. **The copy is written in ITS OWN savepoint, after the item's own savepoint has rolled back** (hard-won law 14). A failure writing the copy is logged and the item is answered exactly as before, without `kept_for_office` — the batch is never poisoned and the phone never hears a promise that was not kept.
3. **`detail.kept_for_office: true`** rides on the refusal only when the copy was stored in that request. The phone stores the refusal as it is (`outbox.refusal`), so the flag needs no handset migration.
4. **When the same key later applies** — the technician's fixed resend, or the office's *Apply to the job* — the copy closes as `applied_later` (by the phone) or `applied` (by the office), in the SAME savepoint as the receipt, so the copy and the receipt can never disagree.
5. **The capture token is never stored** — it is a credential. The copy keeps the payload the phone sent, the kind, the job, the capture time and place, and the captor (resolved from the token, an expired one included).
6. **Photographs:** a `photo` item's bytes never reach a refused declaration (no upload link is made), so the copy keeps the declared photo id and says the photograph is still on the phone; an `attachment` item's bytes were already delivered by `POST /work-orders/{id}/attachments`, are never deleted, and the copy links them so the office sees the thumbnail. A reading's copy lists the photographs refused with it (same job, same reading).
7. **Mark reviewed** (with an optional note) closes a copy for the office without touching the job. **Apply to the job** re-runs the kind's normal apply path, AS THE OFFICE PERSON, with a receipt under the item's own key (so the phone's later resend is a duplicate and leaves its outbox): it is refused, with the reason, when the job is closed, cancelled or accepted, when the service refuses it now, or when the copy came through the ROUTE-READS door (a route reading is posted by the reads pipeline, never from here). The captor stays the technician who captured it.
8. **Both doors keep copies.** The job door (`apps/work/sync.py`, #90 and the batch across jobs) and the route-reads door (`apps/metering/field_reads.py`). Metering never writes Work's table: the reads door hands the refused item to `apps.work.refused_items` through `metering.seams` (the `work_route_findings` precedent).
9. **Who acts:** any office role lists and reads; the roles that write work orders (`WorkOrdersReadAnyWriteAdminOrClerk`) mark reviewed and apply. Every act writes `audit_log`.

## 4 · What is built
**Server (work)** — `apps/work/refused_models.py` (`work_refused_items`), `work/0056` (table) + `work/0057` (RLS ENABLE + FORCE), `apps/work/refused_items.py` (keep · close · list · detail · mark reviewed · apply), `apps/work/refused_items_api.py` (spliced into `api.urlpatterns` by one line). `apps/work/sync.py` and `apps/metering/field_reads.py` call it.

    GET  /work/refused-items?status=&reason=&technician=&kind=&q=&page=&per=
    GET  /work/refused-items/{id}
    POST /work/refused-items/{id}/review   {note?}
    POST /work/refused-items/{id}/apply

**Web** — Work → From the field → **Refused work** (a fifth pane, `/work/field/refused`): Technician · Job · What · Reason · When · Status, filters and search by job number; a detail drawer with the work as sent (a reading's value and unit, the note, photographs), *Mark reviewed* and *Apply to the job*.

**Phone** — FF-50's refused row (one item or a group) adds *"The office will review this."* when every item behind it carries `kept_for_office`.

## 5 · Tests
`06-backend/tests/test_cr194_refused_field_work.py` · `06-backend/tests/test_cr194_refused_field_work_pg.py` (the copy's own savepoint; RLS) · `07-frontend/src/features/work/field/FieldRefusedPane.dom.test.tsx` · `field-app/tests/screens/me/refusalGroups.test.ts` (amended).

## 6 · Version and rollback
Version recorded on the index row at close. **Rollback:** `migrate work 0055` drops the table and every copy the office held; the doors then answer exactly as on 2026-10-21 (the phone's line disappears with the flag).

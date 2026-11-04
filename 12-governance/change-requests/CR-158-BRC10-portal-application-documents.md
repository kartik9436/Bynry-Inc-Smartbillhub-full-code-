# CR-158-BRC10 — A customer attaches documents to a portal new-service application; the clerk opens them on the request

**Raised:** 2026-10-01, by the Product Owner, when told during a web walk of the portal
new-service request that the portal could not accept a file (`DF-4`). The ruling is the
decision-log row dated 2026-10-01 headed *"CUSTOMERS MAY NOW UPLOAD DOCUMENTS FROM THE
PORTAL — `DF-4` … IS SUPERSEDED FOR THE NEW-SERVICE REQUEST"*; it is quoted, not
paraphrased, below.
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, claimed for this branch by `CR-156-BRC10`
in `12-governance/14-id-reservations.md`). Number from `10-scripts/allocate.py cr` against
the remote (`158`), re-verified at push time.
**Classification:** a **CHANGE** (`13-change-process.md` §1) — the product did what was
agreed (`DF-4`: *"v1 uploads are STAFF-mediated; consumer upload portal = v2"*), and the
agreement moved.

## 0 · What arrived, in the requester's words

> *"you need to allow customer to upload documents and save those document to server for
> that Utility - and then clark should able to view those document in new request"*

> *"we need to now accept the document from portal - make provisio, and use upload
> document component we build"*

## 1 · What signed statement is reversed

`DF-4` (PO 2026-08-08), carried into `04-docs/01-requirements/06-non-functional-requirements.md`
as *"v1 uploads are STAFF-mediated; consumer upload portal = v2"*. **Reversed for the
portal's new-service request ONLY.** Every other portal flow (the report's photo, the
hardship certificate) keeps `DF-4` until it is ruled. No ❄️ B4/B5 figure moves; no money
path is touched.

## 2 · Status

BUILT — see §3. Version and commit in §4. **Its one "not done" item — an unsent
application's files kept for ever — is BUILT too (`2.443.0`, 2026-10-02), §5.**

## 3 · What was built (judgments recorded in the decision log, 2026-10-01, *"PORTAL DOCUMENT UPLOAD — THE LIMITS …"*)

**Customer (portal, `CWP-047` step 3 *About you*).** The proof-of-identity box the
wireframe draws, held under `DF-4` until now, is the product's own `FileDropField`
(`portal/guest/ApplicationDocuments.tsx`). Limits stated before the attempt: **PDF, JPG or
PNG · up to 10 MB each · 5 files at most**. Each file posts the moment it is chosen
(`POST /portal/public/applications/{token}/documents`, multipart) and is listed with its
type and size and a Remove (`DELETE …/documents/{id}`). Step 4 restates the files
read-only. Attaching stays optional; Send never waits for a file.

**Safety.** The type is read from the bytes (`%PDF-`, PNG signature, `FF D8 FF`) and the
browser's claim is ignored; a wrong type answers **415** and an oversized file **413**,
each naming the file (*"notes.png: use PDF, JPG, PNG."*, *"scan.pdf is over 10 MB."*). The
database CHECKs refuse the same two. Files are held on the draft in
`portal_application_documents` (RLS `FORCE`, `portal/0010` + `0011`) and never enter the
seven-year store until Send, so an abandoned draft's file is never visible to staff.

**Submit.** In the submit's own transaction, each held file is handed to
`customers.service_request_documents.attach_from_portal`, stored in the document store,
filed as a `service_request_documents` row (`other`, `not_checked`, no staff uploader,
the applicant's upload time) and the held copy deleted.

**Clerk.** The request detail's Documents tab and the capture screen's table show name,
TYPE, size and the date; **Open** and **Download** go through the new
`GET /service-requests/{id}/documents/{docId}/content?as=view|download`, which answers
`Content-Disposition` (inline only for a viewed PDF/PNG/JPEG), `nosniff`,
`Content-Security-Policy: default-src 'none' …` and `Cache-Control: private, no-store`.
Another utility gets 404. `audit_log` rows: `portal.application_document.uploaded` /
`.removed`, `customers.service_request_document.attached_from_portal` / `.viewed` /
`.downloaded`.

**Gates and records.** `write_points.MODULE_WRITE_TABLES["applications.py"]` now names
`PortalApplicationDocument`, with its reason (G81/G84 green). The `portal.apply.proofHeld`
hold is released in `portal/routing/holds.ts` and its key retired from all eleven
catalogues. `DF-4` stamped *superseded for the new-service request* in the NFR text,
`EP-CWP-04`, `BR-CWP-001` and `03-field-map.md`. Review-ledger row for the two migrations.

**Tests.** Backend `tests/test_cr158_portal_application_documents.py` (11) and
`…_pg.py` (4) — 15 passed on PostgreSQL 16; red proved by breaking the byte sniff, the
`nosniff` header and the hand-over (4 failed, 7 passed). DOM:
`CheckAndSend.dom.test.tsx` (the step-3 hold test inverted; three new cases). e2e:
`07-frontend/e2e/CR-158-portal-application-documents.spec.ts` on Six Rivers Utility
(water, sewer, trash, fire, battery, solar — PO 2026-10-01), seeded by
`10-scripts/cr158_seed_portal_upload.py`.

## 4 · Version and proof

**`2.438.0`** (`allocate.py version --bump change`). Build commit `5ac17a0e9`; this
version/record commit follows it. e2e run 2026-10-02 against the booted stack
(PostgreSQL 16, Django, built SPA) on Six Rivers Utility: the applicant at
`88 Riverbend Way` (all six services available, water and solar among them) attached
`tenancy-agreement.pdf` and `photo-id.png`, sent `SR-26-0001`, and the clerk opened both
— bytes identical, `inline`, `nosniff`, `default-src 'none'`. Screens in
`08-qa/screens/cr158-portal-upload-2026-10-01/`. **Not proved:** a PDF actually DRAWN by a
desktop browser's viewer under the policy (headless Chromium has no PDF viewer) — a person
opening one on screen is still owed. ⚠ **PROVED 2026-10-02, no code change:** headed
Chromium 141 under `xvfb-run` (`07-frontend/e2e/CR-158-pdf-display-headed.spec.ts`) — the
clerk clicked a customer's three-page PDF on the Documents tab and Chromium's own viewer drew
it, *"SAMPLE ID — page 1"* on screen, its toolbar reading **3** pages; a PNG and a JPEG drew
as 480×300 images; `as=download` saved `sample-id.pdf` instead of drawing it. The served
policy did not block the viewer. Screens and what was and was not proved:
`08-qa/screens/pdf-display-2026-10-02/README.md`.

**Rollback.** Revert the commit; `portal/0011` and `0010` reverse cleanly (the table holds
only unsent drafts' files). Files already filed on requests stay, as any filed document
does.

## 5 · The "not done" item — an abandoned application's files — BUILT `2.443.0` (2026-10-02)

**What was not done.** §3 held a draft's files outside the seven-year store, but nothing
ever deleted an UNSENT application: a stranger who uploaded a driving licence and never
pressed Send left it in `portal_application_documents` for ever. The 2026-10-01
review-ledger row said so (*"an abandoned application's files are never cleared on a
timer (no draft is)"*) and put it to the PO as a separate ruling.

**The ruling** (decision log, 2026-10-02, option A). PO verbatim: *"A · Delete it 30 days
after her last visit. Her draft and the photo are deleted on 31 October, and the deletion
is logged. If she returns on 20 October, the 30 days start again."*

**What was built.**
* **The last visit** — a new column `portal_application_drafts.last_visited_at`
  (`portal/0012`, nullable, no backfill). It is stamped when the applicant OPENS the link
  (the guest `GET` now goes through `applications.open_draft`), SAVES, or adds or removes a
  file. A draft from before the column counts from its last save (`updated_at`).
* **The nightly job** — `apps/portal/draft_cleanup.py`, beat entry `portal.draft_cleanup`
  at **03:40 UTC**, installed from `PortalConfig.ready()` (`G132`). Per utility, in its own
  tenant context, it deletes every UNSENT draft whose last visit is on or before
  *today − 30* in the utility's own timezone — so 1 October goes on 31 October, and a return
  on 20 October moves it to 19 November — with the files on it. The bytes live on those
  rows, so deleting the rows deletes the bytes. One `audit_log` row per draft:
  `portal.application_draft.deleted_unsent`, the draft's own id, the last visit, the file
  count and the reason `unsent 30 days` — never a file name or its contents, the
  applicant's name, contact, date of birth or tax ID, or the link's token.
* **Never touched:** a SENT application, its draft row, its documents in the store; a draft
  visited within the 30 days; another utility's drafts. A second run deletes nothing.
* **Allow-list.** `write_points.py` names `draft_cleanup.py` in `STAFF_WRITE_MODULES` and
  `MODULE_WRITE_TABLES` for exactly this delete, with the ruling in its comment. `G81` was
  shown red on the file before the row (two `.delete()` lines named) and green after.

**Tests** — `06-backend/tests/test_cr158_draft_cleanup_pg.py`, **9 passed on PostgreSQL
16.13** with a frozen clock: 31 days → draft, 2 files and their bytes gone and one audit
row with no personal content; 29 days → survives (and goes the next day); the ruling's own
figure, 1 October → kept on 30 October, gone on 31 October; opened (not edited) on
20 October → kept on 31 October and 18 November, gone 19 November; a pre-column draft counts
from its last save; a sent application's two filed documents and the store untouched four
months later; another utility's draft untouched by this utility's run (and removed by its
own); a second run deletes nothing and writes no audit row; the beat entry is on the celery
app. **Red first:** with *unsent* dropped from the filter and the open-is-a-visit stamp
removed, 2 failed; with the 30 days counted as 720 hours and the tenant predicate dropped,
5 failed; with the audit write removed, 2 failed. Neighbours green: the CR-158 SQLite and
PostgreSQL suites and `US-CWP-013`'s, 32 passed on PostgreSQL.

**Found on the way:** `DEF-CWP-9115` — `G84` cannot see a write made through a queryset
chain (`.objects.filter(…).delete()`), so inside an already-listed portal file it compares
nothing; `G81` still catches the same write in an unlisted file.

**Rollback.** Revert the commits; `portal/0012` drops one nullable column and loses
nothing a person typed. Drafts already deleted stay deleted — that is the ruling, and the
audit rows say which and when.

# CR-172-BRC10 — The utility logo moves into the S3 document store, and is drawn everywhere

**Raised:** 2026-10-05 by the Product Owner, in chat.
**Status:** **DONE — 2.525.0 (lane LOGO, 2026-10-05).** Plan approved the same day (decision log 2026-10-05, *"THE LOGO-TO-S3 PLAN IS APPROVED AS WRITTEN"*).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`). `allocate.py cr` answered 172 against the remote and `--verify 172` reported it free on every branch at allocation.
**Defects it closes:** `DEF-TEN-9704` (broken image in the header and the Brand preview — the cause) · `DEF-TEN-9705` (four surfaces never draw the logo) · `DEF-INT-9707` (found on the walk: the Bill layout previews were refused framing on two-host deployments).
**Classification (`13-change-process.md` §1):** a CHANGE to storage design, plus two DEFECTS found by reproducing it. No money rule, no signed figure, no RLS policy. The signed logo rules are unchanged and finally built in full (see §1).

## 0 · What arrived, in the requester's words (verbatim)

1. *"The uploaded logo is stored in S3, the same way the product's other files are stored. The database holds only the reference (the link/key to the S3 object), not the file bytes. The logo shows correctly everywhere it is drawn: the app header, bill layout, customer portal settings, and generated documents. Replacing the logo shows the new one. Another utility's logo is never shown. Existing utilities that already uploaded a logo keep it, with nothing lost. If storage is unavailable, the upload refuses with a clear message … The existing rules stay as they are: SVG/PNG only, 2 MB limit, sanitised SVG."*
2. *"use common compotent to save logo - dont create seperate code"*
3. The go: *"this si approved when your load and tasks queue allow please start this work"*

## 1 · What is reversed, and what is NOT (step 2)

**No PO ruling is reversed.** Two LANE choices are, and both are quoted so the next reader can see they were choices:

| Where | The lane's words | Now |
|---|---|---|
| `apps/tenancy/models.py`, beside `logo_bytes` (US-TEN-005 gap lane, 2026-08-09) | *"No document-storage kernel exists in core/ (no object store, no signed-URL contract), so the sanitized bytes live on the row and `logo_file_id` carries their content reference `sha256:<hex>`. Swapping to an object store later changes these two columns and nothing else"* | The kernel exists (`CR-049`, `CR-160-BRC10`). The bytes go into it; `logo_file_id` holds the stored document's id. |
| `apps/tenancy/document_models.py`, on `NFR-33` (CR-049 task 1 lane, 2026-08-30) | *"`tenant logo` IS ON `NFR-33`'s LIST AND IS DELIBERATELY NOT A KIND HERE. It already has storage — `tenants.logo_bytes` … and moving it is a migration over live rows that buys this CR nothing."* | It is a kind: `tenant_logo`, stored in the `tenancy` folder. |

The signed rules this BUILDS rather than changes:
- **`BR-TEN-019` (CONFIRMED, PO R2-B4)** — *"Logo: SVG or PNG ≤ 2 MB; SVG sanitized server-side + rasterized for PDF/print"*. The first half was built; **the rasterising half was never built** (`BrandMark.tsx` E3). It is built here.
- **`BR-TEN-017` (CONFIRMED, PO R2-A1)** — *"Company identity/brand/remittance values are stamped onto documents at issue time; edits affect future documents only — issued documents are never re-rendered."* A bill now stamps WHICH logo it was issued with.
- **`NFR-33`** — tenant logos are a STORED ARTIFACT. They now live where the others do.

No ❄️ FROZEN figure is touched.

## 2 · The S3 path

`t/<utility web name>/tenancy/<yyyy>/<mm>/<file id>.<svg|png>` — `CR-160-BRC10`'s layout, composed by `document_storage.key_for()` from the stored row, never by logo code. `tenancy` was already on `STORAGE_MODULES` (*"logos and branding, when they move into this store"*); what is added is the KIND `tenant_logo` mapped to it, and the SOURCE `tenant_logo`.

- One upload = one `source_id` minted for it.
- A **PNG** upload is ONE stored document.
- An **SVG** upload is TWO stored documents on the same `source_id`: the cleaned SVG (`image/svg+xml`) and its PNG rendering (`image/png`) — *"two representations of one document"*, exactly what `uq_stored_documents_filed` permits. Screens draw the SVG; printed documents draw the PNG.
- `tenants.logo_file_id` = the id of the stored document that was uploaded. `tenants.logo_content_type` stays (it says which of the two to serve). **`tenants.logo_bytes` is emptied** by the migration and is **dropped in a LATER release**, once every environment has run the migration and nothing reads it.

No separate logo storage code exists: the upload calls `document_store.store()`, the read calls `document_store.reference()`/`fetch()`/`for_source()` — the same calls a bill, a receipt and a work-order photograph use. `apps/tenancy/logo.py`'s sanitiser stays the only way in (SVG or PNG, 2 MB, SVG cleaned) and gains only the rasterising function.

## 3 · How existing logos move

Data migration `tenancy/0061` (🔒 migration ordering, HUMAN-REVIEW-PENDING):
1. For each utility whose row still holds bytes, it stores them through `document_store.store()` under that utility's own tenant context (and the PNG rendering when the logo is an SVG).
2. It reads the object back through `document_store.fetch()` and compares **sha256 byte for byte** with what was on the row. Only a match is accepted.
3. Only then does it repoint `logo_file_id` to the stored document and empty `logo_bytes`.
4. **Re-runnable:** a row already repointed is skipped; a row whose copy was stored by an earlier, interrupted run is found by its deterministic `source_id` and reused, not stored twice.
5. **Storage down:** the row is left exactly as it was — bytes, reference and all — and the logo keeps drawing from the row. The migration does not fail; it prints how many it left, and `manage.py move_logos_to_store` finishes the job once storage is back.

## 4 · Impact (step 3)

| Surface | Effect |
|---|---|
| Upload (Settings › Company › Brand) | Writes to the store. Storage down → refused with *Logo storage is unavailable. Nothing was saved.* (11 catalogues), nothing saved. |
| App header, Brand preview | The `<img>` address now carries the API's origin (`DEF-TEN-9704`) and the logo's reference, so a replacement shows at once. |
| Bill layout | The chooser shows the logo; its preview PDF draws it. |
| Customer portal settings | Shows the logo itself instead of the words *On file*. |
| Customer portal | The header draws the logo beside the utility's name. |
| Generated bills | The bill stamps the logo it was issued with and draws it, as an image, on the PDF and the HTML. A bill issued before this change keeps the page it had (`BR-TEN-017`). |
| Logo read route | Readable without signing in — the logo is printed on every bill and shown on the public portal — and still scoped to the utility in the address. The upload stays System Admin only. |
| Dependencies | **One added: `resvg-py`** — a self-contained SVG renderer (no system library), needed for `BR-TEN-019`'s rasterising clause. Nothing in the backend could turn an SVG into a picture before. |
| Data | Every stored logo moves; nothing is deleted. |
| Lanes running | MVI-P0, FIN-T and FIN-W touch no logo file. |

## 5 · Judgments that were ours

Recorded in the decision log (2026-10-05, *"LOGO TO S3 — JUDGMENTS OF OURS"*).

## 6 · Built (step 6)

Commit `9b6b8ae50` (code) and the closing records commit.

| Surface | Before (2.521.0, two-host build) | After (2.525.0) |
|---|---|---|
| App header | broken image — the `<img>` asked the app's host and got `index.html` (200 `text/html`) | the logo, from the API origin, `?v=<reference>` |
| Settings › Company › Brand | broken image (same cause) | the logo |
| Bill layout | previews *"refused to connect"* (`DEF-INT-9707`); the preview PDF held no image | previews load; the preview PDF draws the current logo |
| Customer portal settings | the words *On file* | the logo itself |
| Customer portal | the name only | the logo beside the name |
| Generated bill | no image | the logo the bill was STAMPED with (a reprint after a replace still draws the old one) |

Photographs: `08-qa/logo-2026-10-05/before-*` and `after-*`; the walk is `10-scripts/logo_s3_walkthrough.mjs`.

**Migration, proved on PostgreSQL 16 (`sbh_wlogo`, a real S3 API):** storage down → *"0 moved … 1 left on the row"*, row unchanged (247 bytes, sha256 `88a30611…`); storage back → *"1 moved"*, the S3 object 247 bytes, sha256 `88a30611…`; again → *"1 already there"*; `migrate tenancy 0060` refused with its counted sentence; `--back` restored the bytes; moving again reused the same stored document.

**Left:** dropping `tenants.logo_bytes` (a later release, once every environment has run `0061` and `move_logos_to_store` reports 0 left on the row).

## 7 · Version · rollback

**2.525.0** (`allocate.py version --bump change`, verified at push).

**Rollback, stated before shipping:** revert the build. The migration's reverse copies each stored logo's bytes BACK onto its row from the store (`logo_bytes` is only emptied, never dropped, in this release) and restores the `sha256:` reference, so the previous build reads every logo again. Stored objects stay in the bucket (write-once); they cost kilobytes.

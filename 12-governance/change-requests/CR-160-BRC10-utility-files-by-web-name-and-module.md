# CR-160-BRC10 — Utility files are stored at `t/<utility web name>/<module>/<yyyy>/<mm>/<file id>`, and no file is object-locked for now

**Raised:** 2026-10-02, by the Product Owner, in chat. The ruling is the decision-log row
dated 2026-10-02 headed *"`CR-160-BRC10` — UTILITY FILES ARE STORED AT `t/<utility web
name>/<module>/<yyyy>/<mm>/<file id>` …"* (commit `4e44763e6`); it is quoted below, not
paraphrased, and nothing in it is put back to the PO (hard-won law 13).
**Branch:** `claude/upbeat-dirac-olttw0` (`BRC10`, claimed for this branch by `CR-156-BRC10`
in `12-governance/14-id-reservations.md`). Number `160` is the one the ruling itself
carries. `10-scripts/allocate.py cr --verify 160` answers *TAKEN* — and the only thing
holding it is that same decision-log row and its commit subject, which is this CR's own
ruling and not a sibling's CR (checked with `git grep CR-160` and `git log --grep`).
**Classification:** a **CHANGE** (`13-change-process.md` §1) — the product stored files
exactly as `CR-049` decision 3 agreed, and the agreement moved.

## 0 · What arrived, in the requester's words

> *"Change the S3 key layout for utility-specific files to t/<tenant>/<function>/<yyyy>/<mm>/<object> in ONE bucket per environment"*

> *"Instead of Fucntion can you do it module"*

> *"STart from t - dont add Sbh-prod - ew have bucket seperated out enviornment wise"*

> *"we dont want this to be enabled right now - dont lock it"* (on per-object locks for legal files and a delete-after-30-days tag on exports)

> *"Yes, web name"* · *"yes, as listed - you can cosider others module also"*

**Worked example shown to the PO:** a September 2026 bill PDF for Austin Water is the
object key `t/austin-water/billing/2026/09/<file id>.pdf` in that environment's bucket.

## 1 · What signed statements are reversed

| Statement | Where | What happens to it |
|---|---|---|
| `CR-049` step 5d(e) **decision 3** — key layout `t/<tenant_id>/<yyyy>/<mm>/<document_id>` | `06-backend/apps/tenancy/document_storage.py` decision 3 · `document_models.StoredDocument` docstring · `CR-049` · decision log 2026-08-30 | **AMENDED** for every file written from this change on. Old-shape keys are still read; nothing is moved; no `storage_key` is rewritten. |
| `document_storage.py` **decision 6** — *"IMMUTABLE RETENTION FOR NFR-35's SEVEN YEARS"*, COMPLIANCE Object Lock by default | `document_storage.py` · `config/settings/base.py` · `.env.example` · `09-infra/02-aws-runbook.md` | **SUSPENDED**: no object is locked and none carries an expiry tag. The lock stays a setting (`DOCUMENT_STORAGE_OBJECT_LOCK_MODE`), default now `NONE`; switching it on applies to files written after that moment only. |
| `NFR-35` — *"write-once (immutable object lock), retention 7yr"* | `04-docs/01-requirements/06-non-functional-requirements.md` | The **object-lock half is suspended by this ruling**; the database row stays write-once (`tenancy_stored_document_write_once` is untouched) and the product still deletes nothing. |

No ❄️ B4/B5 figure moves; no money path is touched.

## 2 · Status

**DONE — `2.454.0`, 2026-10-02.** Code in `234f11a9f`; the close (version, CHANGELOG,
decision-log follow-up, review-ledger row, the remaining docstrings) in the commit that
carries this line.

## 3 · Impact

* **Code:** `apps/tenancy/document_storage.py` (key shape, the module list, key regex,
  lock default), `apps/tenancy/document_models.py` (the fixed kind → module map),
  `apps/tenancy/document_store.py` (the only caller of `key_for`: reads the utility's web
  name server-side), `core/storage_guard.py` (refuses a bucket with a DEFAULT retention
  rule), `config/settings/base.py`, `06-backend/.env.example`.
* **Data:** none moved. Every existing `stored_documents.storage_key` is read exactly as
  stored. No migration.
* **Docs:** every live document quoting the old `t/<tenant_id>/<yyyy>/<mm>/` shape — counted
  and amended in §5.
* **Runbook:** `09-infra/02-aws-runbook.md` — bucket created WITHOUT a default retention
  rule; Object Lock no longer required at creation.
* **Hard-won law 4:** a host that already has a `.env` keeps whatever
  `DOCUMENT_STORAGE_OBJECT_LOCK_MODE` it typed. A host that typed `COMPLIANCE` keeps
  locking until somebody edits that host's `.env`.
* **Lanes building now:** none touch the document store (PO answers batch: integrations
  BR-INT-008, G48, G53; tenant-isolation proof).

## 4 · Out of scope (noted, not built)

Moving existing objects to the new shape · a second cloud adapter · the archive shipper.

## 5 · Close

**Version:** `2.454.0` (`allocate.py version --bump change`, verified free at push).

**What was built.** `document_storage.key_for(tenant_folder, module, document_id, moment,
extension)` composes `t/<web name>/<module>/<yyyy>/<mm>/<file id>[.ext]`; its only caller,
`document_store.store`, reads `tenants.subdomain` for the session's own tenant and the
module from `document_models.DOCUMENT_KIND_MODULE[kind]` — 48 kinds, all mapped, onto the
PO's twelve modules (no module added). The key check accepts the new shape AND the
`CR-049` shape; a folder that is not a BR-TEN-011 web name, a module off the list and an
unmapped kind are refused. `DOCUMENT_STORAGE_OBJECT_LOCK_MODE` defaults to `NONE`: no put
carries `ObjectLockMode`, a retain-until date or `Tagging`. `core/storage_guard.py` asks
the bucket once at boot and refuses a DEFAULT retention rule (`smartbillhub.E002`); a
bucket it cannot ask is a warning. The map's reasoning and the web-name finding are the
decision-log follow-up row of 2026-10-02.

**Can a web name change?** No product path changes it after sign-up; nothing in the
database forbids an operator doing so. If one does, old files stay under the old folder,
still readable by their stored key, and a whole-utility prefix operation would miss them.

**Proof.** `tests/test_cr160_storage_key_layout.py`, 68 cases: 68/68 on PostgreSQL 16
(the cross-tenant case through the non-superuser probe role), 67 + 1 PG-only skip on
SQLite. **Red first** against `2ed37e46c` with only the new module map copied in:
`50 failed, 17 passed` — key shape per module (13), a stored file's key (12), the folder
refusals (13), the module refusal, the bad-web-name tenant, the no-lock puts (7), the
`NONE` default, the default-retention refusal and the cannot-ask warning all failed; the
17 that passed are the map's own checks, the old-key and malformed-key cases, the
no-caller-argument check, the lock switch and the clean-bucket boot — regression guards,
not evidence. Existing suites: `test_cr049_t1_document_store.py` 38/38 on PG,
`test_def_2379_storage_boot_check.py` 5/5, `test_cr094_i_account_documents.py` 18/18 and
`test_service_request_documents.py` 25/25 on PG. **Two reds I did not cause, dated:**
`test_cr049_t3_reprint_route.py::…regulator_register_lists_a_date_range…` and
`test_cr049_t4_bill_freeze.py::…tc2b…` fail on PG identically at `2ed37e46c` (before this
change) and after it.

**Web walk (Chromium, `vite build --mode wolocal`, filesystem backend, PostgreSQL 16):**

| # | What | Result | Key written |
|---|---|---|---|
| a | Clerk issues a one-time $15.00 fee bill on AC-2026-00012 and opens its document | BL-2610-000104 issued; page says *"the bill as it was issued … has not been rebuilt"*; the PDF answers 200, `%PDF`, provenance `original` | `t/brazosbend/billing/2026/10/01a0fcd1-eaad-747e-9294-51e66d33c5fe.pdf` (+ `.html` beside it) |
| b | Clerk files `cr160-signed-lease.pdf` on AC-2026-00012 and fetches it | Filed and listed; the link the API mints points at the new key and the bytes match. **No open control on the row — `DEF-CUS-9147` filed** (pre-existing) | `t/brazosbend/customers/2026/10/01a0fcd3-1d22-7b6c-b81b-92d4937ce71d.pdf` |
| c | Portal applicant at Six Rivers attaches a PDF and sends; the clerk opens it on SR-26-0009 | Opens inline, 200, identical bytes | `t/sixrivers/customers/2026/10/01a0fcd7-1779-7e2b-ab00-ac24736a361f.pdf` |
| d | Clerk downloads the premises list as CSV | `brazosbend_premises_full-list_….csv`, 80 lines. **Exports are not written to the document store at all** (job artifacts), so no key and no tag | — |
| e | A file stored under the OLD shape opens | Clerk opens `cr160-august-deed-old-key.pdf` on SR-26-0009: 200, the August bytes | `t/01a0fcd5-0868-7695-a69b-c74b90202da7/2026/08/01a0fcda-6c43-7cd3-8b68-e37fbb22e70b` |
| f | Six Rivers' clerk asks for Brazos Bend's bill and lease; Brazos Bend's clerk asks for Six Rivers' file, by id and by document route | Every request answers 404 *not found*; the bill page reads *"This bill has no document yet"* | — |

Screenshots: `cr160_a2_bill_document.png`, `cr160_b1_account_document_filed.png`,
`cr160_c1…c4`, `cr160_d1_export_downloaded.png`, `cr160_e1_old_key_listed.png`,
`cr160_e2_old_key_opened.png`, `cr160_f1_other_utility_refused.png` (lane scratchpad).

**Docs that quoted the old key shape — counted by grep, not from a list:** 12 places in 8
files. **Amended 9:** `document_storage.py` (decision 3, tenant-separation section),
`document_models.py` (module docstring, `StoredDocument`), `test_cr049_t1` tc17,
`frozenDocument.dom.test.tsx`'s comment, `CR-049`'s decision table (row 3 stamped
SUPERSEDED), the AWS runbook, the deployment architecture. **Left 3, on purpose:** the
verbatim red-proof transcript in `test_cr049_t1` tc4 (`t/1111…/2026/08/2222…`) and the
two 2026-08-30 decision-log rows — history, superseded by the 2026-10-02 rows rather than
rewritten. **Lock claims amended:** decision 6, NFR-35, `CR-049` decision 6, BR-LED-799,
the deployment architecture (3), the runbook (4), `.env.example`, `base.py`, the boot-check
hint, and the docstrings of `document_models` (2), `portal/models.py`,
`customers/api.py`, `account_documents.py`, `service_request_documents.py`,
`account_document_models.py`, `ledger/cost_capture.py`, `core/document_shrink.py`.
About ten further mentions of the seven-year lock inside those same docstrings and in
older conformance records were left as written; each file now carries the dated note.

**Rollback.** Revert the change commit and redeploy: new files go back to
`t/<tenant id>/<yyyy>/<mm>/<file id>` and the lock default to `COMPLIANCE`. ⚠ **Keep
`_KEY_RE` accepting the new shape** (revert it last, or not at all): files written while
`2.454.0` ran carry the new key, and the old check would refuse to open them. No migration,
no data rewrite — nothing in the database changes either way. A host whose `.env` types
`DOCUMENT_STORAGE_OBJECT_LOCK_MODE` keeps what it typed (hard-won law 4).

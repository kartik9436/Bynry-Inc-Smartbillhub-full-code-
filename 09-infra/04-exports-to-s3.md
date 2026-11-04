# Export files move from a shared disk to S3

> **Status:** design APPROVED by the PO on 2026-10-02 with three changes, and BUILT in 2.455.0 (§9). The decision-log row is
> *"EXPORT FILES MOVE FROM THE SHARED DISK TO S3 — THE DESIGN IS APPROVED"* (`47ffb95ef`).
> This file holds the analysis behind it (steps 1–9), the risks and the build order (steps
> 10–11). Measured at `d3cdd299d` (2.453.1); approval read at `47ffb95ef`.
> Fixes `DEF-MET-4954`. Findings filed from this analysis: `DEF-BIL-9148` (print-set ZIP written into the
> shared folder) and `DEF-GOV-9149` (docs saying no S3 file service exists). The cross-utility sweep
> `DEF-TEN-9146` was fixed by another lane in `a1ce173c6` (2.454.1); the S3 sweep keeps its rule — a
> tenant is required and there is no all-tenants path.

## 1 · What passes between web and the workers through a directory

**One thing: the generated download file.** It is written to `JOB_ARTIFACTS_DIR`
(`config/settings/base.py`, default `<BASE_DIR>/var/artifacts`). Three job kinds write it:

| Job kind | Queue | What it writes |
|---|---|---|
| `list_export` | default (`celery`) | 32 registered lists: premises, units, routes, cycles, reads, assets, 5 rating lists, 7 finance exports (trial balance/GL, remittance, revenue…), bill-run releases, deposits, 12 reports. Counted at runtime: `exports.registered_resources()` |
| `audit_export` | default | the audit-log CSV |
| `billing.bills.print_set` | `billing` | the print-set ZIP (`bills/*.pdf`, `manifest.csv`, `held-back.csv`, `README.txt`) |

The job record stored the **writing container's absolute path**
(`jobs.payload.artifact_path`). Web read it back through `GET /api/exports/{job_id}/file`,
the report-delivery link `GET /api/reports/delivery/{token}`, and the run-history screen's
"does the file exist" check.

### Inventory by class

How each grep hit was classified is in §8.

| Class | Count | What |
|---|---|---|
| **A** — shared between containers, must move | 7 places, one mechanism | the 3 writers · the path on the job record · the 2 download routes · the existence check and retention sweep. Plus infra: 3 compose mounts, the Dockerfile `mkdir`, `.env.example`, `base.py`, the EFS plan |
| **B** — scratch inside one task | 1 | `/tmp/print-set-*` (two small CSVs; `TemporaryDirectory` cleans up on failure) |
| **C** — per-container runtime | 3 | `/tmp/celerybeat-schedule`, the gunicorn control socket `/app/.gunicorn`, process-local temp |
| **D** — dev/test only | 5 | filesystem document backend (refused by production settings), test-settings temp and lock files, `core/walk_switches.py` (production forbids it), `export_openapi`, local `DOCUMENT_STORAGE_DIR` |
| No disk at all (checked) | — | **9 upload doors** (logo → a database column; the rest → the document store or a database column) · **imports** (meter reads, payments, premises ETL: file decoded in the request, rows staged in database tables) · runbook result files (streamed from the database) · ledger GL batch files (document store) · integrations and portal files (in memory) · **zero Celery task arguments are paths** |

### Corrections to what we believed

- **The volume was on only three containers** (`backend`, `celery`, `celery-billing`), not on
  `celery-beat`, `celery-integrations`, `celery-work` or `celery-runbooks`. That was harmless
  only because no export kind is routed to those queues.
- **There are no heartbeat files.** Job and batch heartbeats are database rows.
- **The print-set ZIP is written straight into the shared folder**, not into `/tmp`. Only the
  two CSVs go to scratch. A crash mid-build leaves a partial ZIP behind (`DEF-BIL-9148`).
- **Retention was not one rule.** The list export sweeps one utility's files at its own
  setting. The audit export and the print set swept every utility's files at 3 days
  (`DEF-TEN-9146`).

## 2 · Reproduction of `DEF-MET-4954` (before)

The setup was PostgreSQL 16 with gunicorn web and a separate celery worker, both on
`JOBS_EAGER=false`, each given its own artifacts folder. Signed in as the Brazos Bend clerk:
- `POST /api/exports {"resource":"premises"}` returned 202, and the job succeeded on the worker.
- `GET /api/exports/<id>/file` returned **404** `errors.not-found`.
- The 748-byte CSV existed only in the worker's folder.

**Control:** pointing web at the worker's folder made the same flow answer 200 `text/csv`.

## 3 · Print set, measured

- **Real bills, rendered by the print set's own renderer:** one page, 14.6–16.6 KB a PDF.
  ZIP compression gives a 0.167 ratio, so about **2.7 KB a bill in the archive**.
- **2,000 renders:** a 5.4 MB ZIP in 59 s (0.029 s a bill on a loaded host, row-level
  security off). Python heap peak 5.7 MB, process RSS 127 → 137 MB.
- **The 40,000-account database** (read-only SQL): 80,234 kept bill PDFs, median 7.6 KB,
  mean 13.1 KB, max 20.2 KB.
- **Projected at 40,000 bills:** about **107 MB** of ZIP when bills are re-rendered. The
  ceiling is about **525 MB** if the kept originals do not compress at all (not measured;
  their bytes are not on the measuring host).
- Memory stays bounded because the build holds one bill at a time. **Scratch disk needed is
  about the size of the ZIP.**
- The per-set ceiling `BILLING_MAX_BILLS_PER_PRINT_SET` is **25,000** (≈ 67 MB), so a whole
  40,000-bill set is refused at the door today.

## 4 · The design (approved, with the PO's three changes)

- **Where:** every export file goes to **`t/<web name>/export/<yyyy>/<mm>/<file id>.<ext>`**.
  `export` joins `CR-160-BRC10`'s fixed module list as its one non-code-module folder. This
  covers list, report and finance exports, the audit-log export and the bill print set. The
  bucket is the environment's own; the key never names it.
- **How:** a **sibling export store** on the same bucket, client and key rules as the
  document store. The document store cannot be used directly:
  - its table refuses every UPDATE and DELETE (migration `0026`);
  - its backend interface has no delete, by design;
  - it moves whole files in memory, and a print set needs a streamed multipart upload.
- **What the record holds:** a tenant-scoped `job_artifacts` table with FORCE row-level
  security. It stores the job, the exact storage key, the file name (the IS-11 name), content
  type, size, hash and status (`pending` → `stored` → `deleted`). The row is written
  **before** the upload, so an object that never finished uploading can still be found
  without listing the bucket. `jobs.payload.artifact_path` is no longer written.
- **Download:** `GET /api/exports/{job_id}/file` checks the row and the utility's retention
  setting at that moment, then **redirects to a signed link that lasts 4 hours** (the
  2026-08-30 ruling, `document_storage.url_ttl_seconds()`). The link carries the file name.
  It redirects rather than streams because a web worker is killed at 60 s and a print set is
  100 MB or more. **The report-delivery link streams the file**, so a machine that does not
  follow redirects keeps working. **Run history reads the row's status** and never asks the
  bucket.
- **Deleting old exports:** once a day, for each utility, celery-beat finds that utility's
  `stored` rows older than its `file_retention_days` (3 by default), deletes each object and
  marks the row `deleted`. **No other data can be deleted, three ways:**
  1. the sweep acts only on `job_artifacts` rows;
  2. it refuses any key that does not start with `t/<that utility's web name>/export/`;
  3. the app's IAM permission to delete is limited to `t/*/export/*` (policy text in
     `02-aws-runbook.md`).

  A test proves that a bill key and a notice key are refused. *"Delete on the next export"*
  is gone.
- **Print set:** the ZIP is built in a temporary folder, uploaded in parts, and the folder is
  deleted whether the job succeeds or fails.
- **Every environment** — dev and staging included — uses its own S3 bucket through the same
  S3 code. There is **no filesystem stand-in for exports**. Automated tests run against an S3
  emulator (`moto`) through the same client, so no test needs AWS credentials.
- **Removed:** the Docker `artifacts:` volume, the EFS plan, `JOB_ARTIFACTS_DIR` and the
  Dockerfile `mkdir`.

**Worked example:** Austin Water's September 2026 Premises export is stored at
`t/austin-water/export/2026/09/<file id>.csv`. The Download button hands over a link valid
for 4 hours. The daily sweep deletes the file 3 days later (or after Austin Water's own
setting), and it cannot touch anything outside `t/austin-water/export/`.

## 5 · Risks (step 10)

| # | Risk | What we do about it |
|---|---|---|
| R1 | **The app deletes something that is not an export.** No file is locked (`CR-160-BRC10`), so a delete permission is the only barrier | Three layers (§4). The guard runs inside the adapter's `delete`, so no caller can skip it. A red-first test feeds it a `billing/` key and a `notifications/` key |
| R2 | **A host with no bucket configured loses exports at deploy.** Compose runs production settings, and the shared volume used to carry exports on hosts with no bucket | It is a deploy precondition, written in the runbook and CHANGELOG. Exports refuse with a sentence naming `DOCUMENT_STORAGE_BUCKET`, never silently (law 3). ⚠ Editing `.env.example` reaches no existing host (law 4) |
| R3 | **Exports made before the deploy** have only a disk path | They answer the same 404 as an expired file. They are transient (3 days), so the honest behaviour is "expired"; nothing is migrated |
| R4 | **Rollback.** Exports made after the deploy live only in S3 | After a rollback those links 404 until the files would have expired anyway. No data is lost: an export is regenerable |
| R5 | **Print-set upload time and memory** at 107–525 MB | Multipart upload with bounded concurrency (part size × concurrency ≈ 32 MB). The upload sits inside the billing worker's existing time limit; at 25,000 bills it is ≈ 67 MB |
| R6 | **Web name changes after an export is made** | Each row keeps its exact key. If the web name changed, the sweep's prefix guard refuses the old key and logs it. That is the safe direction: a few small files leak rather than the guard loosening |
| R7 | **The signed link is a bearer token for 4 hours** | Already ruled and accepted for documents (2026-08-30). It reaches one file, and the setting can shorten it without a deploy |
| R8 | **`moto` is a new dev dependency** | It goes into `pyproject.toml`'s `dev` extra, which CI installs. No runtime dependency is added |
| R9 | **The token download streams through a web worker** | Report CSVs are small. A file too large for 60 s would show as a stalled download, and it is named here so it is not rediscovered |

## 6 · Build order (step 11) — each step shippable with a red-first test

1. **Key, module and adapter.** Add `export` to `STORAGE_MODULES` with the ruling; map `application/zip` to `zip`. Add an S3 export adapter with `put_file` (multipart from a path), `delete` (prefix-guarded), `read_url` (4 h, with file name and type) and `open_stream`. Tests run on `moto`.
2. **The record.** `job_artifacts` model, migration and FORCE row-level security, with `HUMAN-REVIEW-PENDING` and a review-ledger row. Isolation test on PostgreSQL as a non-superuser role.
3. **The store service.** Begin (pending row) → upload → stored, plus resolve for download. The job record no longer carries a path.
4. **The writers** (list export, audit export, print set). Write to scratch, then the store. Built on `DEF-TEN-9146`'s fix (`a1ce173c6`), which landed first on these same files.
5. **The readers.** Download redirect, token stream, run-history status.
6. **The sweep.** Daily beat entry, per utility, by row, prefix-guarded.
7. **Remove the disk.** `JOB_ARTIFACTS_DIR`, the compose volume, the Dockerfile `mkdir`, the EFS plan in both infra docs, `.env.example`.
8. **Re-take the `DEF-MET-4954` reproduction** with web and worker on separate disks; it must succeed. Then version, CHANGELOG, close the defect.

## 7 · What changes, file by file

- **Backend:**
  - `tenancy/`: `document_models.py` (module list), `document_storage.py` (zip extension; the client shared with the adapter), a NEW export store, the model and migration, `exports.py`, `services.py`, `selectors.py`, `api.py`, the sweep, and the beat install in `apps.py`;
  - `audit/exports.py`, `billing/print_set.py` and `billing/print_api.py` docstrings, `reports/delivery_api.py`, `reports/run_history.py`;
  - settings `base.py` and `test.py`, `.env.example`, `pyproject.toml`.
- **Infra:** `docker-compose.yml` (three mounts, the top-level `volumes:` and two comment blocks) and `Dockerfile` (the artifacts `mkdir`).
- **Docs:** `02-aws-runbook.md` (P5 IAM, the S3 row, the EFS row, cost, step 5, §8 variables, §10.6, §10.7) and `01-deployment-architecture.md` (§ variable table, §13 item 9, the lifecycle line).
- **Tests:** 13 test files read the disk path today and move with it.

## 8 · Pattern search behind the inventory (law 7)

Counted over `06-backend/**/*.py`. The **non-test** column excludes `tests/`, `migrations/` and `test_*`.

| Pattern | Non-test hits | Classified |
|---|---|---|
| `JOB_ARTIFACTS_DIR` | 7 | A, plus 1 D (test settings) |
| `artifacts_dir` | 6 | A |
| `resolve_artifact` | 9 | A |
| `job_artifact` | 6 | A |
| `tempfile` | 4 | 2 B (print set) · 2 D (test settings) |
| `/tmp` | 3 | D (walk switches docstring) |
| `NamedTemporaryFile` · `shutil` · `MEDIA_ROOT` · `FileField` · `default_storage` | 0 | — |
| `open(…, "w"…)` | 3 | 1 A (`write_csv`) · 2 B |
| `write_bytes` / `write_text` | 1 / 2 | D (filesystem document backend; `export_openapi`) |
| `Path(settings.` | 2 | A |
| `FileResponse` | 7 | A (the two download routes) |
| `StreamingHttpResponse` | 12 | no disk (streams from the database) |
| `request.FILES` | 9 | no disk (in memory → document store or a database column) |
| `zipfile` | 7 | 1 A (print set) · rest in memory |
| `csv.writer` | 17 | 1 A · 2 B · 14 in memory |
| Celery task arguments that are paths | 0 | job id + kind, or subdomain |

## 9 · Built (2.455.0) — and the reproduction re-taken

Each step was built small, each with a test that went red first where a guard was added:

| Step | What | Red first |
|---|---|---|
| 1 | `export` on the fixed module list; `apps/tenancy/export_storage.py` (multipart upload, signed read link, stream, prefix-guarded delete) | with the key check removed, **18 of 18** refusal cases failed — a bill, notice or receipt key and another utility's export were deleted |
| 2 | `job_artifacts` + tenancy migration `0055` (FORCE RLS, three database checks) | with RLS disabled the NOSUPERUSER probe saw the other utility's row (`1 == 0`) |
| 3 | `apps/tenancy/export_store.py` (publish, find, hand over, sweep) | with the sweep's utility filter removed, another utility's key reached the adapter and was refused (`(1,0,1) != (1,0,0)`) |
| 4 | the three writers build in a scratch folder and publish | — |
| 5 | download → 302 to a signed link; report token → stream; run history → row status | — |
| 6 | daily beat sweep, `tenancy.export_retention_sweep`, 03:47 UTC, one task per utility | — |
| 7 | volume, EFS plan, `JOB_ARTIFACTS_DIR`, Dockerfile `mkdir` removed; docs | `test_no_two_app_containers_share_a_directory` replaces the test that REQUIRED the shared volume |

**The re-take of §2**, with nothing shared on disk:
- **Setup:**
  - web (gunicorn) and worker (celery `-Q celery,billing`) as separate processes, each with its OWN `TMPDIR`;
  - `JOBS_EAGER=false`;
  - both pointed at one S3 bucket on an S3 emulator.
- **Request:** `POST /api/exports {"resource":"premises"}` → 202, and the worker reports *"export … stored 748 byte(s) at t/brazosbend/export/2026/10/01a0fd38-39af-7f8d-91fa-9a1810d80233.csv"*.
- **Download:** `GET /api/exports/<id>/file` → **302**, `Cache-Control: no-store, private`, signed for `attachment; filename="brazosbend_premises_full-list_current-state_20261002T1025.csv"`, 4 hours.
- **Following the link:** **200 `text/csv`**, 748 bytes, the Premises CSV.
- **Scratch:** both scratch folders were empty afterwards.
- **In a browser:** `10-scripts/s3a_def_met_4954_s3_export_walkthrough.mjs` (Premises list → Export → *Download the CSV*) saved `brazosbend_premises_full-list_current-state_20261002T1032.csv`, 748 bytes — **not `file.json`**.

## 10 · The first real deployment, and the host checklist (2.459.1 + 2.460.1)

**What the PO's developer saw on 2026-10-02**, on 2.455.0, with the app at
`app-dev.bynry.com` and the API at `api-smart360-dev.bynry.com`:

1. A Premises export sat in `running` (*"done 73"*) long after it started, with no celery
   error and nothing in the bucket. After the celery task was given **more CPU and memory**,
   the same export logged *"stored 4849 byte(s) at t/odysseus-water-utility/export/…"* and
   the object was in S3. So the first export was a worker that died or starved between
   building the file and uploading it — measured below, the upload is the moment a fresh
   worker process first loads the S3 client.
2. **Download saved `file.htm`** even once the file was in S3. Cause: the link was the
   server's relative path `/api/exports/{id}/file`, which the browser resolved against the
   APP host; a static host answers any unknown path with the app's `index.html`, and Chrome
   on Windows saves that as `file.htm` (blank when opened). Reproduced on two origins here:
   the old bundle saved `file.html`, 882 bytes of `index.html`, while the worker had stored
   the 655-byte CSV. **Fixed in 2.459.1** (`DEF-TEN-9189`, the coordinator's commit
   `cb83a1096`): every link a job returns is resolved against the API host. Proved on two
   origins in Chromium: the click saved `brazosbend_premises_full-list_current-state_….csv`,
   655 bytes, and the page stayed put.

**What 2.460.1 adds (`DEF-TEN-9190`) — every way an export can fail now says so:**

| Before | Now |
|---|---|
| S3 client on boto3's defaults: 60 s connect, 60 s read, five attempts — **311 s** measured before a silent endpoint fails one upload | 5 s connect, 60 s read, 3 retries (`DOCUMENT_STORAGE_CONNECT_TIMEOUT` / `_READ_TIMEOUT` / `_MAX_ATTEMPTS`) |
| nothing logged between *"wrote N rows"* and *"stored"* | `export <job>: built premises, 73 row(s)` → `uploading <n> byte(s) to s3://<bucket> via <endpoint> in <region> at <key>` → `stored` |
| a failure was the job's own traceback; a hang was nothing | ONE ERROR line: `export <job>: publish FAILED while uploading - key …, s3://… - File storage refused the upload. (ClientError: …)`, and the job fails with that plain sentence |
| "stored" meant *the upload call returned* | the worker reads the object back (HEAD) and compares its size before the row says `stored` |
| a job killed mid-export said `running` until the 2 h 17 min soft limit | every 10 min celery-beat fails an export job with no progress for 30 min (`EXPORT_STALL_SECONDS`), reason *"The export stopped responding."*, never a bill run |
| a worker with no bucket started and took jobs | it **refuses to start** (`smartbillhub.E003`), and every worker logs where it writes at start: `celery worker (build 2.460.1): export storage: s3://<bucket> via AWS in <region> - reachable` — or `UNREACHABLE from this process - <why>` |
| a succeeded job with no file, or a file deleted from the bucket, was a silent 404 | still the same 404 to the browser (HR-1), and an ERROR line naming the job and the key |
| celery runs Django's system checks when a worker starts (its Django fix-up), so the document check asked the bucket for its retention rule with the upload client — measured: a worker on a silent path took **4 min** to start | start-up questions use a separate 3 s / 5 s / one-attempt client: the same worker starts in **14 s** and says `UNREACHABLE` |

**Measured on two origins here** (app on one host, API on another, gunicorn + celery on
production settings, an S3 emulator): a worker whose S3 endpoint accepts and never answers
logged *uploading* at 20:23:01 and *publish FAILED … File storage did not answer.* at
20:27:10, and the Premises screen showed *"The export didn't finish."* with no Download
link; a worker pointed at a bucket that does not exist failed the export in under a second
with *"The storage bucket does not exist."*; a worker with no bucket at all exited with
code 1 and `REFUSES TO START (smartbillhub.E003)`.

⚠ **Not yet on screen: the REASON.** The job record carries it (`error`:
`ExportNotStored: File storage did not answer.`) and the log carries it, but the Export
control still renders only *"The export didn't finish."* Showing the sentence is a
one-function change to `exportOutcome` in `07-frontend/src/features/exports/ListExportButton.tsx`,
held back in 2.460.1 because that file was being changed by the 2.459.1 link fix.

### 10.1 Host checklist — every item, per container

**Environment** (one `06-backend/.env` in docker-compose; one task definition each on ECS —
⚠ law 4: a template change reaches no host that already has a `.env`):

| Variable | web (`backend`) | `celery` | `celery-billing` | `celery-beat` |
|---|---|---|---|---|
| `DJANGO_SETTINGS_MODULE=config.settings.production` | ✔ | ✔ | ✔ | ✔ |
| `DOCUMENT_STORAGE_BUCKET` (the environment's ONE bucket) | ✔ hands out links | ✔ **uploads** | ✔ **uploads** print sets | ✔ (runs the sweep's fan-out) |
| `DOCUMENT_STORAGE_REGION` (the bucket's region, e.g. `us-east-1`) | ✔ | ✔ | ✔ | ✔ |
| credentials: a **task role** (ECS) or `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | ✔ | ✔ | ✔ | ✔ |
| `DOCUMENT_STORAGE_ENDPOINT_URL` | **leave unset on AWS**; set only for an S3-compatible emulator, and then identically on all four | | | |
| `DOCUMENT_STORAGE_SSE` | leave unset (`AES256`) | | | |
| `JOBS_EAGER=false` | ✔ | ✔ | ✔ | ✔ |
| optional: `DOCUMENT_STORAGE_CONNECT_TIMEOUT` 5 · `_READ_TIMEOUT` 60 · `_MAX_ATTEMPTS` 3 · `EXPORT_STALL_SECONDS` 1800 | defaults are right | | | |

**IAM** — the task role of every app task carries the policy written out in
`02-aws-runbook.md` §10.6: `s3:PutObject`, `s3:GetObject` (which also covers HEAD) and
`s3:AbortMultipartUpload` on `t/*`; `s3:DeleteObject` on `t/*/export/*` and **nowhere
else**; optionally `s3:ListBucket` + `s3:GetBucketObjectLockConfiguration` on the bucket
for the start-up checks.

**Network** — the worker tasks need a route to S3 exactly as web does: a NAT gateway or an
**S3 gateway VPC endpoint** in the route table of the worker's subnet. A worker in a
private subnet without either logs `UNREACHABLE from this process` at start, and each
export then fails in under a minute with *"Could not reach file storage."*

**Size** — measured on this build (production settings, PostgreSQL 16, moto S3):

| Process | Resident memory |
|---|---|
| a Django process after `django.setup()` | 131 MB |
| + the first S3 use in that process (`import boto3` + client) | **+21 MB** → 152 MB |
| celery main process, after start | 198 MB |
| one celery pool child after running exports | 188 MB |
| a print set, per 2,000 bills (09-infra/04 §3) | +10 MB, plus up to 32 MB of upload buffers (8 MB parts × 4) |

So **one celery container with the shipped `--concurrency 2` is about 570 MB resident
before any large job** (main + two children; copy-on-write sharing wears off as each child
works). **Minimum: 1 GB for `celery`, 1 GB for `celery-billing` (2 GB if print sets above
~10,000 bills are expected), 0.5 vCPU each.** A 512 MB task — the smallest Fargate size, and
the most likely original size given that resizing fixed it — runs out exactly where the
developer's export stopped: the child has built the file and is loading the S3 client for
the first time. **The check:** ECS console → the cluster → Tasks → *Stopped* → the
celery task's *Stopped reason* reads `OutOfMemoryError: Container killed due to memory
usage`, or the container's exit code is **137**; on docker-compose, `docker inspect
<container> --format '{{.State.OOMKilled}}'` reads `true`. A pool child killed by the
kernel inside a task that survives leaves `WorkerLostError` / `exited with 'signal 9
(SIGKILL)'` in the celery log; a whole task killed leaves nothing in it, which is the
silent case 2.460.1's stall sweep now closes.

**Restart** — after changing any of the above, **rebuild BOTH images and restart all four
services** (web, celery, celery-billing, celery-beat). Then read each worker's first lines:
`celery worker (build 2.460.1): export storage: s3://… - reachable`. A worker that prints
no such line is not on this build.

### 10.2 Which of these the developer's host most likely lacked

- **Memory on the celery task** — most likely, and the developer's own resize confirms it:
  the export stopped after building 73 rows, at the first S3 use, with no error, and worked
  after the task was given more. Set ≥ 1 GB.
- **Not the bucket, region or IAM** — the resized worker stored the file with the same
  settings and role, and web already filed documents.
- **The `file.htm`** was not configuration at all: it was ours (`DEF-TEN-9189`), fixed in
  2.459.1, and needs only the new front end deployed.

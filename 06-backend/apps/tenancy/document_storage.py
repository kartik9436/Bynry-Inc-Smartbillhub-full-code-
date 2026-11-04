# ── Trace ──────────────────────────────────────────────
# Change:   CR-049 task 1 — the storage seam. Three PO rulings, 2026-08-30:
#           (a) "we will need storage - on cloud - define proper engineering
#           for it; later document retrival become an issue - look at volume,
#           performance, speed, cost, you will ahve to save link in DB for PDF
#           links, also you ahve to see tenant wise seperations"
#           (b) "dont expire it in minutes - exprise it in 3 or 4 hours"
#           (c) "curently we will start with AWS, but we need to keep it multi
#           cloud - google or any other cloud - in future we mght have
#           differnt requirements"
# Rules:    BR-NOT-027 (a sent legal document is frozen AS THE DOCUMENT) ·
#           NFR-33 (STORED ARTIFACTS) · NFR-35 (write-once immutable object
#           lock, 7-year retention) · BR-NOT-005 / TD-8 (provider adapters
#           behind ONE seam — the idiom this file copies) · CLAUDE.md rule 1
#           (tenant scoping) · hard-won law 3 (defaults fail closed) ·
#           hard-won law 1 (a comment claiming a guarantee is not the guarantee)
# Tests:    06-backend/tests/test_cr049_t1_document_store.py
# Impacts:  apps/tenancy/document_store.py is the ONLY caller. Nothing else in
#           this product may import this module — see "NEVER A KEY AS AN INPUT".
# ───────────────────────────────────────────────────────
"""Where a document's BYTES live: one seam, one shipped cloud, room for others.

This is the idiom `apps/notifications/provider_seam.py` uses for delivery
providers, for the same reason: **which vendor, and whether there is one at
all, is a deployment fact and not a code fact.**

⚠ THE SEAM IS DRAWN AT INTENT, NOT AT MECHANISM — READ THIS BEFORE CHANGING IT
------------------------------------------------------------------------------
PO ruling 2026-08-30: *"curently we will start with AWS, but we need to keep it
multi cloud - google or any other cloud - in future we mght have differnt
requirements"*.

**"S3-compatible" sounds like it solves that, and it does not.** The S3 API is
genuinely portable for the COMMON operations — put, get, pre-sign, checksum —
and Google's interop mode and MinIO both speak it. **It is NOT portable for the
compliance features this entire rule depends on.** Object lock and WORM,
lifecycle transitions and customer-managed encryption keys are spelled
differently on every cloud, and Azure Blob needs a real adapter rather than an
endpoint swap.

So the interface below says **"store this immutably for seven years"** and lets
each cloud's adapter decide what that is: S3 Object Lock in COMPLIANCE mode on
AWS, a bucket retention policy on GCS, an immutability policy on Azure. **An
interface carrying `set_object_lock(mode="COMPLIANCE")` would be an AWS
interface wearing a neutral name, and the second cloud would be a rewrite
rather than an addition.** That sentence is here because it is the thing a
later lane will otherwise undo while "simplifying" — the parameter looks like
harmless plumbing right up to the day somebody has to add GCS.

**And if a cloud cannot express a compliance feature, its adapter does not fake
it.** `guarantees_immutable_retention` is on the interface, and `backend()`
refuses to hand a production deployment a backend that answers False. A backend
that silently stored a deletable object would be worse than no backend: the
whole point of this store is a guarantee, and hard-won law 3 is exactly about
which way an unconfigured system should fail.

**Today there is ONE cloud adapter and it is AWS**, named `AwsS3Storage` and
not `S3CompatibleStorage`, because naming it for the protocol would be claiming
a portability the guarantee does not have. A GCS or Azure adapter is a new
class here, a new value in `document_models.STORAGE_BACKENDS`, and a migration.

THE SEVEN DECISIONS THIS FILE IMPLEMENTS
-----------------------------------------
Made under the standing PO ruling of 2026-08-09, recorded in
`12-governance/02-decision-log.md` on 2026-08-30 and in `CR-049` step 5d(e).
**They are decided. Do not re-open them here; change them there.**

1. **VENDOR-NEUTRAL INTERFACE, AWS SHIPPED FIRST** — as amended by ruling (c)
   above. The interface names no cloud; exactly one adapter exists.
2. **A FILESYSTEM BACKEND FOR TESTS AND LOCAL DEV**, behind the same interface,
   chosen by settings, **needing no dependency at all** — which is what keeps
   the suite honest without a cloud account.
3. **KEY LAYOUT `t/<utility web name>/<module>/<yyyy>/<mm>/<file id>[.ext]`** —
   ⚠ **AMENDED 2026-10-02 BY `CR-160-BRC10` (PO), SUPERSEDING
   `t/<tenant_id>/<yyyy>/<mm>/<document_id>`.** PO, verbatim: *"Change the S3
   key layout for utility-specific files to t/<tenant>/<function>/<yyyy>/<mm>/
   <object> in ONE bucket per environment"*, *"Instead of Fucntion can you do it
   module"*, *"STart from t - dont add Sbh-prod - ew have bucket seperated out
   enviornment wise"*, *"Yes, web name"*. Worked example: a September 2026 bill
   PDF for Austin Water is `t/austin-water/billing/2026/09/<file id>.pdf`.
   **ONE bucket per environment; the key starts at `t/` and never names the
   bucket.** The utility folder is `tenants.subdomain` (BR-TEN-011), the module
   is `document_models.DOCUMENT_KIND_MODULE[kind]` from the fixed list
   `STORAGE_MODULES`; both are read from the ROW being written, never from a
   caller. Dated so a lifecycle rule moves cold objects **without reading the
   database** — that is what makes the archive cost about $8 a month rather
   than $27 (the arithmetic is in `document_models.py`). **OLD-SHAPE KEYS STILL
   LOAD**: every row stores its exact key, nothing was moved and no
   `storage_key` was rewritten, so `_require_key` accepts both shapes.
   ⚠ A web name is set once at sign-up and no product path changes it — but
   nothing in the DATABASE forbids an operator changing it; if one ever does,
   older files stay under the old folder, still readable by their stored key,
   and a whole-utility prefix operation would miss them (decision log
   2026-10-02).
4. **TENANT SEPARATION IS THE DATABASE ROW, NOT THE PREFIX.** See below; it is
   the thing a reader is most likely to get wrong.
5. **DELIVERY IS A SHORT-LIVED TEMPORARY URL** — four hours, per ruling (b).
   Never a public object, never a permanent link. See `url_ttl_seconds`.
6. **ENCRYPTION AT REST ON.** ~~IMMUTABLE RETENTION FOR NFR-35's SEVEN YEARS —
   beside the database trigger, not instead of it.~~ ⚠ **THE LOCK HALF IS
   SUSPENDED 2026-10-02 BY `CR-160-BRC10` (PO): NO FILE IS OBJECT-LOCKED, LEGAL
   FILES INCLUDED, AND NO FILE CARRIES AN EXPIRY TAG.** PO, verbatim: *"we dont
   want this to be enabled right now - dont lock it"*. The lock stays a setting
   — `DOCUMENT_STORAGE_OBJECT_LOCK_MODE`, default now `NONE` — and switching it
   on later applies ONLY to files written after that moment; a file written
   unlocked can never be locked afterwards. **What that costs, stated to the
   PO:** the product still never deletes a sent bill or legal notice (the
   database row stays write-once), but someone with direct access to the
   storage account could delete or overwrite the FILE. The boot check still
   refuses a bucket carrying a DEFAULT retention rule (`core/storage_guard.py`),
   because a default rule would lock every file written — exports included —
   for seven years, and in COMPLIANCE mode nobody could delete one.
7. **THE CONTENT HASH IS THE OBJECT'S CHECKSUM AS WELL AS A COLUMN**, verified
   on read.

⚠ TENANT SEPARATION IS THE DATABASE ROW. THE PREFIX IS A NAMING CONVENTION.
----------------------------------------------------------------------------
**This is the sentence to read twice.** `t/<web name>/…` (and the older
`t/<tenant_id>/…`) looks like isolation and is not. An object store has no
row-level security and no `app.tenant_id`; a prefix is a string in a name, and anything holding the bucket credentials can
read every prefix in it.

**What actually prevents a cross-tenant read is that the only way to LEARN a
key is to read a row of `stored_documents`, and that table is RLS
`FORCE`-scoped.** The prefix earns its place for operational reasons — a bucket
policy, an access log, a per-tenant export, a lifecycle rule — and for none
other.

Three rules follow, enforced in the signatures below rather than requested:

  * **NEVER LIST THE BUCKET.** There is no `list()` on this interface and there
    must never be one. Enumeration is always a database query — and that is
    what makes the bulk export the PO asked for POSSIBLE rather than blocked: a
    listing returns keys and byte counts, the table returns *the March bill for
    account ACC-1042, 61 KB of PDF, hashed to abc…*.
  * **NEVER DERIVE A KEY FROM A TENANT OR A MODULE A CALLER SUPPLIED.**
    `key_for` takes the utility's web name and the module from the row being
    written (`document_store` reads the web name from `tenants` under the
    session's own tenant, and the module from the row's kind through a fixed
    map), and `document_store` is its only caller.
  * **NEVER ACCEPT A KEY AS AN INPUT PARAMETER** from anything above
    `document_store`. Every function here takes a key, because that is what a
    storage backend does — and the one module allowed to call them resolves
    that key from an RLS-scoped row and from nothing else.

⚠ DEFAULTS FAIL CLOSED — HARD-WON LAW 3, AND IT IS WHY `backend()` LOOKS ODD
-----------------------------------------------------------------------------
`sslmode=disable` and `ALLOWED_HOSTS=localhost` each blocked a live deploy
because the SAFE option was the one somebody had to type. Here the dangerous
option is a production deployment quietly writing legal documents to a
container's local disk, where the next restart destroys them.

So:

  * `DOCUMENT_STORAGE_BACKEND` defaults to **`"aws_s3"`**, everywhere;
  * with no bucket configured, `backend()` **RAISES** — it does not fall back;
  * choosing the filesystem backend takes **TWO** deliberate settings, the
    second of which (`DOCUMENT_STORAGE_ALLOW_FILESYSTEM`) is False in
    `base.py` and True only in `config/settings/test.py` and `local.py`;
  * and a backend that cannot promise immutable retention is refused unless
    that same second setting is on.

That two-key shape is copied deliberately from `FIELD_ENCRYPTION_KEYS` /
`FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS`, which solves the identical problem one
subsystem over: a development convenience that must be impossible to reach by
accident.

⚠ AND A TEMPLATE CHANGE NEVER REACHES A HOST THAT ALREADY HAS A `.env`
(hard-won law 4). Adding these settings to `.env.example` fixes nothing already
deployed. A host upgraded past this commit and not given a bucket **will refuse
to store documents**, loudly, at the first attempt — which is the correct
outcome and is not a bug report.

WHAT A DEPLOYMENT MUST CONFIGURE, AND WHAT HAPPENS IF IT DOES NOT
------------------------------------------------------------------
    DOCUMENT_STORAGE_BUCKET          required. Empty ⇒ every store and every
                                     fetch raises StorageNotConfigured.
    DOCUMENT_STORAGE_REGION          required by AWS.
    DOCUMENT_STORAGE_ENDPOINT_URL    normally empty. See `AwsS3Storage`.
    DOCUMENT_STORAGE_URL_TTL_SECONDS default 14400 — FOUR HOURS, ruling (b).
                                     May be shortened without a deploy; may not
                                     be lengthened. See `url_ttl_seconds`.
    DOCUMENT_STORAGE_SSE             default "AES256". Empty is refused.
    DOCUMENT_STORAGE_RETENTION_YEARS default 7 (NFR-35).
    DOCUMENT_STORAGE_OBJECT_LOCK_MODE
                                     default "NONE" — ⚠ CHANGED 2026-10-02 by
                                     `CR-160-BRC10` (PO: *"dont lock it"*); it
                                     was "COMPLIANCE". "COMPLIANCE" or
                                     "GOVERNANCE" switch the per-object lock
                                     back on, for files written AFTER that
                                     moment only, and need a bucket created
                                     with Object Lock. See `object_lock_mode`.

Credentials are NOT settings here. `boto3` resolves them the way every AWS
deployment already does — an instance role, a task role, or the standard
environment variables — so this repo never holds a secret it does not need and
`DOCUMENT_STORAGE_*` can live in plain configuration.

**AND TWO THINGS THIS CODE CANNOT DO FOR YOU**, stated here because law 1 says
a comment claiming a guarantee is not the guarantee:

  * ⚠ **UNDER `CR-160-BRC10` (2026-10-02) NO OBJECT IS LOCKED, SO THIS
    BULLET APPLIES ONLY TO A DEPLOYMENT THAT TYPES `COMPLIANCE`/`GOVERNANCE`
    BACK ON — AND A BUCKET MUST NEVER CARRY A DEFAULT RETENTION RULE**, which
    `core/storage_guard.py` refuses at boot. Kept below as the record of why.
    **Object Lock must be enabled ON THE BUCKET AT CREATION.** AWS cannot turn
    it on afterwards through the console or the API. `put()` sends a
    retain-until date with every object, and on a bucket without Object Lock
    that parameter is REJECTED — loudly, which is the good failure — so the
    seven-year guarantee is a bucket setting this repo can neither make nor
    assert. It is the one part of `NFR-35` no test here can prove, and it
    belongs on the deployment checklist.

    ⚠ **AND IT HAS ALREADY COST ONE DEPLOYMENT A DAY (2026-09-03).** The bucket
    was created, the credentials were right, and tenant creation still stopped
    at step 8 — *Bills, first month* — with
    `InvalidRequest: Bucket is missing ObjectLockConfiguration`, which names
    neither the setting nor the fix. The bucket cannot be repaired in place:
    it is replaced, or `DOCUMENT_STORAGE_OBJECT_LOCK_MODE=NONE` is typed to run
    without the lock while the deployment holds no real documents.
  * **The lifecycle rule that moves year-old objects to cold storage** is
    likewise a bucket setting. Without it the archive costs about $27 a month
    for a hundred utilities instead of about $8. Nothing breaks; it is money.

THE DEPENDENCY, NAMED OUT LOUD
-------------------------------
**`boto3` is added to `06-backend/pyproject.toml` as a RUNTIME dependency**,
not a dev one. That file already carries the scar: `cryptography` was
importable in the dev container and undeclared, so every local test passed and
the shipped image would have raised `ModuleNotFoundError` — the Dockerfile
builds its requirements from that list and from nothing else.

It is still imported **at call time** rather than at module scope, so that
importing this file, running the suite and starting the application all work on
a deployment with no object store — which is every deployment today. When it is
absent the refusal names the package instead of a traceback.

⚠ **AND IT IS NOT INSTALLED IN THE ENVIRONMENT THIS WAS WRITTEN IN**, so the
AWS adapter is exercised against an injected client (`set_s3_client_factory`).
That proves the REQUEST — the key layout, the sha256 checksum, the encryption
mode, the retain-until date and the URL call — and **does not prove a real
round trip against a real bucket.** REPORTED, not hidden.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import os
import re
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import UUID

from django.conf import settings

from apps.tenancy.document_models import (
    BACKEND_AWS_S3,
    BACKEND_FILESYSTEM,
    STORAGE_MODULES,
)

# ═══════════════════════════════════════════════════════════════════════════
# REFUSALS — plain exceptions, deliberately not catalog errors
# ═══════════════════════════════════════════════════════════════════════════
# Nothing here is reached by an HTTP request in this task: there is no endpoint
# until CR-049 task 3. A `message_key` invented now would be an i18n catalogue
# entry with no call site (G18's shape) and a refusal string nobody ever reads.
# Task 3 maps these onto the error envelope when it builds the door.


class DocumentStorageError(RuntimeError):
    """Anything wrong with the bytes half of the document store."""


class StorageNotConfigured(DocumentStorageError):
    """This deployment cannot store documents, and it says so rather than guessing.

    Raised — never swallowed, never downgraded to a local-disk fallback — when
    a bucket, a client library, an encryption mode or a retention guarantee is
    missing. Hard-won law 3.
    """


class StorageWriteRefused(DocumentStorageError):
    """The store was reached, configured, and refused the write anyway.

    Distinct from `StorageNotConfigured`, which means nobody has set this
    deployment up yet and is raised before any call leaves the process. This one
    carries a live refusal from the service, translated into a sentence naming
    what to do about it — see `_translate_put_failure`, which raises exactly one
    of these and passes every other failure through untouched.
    """


class StoredObjectMissing(DocumentStorageError):
    """The row says a key; the store has nothing at it.

    A DIFFERENT condition from "no document was ever stored for this bill",
    which `document_store` answers without touching this module. Collapsing the
    two would let a deleted object read as a document that was never produced —
    the exact substitution `BR-NOT-027` forbids one layer up.
    """


class ContentHashMismatch(DocumentStorageError):
    """The bytes came back and they are not the bytes that went in."""


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════

#: ⚠ FOUR HOURS — PO ruling 2026-08-30, verbatim: *"dont expire it in minutes -
#: exprise it in 3 or 4 hours"*. This supersedes `CR-049` step 5d(e) decision 5
#: as first written ("minutes, not hours"), and the reason is a real workflow
#: rather than a preference: the bulk export hands a client a manifest of
#: temporary URLs that it works through in parallel over tens of minutes, and a
#: five-minute link makes that impossible. Four hours also survives somebody
#: opening a bill, being interrupted, and coming back to it.
#:
#: **WHAT THAT COSTS, STATED PLAINLY RATHER THAN BURIED.** The URL is a bearer
#: token for that ONE document: it carries no session, no tenant context and no
#: role check, so whoever holds it can read the document for four hours —
#: including someone it was forwarded to. **The exposure is BOUNDED**: it
#: reaches exactly one document and cannot be used to discover, list or reach
#: another, because a key is unguessable and nothing here lists a bucket. The
#: PO has accepted that trade.
#:
#: The cap equals the default on purpose, which makes the setting a way to
#: SHORTEN the life of a link without a deploy and not a way to lengthen it. A
#: link that needs to outlive four hours is a new link.
DEFAULT_URL_TTL_SECONDS = 4 * 60 * 60
MAX_URL_TTL_SECONDS = 4 * 60 * 60

#: NFR-35: *"e-signed agreements + import source files are WRITE-ONCE
#: (immutable object lock), retention 7yr with their financial records"*.
#: Applied to every kind and not only those two, because `CR-049` puts the bill
#: and the notice under the same freeze — and a retention that varies by kind
#: is a retention somebody has to remember.
DEFAULT_RETENTION_YEARS = 7

#: ⚠ **THE LOCK IS A SETTING BECAUSE A DEPLOYMENT HOLDING NO REAL DOCUMENTS
#: MUST BE ABLE TO CLEAR ITS OWN TEST BILLS** — PO 2026-09-03, mid S3 setup:
#: *"Until we are in beta mode We should able to delete these pdfs"*.
#:
#: **NFR-35 IS NOT AMENDED AND MUST NOT BE READ AS AMENDED.** It governs a
#: utility's real documents, and it still says seven years, write-once. This
#: setting is an environment-scoped exception for a deployment that holds none
#: of them, and it defaults to the strict value so that reaching the weaker
#: ones takes somebody typing (hard-won law 3).
#:
#: The three values, and they are three rather than two because AWS refuses
#: two of them on a bucket that was not CREATED with Object Lock enabled:
#:
#:   COMPLIANCE  the default until 2026-10-02. Nothing can shorten or remove
#:               the retention for its whole life — not an administrator, not
#:               the account root. This is what `NFR-35` asks for.
#:               ⚠ SUSPENDED BY `CR-160-BRC10`: NONE is the default now.
#:   GOVERNANCE  the same lock, deletable by a principal holding
#:               `s3:BypassGovernanceRetention`. A policy rather than a
#:               guarantee, which is exactly why it is not the default.
#:   NONE        THE DEFAULT FROM 2026-10-02 (`CR-160-BRC10`). No lock
#:               parameter is sent at all. **The only value that works
#:               on a bucket created WITHOUT Object Lock**, where the other two
#:               are refused by S3 with *"Bucket is missing
#:               ObjectLockConfiguration"* — and Object Lock cannot be switched
#:               on after a bucket is created, so that bucket cannot be fixed
#:               in place. ("Beta only" until the PO ruled it the default.)
#:               Nothing written under it is protected from deletion by
#:               anything except an IAM policy.
#:
#: S3 permits raising an object's lock from GOVERNANCE to COMPLIANCE and
#: forbids the reverse, so nothing written during a beta blocks the stricter
#: posture later — but an object written under NONE has no lock to raise.
OBJECT_LOCK_COMPLIANCE = "COMPLIANCE"
OBJECT_LOCK_GOVERNANCE = "GOVERNANCE"
OBJECT_LOCK_NONE = "NONE"
OBJECT_LOCK_MODES = (OBJECT_LOCK_COMPLIANCE, OBJECT_LOCK_GOVERNANCE, OBJECT_LOCK_NONE)

#: The two a deployment must TYPE, and the reason the refusal in `backend()`
#: below lets them through: both give up the retention guarantee, so both are
#: decisions rather than defaults.
OBJECT_LOCK_WEAKER_THAN_NFR35 = (OBJECT_LOCK_GOVERNANCE, OBJECT_LOCK_NONE)

#: ⚠ **THE DEFAULT IS `NONE` FROM 2026-10-02 (`CR-160-BRC10`, PO: *"we dont
#: want this to be enabled right now - dont lock it"*).** It was COMPLIANCE.
#: No file is locked — legal files included — and switching a stricter mode
#: on later applies only to files written after that moment.
DEFAULT_OBJECT_LOCK_MODE = OBJECT_LOCK_NONE

#: The key layout, decision 3 as amended by `CR-160-BRC10` (2026-10-02).
#: `{yyyy}/{mm}` is the LIFECYCLE handle; the extension is optional and comes
#: from the content type (`extension_for`). Never the bucket name.
KEY_TEMPLATE = "t/{tenant_folder}/{module}/{yyyy}/{mm}/{document_id}{ext}"

#: The utility folder: `tenants.subdomain` as BR-TEN-011 defines it — a
#: lowercase DNS label, `[a-z0-9-]`, 3–63 characters, no hyphen at either end.
#: Checked again HERE, at the key, because a folder name that slipped past
#: sign-up (a row written by hand, an import) must never reach the bucket as a
#: path: no `/`, no `..`, no space, no capital can match this.
TENANT_FOLDER_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,61})[a-z0-9]$")

#: A file extension the key may carry: short, lowercase, letters and numbers.
_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")

#: The content type → the extension written on the key. Anything not listed
#: gets NO extension rather than a guessed one — the key is still valid
#: (`[.ext]` is optional in the ruling) and the row's `content_type` is the
#: authority on what the bytes are.
_EXTENSIONS = {
    "application/pdf": "pdf",
    "text/html": "html",
    "text/plain": "txt",
    "text/csv": "csv",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/svg+xml": "svg",
    "application/json": "json",
    # The bill print set (`apps/billing/print_set.py`) — an EXPORT, stored under
    # `export/` by `apps/tenancy/export_storage.py` (PO 2026-10-02).
    "application/zip": "zip",
}

_MODULES_ALT = "|".join(re.escape(m) for m in STORAGE_MODULES)

#: A key this module produced, and the only shape a backend will touch. It
#: exists to make path traversal impossible rather than unlikely: a key is
#: machine-composed below, so anything not matching is a bug or an attack and
#: either way is refused. ⚠ **TWO SHAPES, ON PURPOSE (`CR-160-BRC10`):** the
#: current one, and the `CR-049` shape every row written before 2026-10-02
#: still carries. Nothing was moved, so both must keep loading.
_KEY_RE = re.compile(
    r"^t/[a-z0-9](?:[a-z0-9-]{1,61})[a-z0-9]/(?:"
    + _MODULES_ALT
    + r")/[0-9]{4}/[0-9]{2}/[0-9a-f-]{36}(?:\.[a-z0-9]{1,8})?$"
)
_LEGACY_KEY_RE = re.compile(r"^t/[0-9a-f-]{36}/[0-9]{4}/[0-9]{2}/[0-9a-f-]{36}$", re.IGNORECASE)


# ═══════════════════════════════════════════════════════════════════════════
# HASHING AND KEYS
# ═══════════════════════════════════════════════════════════════════════════


def content_hash(payload: bytes) -> str:
    """sha256 of the exact bytes, lowercase hex.

    Hex rather than base64 because `export_batches.content_hash` is hex and one
    product should spell a hash one way. AWS's checksum header wants base64, so
    `_checksum_b64` converts at that boundary and the column keeps the form a
    person can compare by eye. **That conversion belongs to the AWS adapter**,
    not to this function: another cloud may want it differently.
    """
    return hashlib.sha256(payload).hexdigest()


def _checksum_b64(hex_digest: str) -> str:
    """The same digest in the base64 form `x-amz-checksum-sha256` requires."""
    return base64.b64encode(binascii.unhexlify(hex_digest)).decode("ascii")


def extension_for(content_type: str) -> str:
    """`pdf` for `application/pdf`; empty for a type not on the short list."""
    base = (content_type or "").split(";", 1)[0].strip().lower()
    return _EXTENSIONS.get(base, "")


def key_for(
    *,
    tenant_folder: str,
    module: str,
    document_id: UUID | str,
    moment: dt.datetime,
    extension: str = "",
) -> str:
    """`t/<utility web name>/<module>/<yyyy>/<mm>/<file id>[.ext]` — decision 3.

    ⚠ **THE UTILITY FOLDER, THE MODULE AND THE DOCUMENT ID COME FROM THE ROW
    BEING WRITTEN, NEVER FROM A CALLER'S ARGUMENT.** `document_store.store` is
    the only caller: it reads `tenants.subdomain` for the session's own tenant
    and the module from the row's kind through `DOCUMENT_KIND_MODULE`. A key
    composed from a tenant somebody supplied is a cross-tenant read with extra
    steps, and it is decision 4's whole point.

    Refuses — never repairs — a folder that is not a BR-TEN-011 web name and a
    module not on `STORAGE_MODULES`: a folder with a `/`, `..`, a space or a
    capital would be a path, not a name.

    ⚠ `moment` is when the OBJECT is written; the row's `stored_at` is stamped
    microseconds later by the database. They can name different months only
    across a month boundary, and it does not matter: **the key is written into
    the row verbatim and is never recomputed.** A key is an output of the row,
    never a function re-evaluated against it.
    """
    folder = str(tenant_folder or "")
    if not TENANT_FOLDER_RE.match(folder):
        raise DocumentStorageError(
            f"{folder!r} is not a utility web name this store can use as a folder. "
            "BR-TEN-011: lowercase letters, numbers and hyphens, 3 to 63 characters, "
            "no hyphen at either end. Refused rather than cleaned: a folder that is "
            "not a plain name would be a path in the bucket (CR-160-BRC10)."
        )
    if module not in STORAGE_MODULES:
        raise DocumentStorageError(
            f"{module!r} is not on the fixed module list ({', '.join(STORAGE_MODULES)}). "
            "A new module is added to document_models.STORAGE_MODULES with a reason, "
            "never invented at a call site (CR-160-BRC10)."
        )
    ext = str(extension or "")
    if ext and not _EXT_RE.match(ext):
        raise DocumentStorageError(f"{ext!r} is not a file extension this store writes.")
    return KEY_TEMPLATE.format(
        tenant_folder=folder,
        module=module,
        yyyy=f"{moment.year:04d}",
        mm=f"{moment.month:02d}",
        document_id=str(document_id),
        ext=f".{ext}" if ext else "",
    )


def _require_key(key: str) -> str:
    if not (_KEY_RE.match(key or "") or _LEGACY_KEY_RE.match(key or "")):
        raise DocumentStorageError(
            f"{key!r} is not a key this store composed. Keys are built by key_for() "
            "from a row's own utility, kind and id; a key that arrived any other way is "
            "either a bug or an attempt to read another tenant's document."
        )
    return key


# ═══════════════════════════════════════════════════════════════════════════
# THE INTERFACE — written at INTENT, per the module docstring
# ═══════════════════════════════════════════════════════════════════════════


class DocumentStorageBackend(Protocol):
    """What a place to put bytes must be able to do — and nothing more.

    ⚠ **EVERY NAME HERE DESCRIBES WHAT IS WANTED, NOT HOW ANY CLOUD DOES IT.**
    `put(..., retain_for_years=7)` means *store this so nobody can change or
    delete it for seven years*; the AWS adapter turns that into Object Lock in
    COMPLIANCE mode, a GCS adapter would turn it into a bucket retention
    policy, an Azure adapter into an immutability policy. If you find yourself
    adding a parameter that only one cloud understands, the seam has moved to
    the wrong layer — see the module docstring.

    ⚠ **THERE IS NO `list` AND NO `delete`, AND BOTH ABSENCES ARE THE DESIGN.**
    Enumeration is always a database query (decision 4). Deleting is refused by
    the retention guarantee and by the table's write-once trigger, so a delete
    method here would be a door onto a locked room — and a later lane would
    find it and assume the lock was advisory.
    """

    #: `stored_documents.storage_backend` — written into the row so a fetch
    #: knows where to look, and so a deployment that switches clouds without
    #: migrating its objects finds out from the row rather than from a 404.
    name: str

    #: **CAN THIS BACKEND ACTUALLY HOLD THE PROMISE?** False means it stores
    #: bytes that something could still change or delete. `backend()` refuses
    #: to hand such a backend to a deployment that has not explicitly opted in,
    #: because a store that silently forgets its guarantee is worse than no
    #: store — see the module docstring's law-3 section.
    guarantees_immutable_retention: bool

    def put(
        self,
        *,
        key: str,
        payload: bytes,
        content_type: str,
        hex_digest: str,
        retain_for_years: int,
    ) -> None: ...

    def get(self, *, key: str) -> bytes: ...

    def temporary_read_url(self, *, key: str, expires_in: int) -> str: ...


# ═══════════════════════════════════════════════════════════════════════════
# BACKEND: the filesystem — TESTS AND LOCAL DEVELOPMENT ONLY
# ═══════════════════════════════════════════════════════════════════════════


class FilesystemStorage:
    """Bytes under a directory. Decision 2 — so the suite needs no bucket.

    **It needs no dependency at all**, which is what lets the whole store be
    proved on a machine with no cloud account.

    ⚠ **IT CANNOT HOLD THE RETENTION PROMISE AND IT SAYS SO** —
    `guarantees_immutable_retention = False`. `retain_for_years` is accepted
    and ignored, deliberately and visibly: a filesystem has no WORM, so writing
    code here that *looked* like it enforced one would be the fake this seam is
    written to prevent. `backend()` is what refuses it in production, and it
    refuses on this attribute as well as on the two settings.
    """

    name = BACKEND_FILESYSTEM
    guarantees_immutable_retention = False

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        return self.root / _require_key(key)

    def put(
        self,
        *,
        key: str,
        payload: bytes,
        content_type: str,
        hex_digest: str,
        retain_for_years: int,
    ) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename: a reader never sees a half-written document, and a
        # crash mid-write leaves a temp file rather than a truncated legal
        # instrument. The cloud adapter gets this from the service for free.
        temp = path.with_suffix(".partial")
        temp.write_bytes(payload)
        os.replace(temp, path)
        # A filesystem has no object metadata, and a backend that could not
        # report the content type would be answering a different question from
        # the real one.
        path.with_suffix(".meta").write_text(f"{content_type}\n{hex_digest}\n", encoding="utf-8")

    def get(self, *, key: str) -> bytes:
        path = self._path(key)
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise StoredObjectMissing(
                f"the document store has no object at {key!r}. The row exists, so the "
                "object was written and has since been removed — which is not the same "
                "as no document having been stored."
            ) from exc

    def temporary_read_url(self, *, key: str, expires_in: int) -> str:
        """A `file:` URL, and it does not expire because it is not a credential.

        ⚠ **THIS CANNOT BE SERVED TO A BROWSER**, which is correct: on the one
        deployment shape that reaches this backend — a developer's machine and
        the test suite — there is nobody to serve it to.
        `document_store.download_url` states that fact to its caller rather
        than dressing a local path up as a delivery mechanism.
        """
        _require_key(key)
        return f"file://{self._path(key)}"


# ═══════════════════════════════════════════════════════════════════════════
# BACKEND: AWS S3 — THE ONE CLOUD ADAPTER THAT EXISTS
# ═══════════════════════════════════════════════════════════════════════════

#: How an S3 client is obtained. Replaceable, for the reason
#: `core.audit.set_audit_sink` and `core.jobs.set_job_store` are replaceable:
#: the seam is the unit under test, and a test that needed AWS would not be run.
_client_factory: Callable[[], Any] | None = None


def set_s3_client_factory(factory: Callable[[], Any] | None) -> None:
    """Install (or clear) the callable that produces an AWS S3 client.

    Tests inject a recorder and assert the exact parameters `put` and
    `temporary_read_url` send — the key layout, the sha256 checksum, the
    encryption mode and the retain-until date. **That proves the request this
    code makes and does NOT prove that a real bucket accepts it.** Said plainly
    because law 1 is about exactly this kind of claim.
    """
    global _client_factory
    _client_factory = factory


def _default_client(config: Any = None) -> Any:
    """A `boto3` S3 client, resolved BY NAME at call time.

    A declared runtime dependency (see the module docstring), imported here
    rather than at module scope so that importing this file, running the suite
    and starting the application all work on a deployment with no object store.

    Credentials are boto3's own resolution — instance role, task role, or the
    standard environment variables — so this repo holds no secret it does not
    need.
    """
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - exercised via set_s3_client_factory
        raise StorageNotConfigured(
            "the AWS document store needs the `boto3` client and it is not importable. "
            "It IS declared in 06-backend/pyproject.toml as a runtime dependency, so "
            "this means the environment was built before that landed: rebuild the image "
            "or reinstall the project (`pip install -e .`)."
        ) from exc
    kwargs: dict[str, Any] = {"config": config if config is not None else client_config()}
    endpoint = getattr(settings, "DOCUMENT_STORAGE_ENDPOINT_URL", "") or ""
    region = getattr(settings, "DOCUMENT_STORAGE_REGION", "") or ""
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    if region:
        kwargs["region_name"] = region
    return boto3.client("s3", **kwargs)


def probe_config() -> Any:
    """SHORT timeouts for a question asked while a process STARTS (DEF-TEN-9190).

    Celery's Django fixup runs the system checks when a worker starts, so the
    bucket's retention question below is asked then — and on a silent network
    path, with the upload client's budget, that held a worker's start for four
    minutes (measured). One attempt, 3 s to connect, 5 s to answer.
    """
    from botocore.config import Config  # type: ignore[import-not-found]

    return Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 0, "mode": "standard"})


def probe_client(client: Any) -> Any:
    """`client`, or — when it is this module's own default — the same with `probe_config()`."""
    if _client_factory is not None:
        return client  # injected (tests): used as given
    return _default_client(config=probe_config())


def client_config() -> Any:
    """Explicit timeouts and a bounded retry budget for every S3 call (DEF-TEN-9190).

    ⚠ **boto3's defaults are 60 s to connect, 60 s per read and five "legacy"
    attempts**, so a worker with no route to S3 (a private subnet without a NAT
    or an S3 endpoint) held an export in `running` for minutes and logged
    nothing. The numbers live in settings (`DOCUMENT_STORAGE_CONNECT_TIMEOUT`,
    `_READ_TIMEOUT`, `_MAX_ATTEMPTS`) so a host can change them without a deploy.
    """
    from botocore.config import Config  # type: ignore[import-not-found]

    return Config(
        connect_timeout=int(getattr(settings, "DOCUMENT_STORAGE_CONNECT_TIMEOUT", 5) or 5),
        read_timeout=int(getattr(settings, "DOCUMENT_STORAGE_READ_TIMEOUT", 60) or 60),
        retries={
            "max_attempts": int(getattr(settings, "DOCUMENT_STORAGE_MAX_ATTEMPTS", 3) or 3),
            "mode": "standard",
        },
    )


def _translate_put_failure(exc: Exception, *, mode: str) -> Exception:
    """Turn ONE opaque S3 refusal into a sentence naming the fix; pass the rest through.

    ⚠ **DEF-2363, AND IT COST THE PRODUCT OWNER A DAY (2026-09-03).** The bucket
    was created, the credentials were right, and tenant creation still stopped
    eight steps in with S3's own words, relayed verbatim to the screen:

        InvalidRequest: An error occurred (InvalidRequest) when calling the
        PutObject operation: Bucket is missing ObjectLockConfiguration

    That sentence is accurate and it is unusable. It names no setting of ours,
    no console checkbox, and — the part that actually costs the day — it does
    not say that the bucket **cannot be repaired in place**, because AWS only
    accepts Object Lock at bucket creation.

    **THIS IS THE ONLY S3 ERROR THIS ADAPTER TRANSLATES, AND THE NARROWNESS IS
    THE DESIGN.** Anything else is returned unchanged so that a permissions
    error still reads as a permissions error; a layer that paraphrased every
    failure would be guessing, and a wrong guess about somebody else's error is
    worse than the error. The test for a lane tempted to generalise this: could
    you write the two fixes down? Here they are, and they are why this case
    earns a translation and no other does.

    Not a `StorageNotConfigured` — that class means *this deployment has not
    been configured yet* and is what `backend()` raises before any call. This
    one is a live refusal from a configured deployment, so it keeps
    `StorageWriteRefused`'s meaning: the store was reached and it said no.
    """
    text = str(exc)
    if "ObjectLockConfiguration" not in text:
        return exc
    return StorageWriteRefused(
        "this bucket was created WITHOUT Object Lock, so S3 refuses every write that "
        f"carries a retention lock — and this deployment writes with {mode}. "
        "AWS accepts Object Lock only at bucket creation, so THIS BUCKET CANNOT BE "
        "FIXED IN PLACE. Two ways out, and both are one line: (1) create a new bucket "
        "with Object Lock ticked ON, move anything already in the old one across, and "
        "point DOCUMENT_STORAGE_BUCKET at it — the answer for a deployment that will "
        "hold real documents; or (2) set DOCUMENT_STORAGE_OBJECT_LOCK_MODE=NONE on "
        "this host, which sends no lock and writes to the bucket you already have — "
        "for a beta holding no real documents, because nothing written under it is "
        "protected from deletion (PO 2026-09-03). Editing .env.example changes "
        f"nothing on a host that already has a .env (hard-won law 4). S3 said: {text}"
    )


class AwsS3Storage:
    """Bytes in an S3 bucket — the shipped adapter, named for its cloud.

    ⚠ **THE NAME IS `Aws…` AND NOT `S3Compatible…` ON PURPOSE.** The put/get/
    pre-sign/checksum calls below really are portable; the retention guarantee
    is not. Naming this class for the protocol would claim a portability the
    guarantee does not have, and would invite the next lane to point it at
    Google or Azure and assume `NFR-35` came along. It did not: those are their
    own adapters, and neither exists yet.

    `DOCUMENT_STORAGE_ENDPOINT_URL` exists for a VPC endpoint or an
    S3-compatible service such as MinIO on a self-hosted deployment. ⚠ **On a
    service that does not implement Object Lock, `put()` will be refused by
    that service** — loudly, which is the good failure — because this adapter
    does not check first and does not degrade. A self-host that needs a
    different retention mechanism needs an adapter, not a setting.
    """

    name = BACKEND_AWS_S3

    #: What this adapter means when nobody says otherwise. ⚠ `NONE` from
    #: 2026-10-02 (`CR-160-BRC10`, PO: *"dont lock it"*); it was COMPLIANCE.
    OBJECT_LOCK_MODE = DEFAULT_OBJECT_LOCK_MODE

    def __init__(
        self,
        *,
        bucket: str,
        client: Any,
        sse: str,
        object_lock_mode: str | None = None,
    ) -> None:
        self.bucket = bucket
        self.client = client
        self.sse = sse
        self.object_lock_mode = object_lock_mode or self.OBJECT_LOCK_MODE

    @property
    def guarantees_immutable_retention(self) -> bool:
        """True under COMPLIANCE, False under either weaker mode — and it MOVES.

        ⚠ **THIS USED TO BE `= True`, A CONSTANT, AND LEAVING IT THAT WAY WOULD
        HAVE BEEN HARD-WON LAW 1 IN ONE LINE** — *a comment claiming a guarantee
        is not the guarantee*. Under GOVERNANCE a principal with one permission
        deletes the object; under NONE there is no lock on it at all. A flag
        that answered True in either case would tell the rest of this product
        that a deletable object is a seven-year record, and the guard in
        `backend()` — the one thing that reads this — would wave it through.

        So the guard now refuses BOTH weaker modes unless somebody typed them,
        which is the whole difference between a decision and a default.
        """
        return self.object_lock_mode == OBJECT_LOCK_COMPLIANCE

    def put(
        self,
        *,
        key: str,
        payload: bytes,
        content_type: str,
        hex_digest: str,
        retain_for_years: int,
    ) -> None:
        """Write the object once: encrypted, checksummed, and locked for N years.

        Where the intent-level arguments land on AWS specifically:

          * `hex_digest` → `ChecksumSHA256` (decision 7). S3 rejects the upload
            if what it received does not hash to this, so corruption in flight
            is caught by the service and not only by our own re-hash on read.
          * `self.sse` → `ServerSideEncryption` (decision 6).
          * `retain_for_years` → `ObjectLockMode` plus a retain-until date
            (decision 6, `NFR-35`), in whichever mode this deployment resolved.
            ⚠ **Both locking modes are accepted only on a bucket CREATED with
            Object Lock enabled**; on any other bucket S3 refuses the whole
            call with *"Bucket is missing ObjectLockConfiguration"*, which is
            why that is on the deployment checklist in the module docstring
            rather than claimed here — and why `OBJECT_LOCK_NONE` exists.

        ⚠ **UNDER `NONE` THE TWO LOCK PARAMETERS ARE OMITTED ENTIRELY RATHER
        THAN SENT EMPTY.** S3 reads `ObjectLockMode=""` as a malformed request,
        not as "no lock", so the only way to write to a bucket without Object
        Lock is to not mention it. `retain_for_years` is still accepted and is
        then IGNORED — the same honest shape `FilesystemStorage` uses, and the
        reason `guarantees_immutable_retention` above goes False with it.
        """
        _require_key(key)
        request: dict[str, Any] = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": payload,
            "ContentType": content_type,
            "ChecksumSHA256": _checksum_b64(hex_digest),
            "ServerSideEncryption": self.sse,
        }
        # ⚠ NO `Tagging` — NO EXPIRY TAG ON ANY FILE, exports included
        # (`CR-160-BRC10`, PO 2026-10-02: *"dont lock it"*, answering both the
        # per-object lock and a delete-after-30-days tag). A tag a lifecycle
        # rule reads is a deletion schedule, and none was ruled.
        if self.object_lock_mode != OBJECT_LOCK_NONE:
            request["ObjectLockMode"] = self.object_lock_mode
            request["ObjectLockRetainUntilDate"] = self._retain_until(retain_for_years)
        try:
            self.client.put_object(**request)
        except Exception as exc:  # noqa: BLE001 — re-raised unless it is THE one case
            raise _translate_put_failure(exc, mode=self.object_lock_mode) from exc

    @staticmethod
    def _retain_until(years: int) -> dt.datetime:
        """Now + the retention, in UTC.

        A clock read, and legitimately so: this is not a business date
        (BR-TEN-043) but the wall-clock instant a WORM lock starts running.
        """
        now = dt.datetime.now(dt.timezone.utc)
        return now.replace(year=now.year + years)

    def default_retention(self) -> dict[str, Any] | None:
        """The bucket's DEFAULT retention rule, or None when it has none.

        ⚠ **ASKED ONLY BY THE BOOT CHECK (`core/storage_guard.py`), AND THE
        ANSWER MUST BE None (`CR-160-BRC10`, PO 2026-10-02).** A default rule
        locks every object written to the bucket — this product sends no lock,
        so S3 would apply the bucket's own — and that would lock every export
        and every upload for the rule's whole period; in COMPLIANCE mode nobody,
        not even the account root, could delete one.

        A bucket created without Object Lock answers S3's
        `ObjectLockConfigurationNotFoundError`, which means *no rule* and is
        returned as None. Any other failure is raised for the caller to report
        as "could not ask" — never as a pass.
        """
        try:
            response = probe_client(self.client).get_object_lock_configuration(Bucket=self.bucket)
        except Exception as exc:  # noqa: BLE001 — one code means "none"; the rest re-raise
            if "ObjectLockConfigurationNotFound" in f"{type(exc).__name__} {exc}":
                return None
            raise
        rule = (response or {}).get("ObjectLockConfiguration", {}).get("Rule") or {}
        return rule.get("DefaultRetention") or None

    def get(self, *, key: str) -> bytes:
        _require_key(key)
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001 — see below
            # botocore spells "no such key" as a `ClientError` carrying an error
            # code, and a VPC endpoint or proxy in front of it can raise
            # something else entirely. Catching the base class keeps this
            # adapter from importing botocore's exception module at call time
            # just to name one class — and nothing is swallowed: the
            # distinction that matters is preserved ("the object is gone",
            # never "no document was stored") and the original exception is
            # chained, so the real cause is one `__cause__` away.
            raise StoredObjectMissing(
                f"the document store could not read the object at {key!r}: {exc}"
            ) from exc
        return response["Body"].read()

    def temporary_read_url(self, *, key: str, expires_in: int) -> str:
        """A URL that works for `expires_in` seconds and then does not.

        ⚠ **A BEARER TOKEN FOR THAT ONE DOCUMENT** — see
        `DEFAULT_URL_TTL_SECONDS` for what that costs and why the PO accepted
        it. It carries no session, so anyone holding it reads the document;
        that is why the object is never public and the link is never permanent.
        """
        _require_key(key)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )


# ═══════════════════════════════════════════════════════════════════════════
# RESOLUTION — and this is the half hard-won law 3 is about
# ═══════════════════════════════════════════════════════════════════════════


def url_ttl_seconds() -> int:
    """The temporary-URL lifetime — four hours, refused if somebody lengthened it.

    A cap rather than a clamp: silently shortening a configured twelve hours to
    four would leave an operator debugging a link that expires sooner than the
    number they typed. Refusing names the setting and both numbers.
    """
    ttl = int(getattr(settings, "DOCUMENT_STORAGE_URL_TTL_SECONDS", DEFAULT_URL_TTL_SECONDS))
    if ttl <= 0 or ttl > MAX_URL_TTL_SECONDS:
        raise StorageNotConfigured(
            f"DOCUMENT_STORAGE_URL_TTL_SECONDS is {ttl}; it must be between 1 and "
            f"{MAX_URL_TTL_SECONDS} (four hours, PO ruling 2026-08-30). A temporary URL "
            "is a bearer token for one document — it carries no session and no tenant "
            "check — so this setting exists to SHORTEN a link's life, never to lengthen "
            "it. If a link needs to outlive four hours, the answer is a new link."
        )
    return ttl


def retention_years() -> int:
    """NFR-35's seven years, or whatever a deployment has raised it to."""
    return int(getattr(settings, "DOCUMENT_STORAGE_RETENTION_YEARS", DEFAULT_RETENTION_YEARS))


def object_lock_mode() -> str:
    """Which Object Lock this deployment writes with — NONE unless typed.

    ⚠ **THE DEFAULT MOVED FROM COMPLIANCE TO NONE ON 2026-10-02**
    (`CR-160-BRC10`, PO: *"we dont want this to be enabled right now - dont
    lock it"*). Typing COMPLIANCE or GOVERNANCE switches the lock back on, for
    files written after that moment only.

    Refuses an unrecognised value rather than falling back to the default. A
    misspelling that quietly became COMPLIANCE would strand a beta on a bucket
    it cannot write to, with a setting that reads as though it should work; a
    misspelling that quietly became NONE would silently drop the guarantee on a
    production deployment. Both are worse than a sentence naming the three
    values, so this refuses and names them.
    """
    raw = getattr(settings, "DOCUMENT_STORAGE_OBJECT_LOCK_MODE", "") or DEFAULT_OBJECT_LOCK_MODE
    mode = str(raw).strip().upper()
    if mode not in OBJECT_LOCK_MODES:
        raise StorageNotConfigured(
            f"DOCUMENT_STORAGE_OBJECT_LOCK_MODE is {raw!r}; it must be one of "
            f"{', '.join(OBJECT_LOCK_MODES)}. NONE is the default (PO 2026-10-02, "
            "CR-160-BRC10: no file is locked for now) and sends no lock at all. "
            "COMPLIANCE locks each file so nothing can delete it before its retention "
            "ends; GOVERNANCE keeps the lock but lets a principal holding "
            "s3:BypassGovernanceRetention delete. Both need a bucket created with "
            "Object Lock, and apply only to files written after they are switched on."
        )
    return mode


def backend() -> DocumentStorageBackend:
    """The configured place to put bytes — or a refusal naming what is missing.

    ⚠ **THERE IS NO FALLBACK PATH IN THIS FUNCTION, AND THAT IS THE POINT
    (hard-won law 3).** A production deployment with no bucket must fail at the
    first attempt to store a document. The alternative — quietly writing to
    local disk — produces a utility that believes it has seven years of legal
    documents and has a container's scratch space, and nobody finds out until a
    regulator asks.

    Reaching a backend that cannot promise immutable retention takes TWO
    settings:

        DOCUMENT_STORAGE_BACKEND = "filesystem"      # someone typed this
        DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True     # and someone typed this

    the second of which is False in `config/settings/base.py` and True only in
    `test.py` and `local.py`. That is the same two-key shape
    `FIELD_ENCRYPTION_ALLOW_INSECURE_KEYS` uses, for the same reason.

    ⚠ **THIS BUILDS A NEW CLIENT EVERY CALL, AND A BILL RUN SHOULD HOIST IT OUT
    OF ITS LOOP.** Constructing a `boto3` client costs tens of milliseconds — an
    irrelevance for one person opening one document, and 36,000 of them on a
    utility's annual bill run. It is deliberately not cached here: a cache keyed
    on settings would have to be invalidated by `override_settings`, which is
    how every refusal in this module is tested, and a stale client is a far
    worse bug than a slow one. The fix belongs to the caller that has the loop —
    resolve once, pass it down — and this note is here so that lane does not
    have to measure it first.
    """
    name = getattr(settings, "DOCUMENT_STORAGE_BACKEND", BACKEND_AWS_S3)
    allow_unguaranteed = bool(getattr(settings, "DOCUMENT_STORAGE_ALLOW_FILESYSTEM", False))

    if name == BACKEND_FILESYSTEM:
        if not allow_unguaranteed:
            raise StorageNotConfigured(
                "DOCUMENT_STORAGE_BACKEND is 'filesystem' but this settings module does "
                "not allow it. Local disk is for the test suite and a developer's "
                "machine: it can make no immutable-retention promise at all, a document "
                "written there is gone at the next container restart, and NFR-35 "
                "requires seven years. Set DOCUMENT_STORAGE_ALLOW_FILESYSTEM only in "
                "config/settings/test.py or local.py, or configure "
                "DOCUMENT_STORAGE_BUCKET and leave the backend at 'aws_s3'."
            )
        root = getattr(settings, "DOCUMENT_STORAGE_DIR", "") or ""
        if not root:
            raise StorageNotConfigured(
                "DOCUMENT_STORAGE_BACKEND is 'filesystem' and DOCUMENT_STORAGE_DIR is "
                "empty. There is no default directory on purpose — a document store "
                "that picks its own location is one nobody can find, back up or clear."
            )
        return FilesystemStorage(root)

    if name != BACKEND_AWS_S3:
        raise StorageNotConfigured(
            f"DOCUMENT_STORAGE_BACKEND is {name!r}; the document store has one cloud "
            f"adapter, {BACKEND_AWS_S3!r}, and {BACKEND_FILESYSTEM!r} for tests and "
            "local development. A second cloud (GCS, Azure) is a new adapter in "
            "apps/tenancy/document_storage.py, a new value in "
            "document_models.STORAGE_BACKENDS and a migration — not a settings change, "
            "because the retention guarantee is spelled differently on every cloud."
        )

    bucket = getattr(settings, "DOCUMENT_STORAGE_BUCKET", "") or ""
    if not bucket:
        raise StorageNotConfigured(
            "DOCUMENT_STORAGE_BUCKET is not set, so this deployment has nowhere to put "
            "a document. It does NOT fall back to local disk: a legal document written "
            "to a container's disk is destroyed by the next restart, and NFR-35 "
            "requires it for seven years. Set DOCUMENT_STORAGE_BUCKET and "
            "DOCUMENT_STORAGE_REGION."
        )

    sse = getattr(settings, "DOCUMENT_STORAGE_SSE", "") or ""
    if not sse:
        raise StorageNotConfigured(
            "DOCUMENT_STORAGE_SSE is empty, which would write customer documents to the "
            "bucket unencrypted. Encryption at rest is a decision of CR-049 step 5d(e); "
            "the default is 'AES256' and emptying it is refused rather than obeyed."
        )

    factory = _client_factory or _default_client
    resolved = AwsS3Storage(
        bucket=bucket, client=factory(), sse=sse, object_lock_mode=object_lock_mode()
    )

    # ⚠ THE LAST GUARD: NOTHING STORES A DELETABLE OBJECT BEHIND THE PRODUCT'S
    # BELIEF THAT IT IS A SEVEN-YEAR RECORD UNLESS SOMEBODY TYPED THAT DECISION.
    #
    # There are now exactly two ways to type it, and both default to the safe
    # value one file away in `config/settings/base.py`:
    #
    #   DOCUMENT_STORAGE_ALLOW_FILESYSTEM = True     a developer's machine, the
    #                                                test suite. False in base.
    #   DOCUMENT_STORAGE_OBJECT_LOCK_MODE = GOVERNANCE | NONE
    #                                                a beta holding no real
    #                                                documents (PO 2026-09-03).
    #                                                ⚠ NONE in base from
    #                                                2026-10-02 — the PO RULED
    #                                                it (CR-160-BRC10: "dont
    #                                                lock it"), so the default
    #                                                IS the typed decision now;
    #                                                it was COMPLIANCE.
    #
    # Anything else answering False is an adapter that cannot hold the promise
    # and never said so, which is the case this guard was written for and the
    # one it still refuses: the day somebody adds GCS or Azure, that adapter
    # gets refused here rather than storing deletable objects quietly.
    deliberate = allow_unguaranteed or object_lock_mode() in OBJECT_LOCK_WEAKER_THAN_NFR35
    if not resolved.guarantees_immutable_retention and not deliberate:
        raise StorageNotConfigured(
            f"the {resolved.name!r} backend cannot promise immutable retention, so it "
            "cannot hold a document NFR-35 requires kept unaltered for "
            f"{retention_years()} years. It is refused rather than used: a store that "
            "silently forgets its guarantee is worse than no store."
        )
    return resolved


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-049 task 1 (sources: 12-governance/11-change-requests.md CR-049 step 5d(e) and its 2026-08-30 amendments · 12-governance/02-decision-log.md 2026-08-30 "DOCUMENTS GO TO CLOUD OBJECT STORAGE, NOT INTO POSTGRES" · BR-NOT-027 · NFR-33/NFR-35 · 06-backend/apps/notifications/provider_seam.py, the seam idiom)
# generated: 2026-08-30 by the CR-049 task 1 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — no endpoint reaches this until CR-049 task 3) E=deferred(no-frontend-half — CR-049 task 3) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — with DOCUMENT_STORAGE_BUCKET empty, backend() was shown returning a FilesystemStorage before the refusal was written and raising StorageNotConfigured after; a temporary URL was shown live before its TTL and refused after. Verbatim transcripts in 06-backend/tests/test_cr049_t1_document_store.py and the lane report.
# exceptions: (1) `boto3` IS A NEW RUNTIME DEPENDENCY in 06-backend/pyproject.toml — reported loudly, and it is not installed in the environment this was authored in, so the AWS adapter is proved against an INJECTED client: the request is verified, a real round trip is NOT. (2) Object Lock must be enabled on the bucket at creation and no test here can assert it — deployment checklist, stated rather than claimed. (3) The lifecycle rule that makes the archive ~$8 a month instead of ~$27 is likewise a bucket setting. (4) `AwsS3Storage.get` catches a bare Exception because botocore's 404 class differs from what a proxy or VPC endpoint raises — the cause is chained, never swallowed. (5) The four-hour URL is a PO ruling that supersedes this CR's own "minutes, not hours"; what it costs is stated at DEFAULT_URL_TTL_SECONDS rather than buried.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2379 — a deployment with no document storage boots happily, and
#          says so eight steps into the first tenant anybody creates.
# Rules:   PO 2026-09-02 ("Yes - please add the check") · NFR-35 (a bill is kept
#          unaltered for seven years) · CLAUDE.md hard-won law 3 (defaults fail
#          closed — the unsafe option must be the one you type) · law 4 (editing
#          `.env.example` fixes nothing already deployed) · BR-TEN-063
# Pattern: `core/rls_guard.py` — the DEF-2717 runtime RLS guard, registered as a
#          Django system check from an AppConfig.ready(). Same shape on purpose.
# ───────────────────────────────────────────────────────
"""**CAN THIS PROCESS FILE A DOCUMENT? ASKED AT BOOT, NOT AT THE FIRST BILL.**

WHAT HAPPENED, AND WHY A STARTUP CHECK IS THE RIGHT PLACE FOR IT
----------------------------------------------------------------
On 2026-09-02 the Product Owner created a utility on a live deployment. Seven
seeding steps went green. Step 8 — *Bills, first month* — stopped with:

    StorageNotConfigured: DOCUMENT_STORAGE_BUCKET is not set, so this deployment
    has nowhere to put a document.

and steps 9, 10 and 11 fell over behind it, each correctly naming step 8 as the
one to fix. **Nothing was wrong with the code, the data or the pricing engine.**
Two environment variables were unset, and the product discovered that fact at
the moment it tried to issue a bill rather than at the moment it started.

The refusal itself is *right* and stays exactly as it is: a legal document
written to a container's disk is destroyed by the next restart, and NFR-35
requires it kept for seven years, so falling back to local disk would be worse
than refusing. What was wrong is only WHEN the deployment found out.

⚠ **THIS IS HARD-WON LAW 3 AND LAW 4 TOGETHER, WHICH IS WHY IT COST A DAY.**
Law 3 says the unsafe option must be the one you type: an unset bucket reads as
*"not configured yet"* and boots. Law 4 says editing `.env.example` fixes
nothing on a host that already has a `.env` — and that deployment had one. So
the two mechanisms that would normally catch a missing setting were both
inapplicable, and the only remaining witness was a tenant creation.

WHAT IT DOES, AND THE ONE THING IT DELIBERATELY DOES NOT DO
-----------------------------------------------------------
It calls **the same `document_storage.backend()` the bill run calls**, and
reports its refusal. It does not re-implement the rules — a second copy of
*"which settings make a working store"* would drift from the first, and the
drift would be silent in exactly the direction that matters: a check that passes
while the product refuses.

**It does NOT touch the network to RESOLVE the backend.** Resolving constructs a
client; it does not call S3. A boot check that made a round trip would turn a
slow bucket into a failed deployment, and *"can this process reach AWS right
now"* is a different question from *"is this deployment configured"*.

⚠ **ONE READ-ONLY CALL WAS ADDED ON 2026-10-02, AND IT IS THE ONLY ONE
(`CR-160-BRC10`).** The PO ruled that no file is object-locked for now
(*"we dont want this to be enabled right now - dont lock it"*) and that the boot
check must still refuse a bucket carrying a DEFAULT retention rule. That fact
lives only on the bucket, so the only way to know it is to ask the bucket once:
`get_object_lock_configuration`. **A default rule is refused (`E002`, an error
even under DEBUG):** this product sends no lock, so S3 applies the bucket's
own to every object — every bill, every upload, every export — for the rule's
whole period, and in COMPLIANCE mode nobody, not even the account root, can
delete one before it ends. **If the question cannot be asked** (no network, no
`s3:GetBucketObjectLockConfiguration` permission) **it is a WARNING and the
boot goes on** — a check that cannot answer must never pass and never block.

WHY IT IS A WARNING IN DEVELOPMENT AND AN ERROR IN PRODUCTION
-------------------------------------------------------------
`config/settings/local.py` and `test.py` set the filesystem backend on purpose,
so they resolve cleanly and this check says nothing at all. A deployment that
resolves nothing is broken, and `DEBUG = False` is what tells us we are looking
at one — Django's own `check --deploy` posture. Under `DEBUG` it degrades to a
warning so a developer who has not finished their `.env` can still run
`manage.py shell`: the failure mode this guards against is a SERVING process,
not a console.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.checks import Error
from django.core.checks import Warning as CheckWarning

#: Stable ids so a deployment can silence this DELIBERATELY (Django's
#: `SILENCED_SYSTEM_CHECKS`) rather than by deleting the check. Silencing it is
#: a decision somebody types; that is the whole difference between this and the
#: empty default it replaces.
ERROR_ID = "smartbillhub.E001"
WARNING_ID = "smartbillhub.W001"

_HEADLINE = "this deployment cannot file a document, and a bill cannot be issued without one"

#: ⚠ **THE OBJECT LOCK SENTENCE IS FIRST, AND IT IS THE ONLY IRREVERSIBLE THING
#: IN THIS FILE (2026-09-02).** It is written down in three places already — the
#: AWS runbook twice, the deployment architecture once, and a comment block in
#: `.env.example` — and every one of them is read at PLANNING time, days before
#: anybody is at a terminal creating a bucket. This message fires at exactly the
#: moment the person IS doing it, which is the only moment the warning is worth
#: anything: AWS will not let Object Lock be switched on afterwards, so a bucket
#: made without it has to be thrown away and replaced, with whatever it already
#: holds moved across.
#:
#: Hard-won law 4 is the same lesson one layer up — *a template change never
#: reaches a host that already has a `.env`* — and this is that law applied to a
#: WARNING rather than to a setting. Documentation that is correct and unread
#: has the same effect as documentation that is wrong.
#: ⚠ AMENDED 2026-10-02 (`CR-160-BRC10`): no file is object-locked now, so the
#: hint no longer tells anyone to create the bucket with Object Lock — it says
#: the opposite thing that matters: NO DEFAULT RETENTION RULE on the bucket.
_HINT = (
    "Create ONE bucket for this environment WITHOUT a default retention rule — "
    "no file is object-locked for now (PO 2026-10-02, CR-160-BRC10), and a default "
    "rule would lock every file for its whole period. Then set "
    "DOCUMENT_STORAGE_BUCKET and DOCUMENT_STORAGE_REGION on this host. "
    "Editing .env.example changes nothing on a host that already has a .env "
    "(hard-won law 4). Until they are set, tenant creation stops at the step "
    "that issues the first month's bills and every step behind it stops with it. "
    f"To run without a document store on purpose — a console, a migration "
    f"container — silence {ERROR_ID} in SILENCED_SYSTEM_CHECKS, which is a "
    "decision somebody types rather than a default nobody sees."
)


def check_document_storage(app_configs: Any = None, **kwargs: Any) -> list[Any]:
    """Django system check: does `document_storage.backend()` resolve?

    Registered from `apps.tenancy.apps.TenancyConfig.ready()` — tenancy owns the
    document store. It is deliberately UNTAGGED: Django filters by tag only when
    a caller passes one, and every path that matters here (`manage.py migrate` on
    the entrypoint, `runserver`, gunicorn through `config/wsgi.py`) passes none.
    A tag would group it and could never narrow when it runs, so leaving it off
    says the same thing with less to misread later.
    """
    from apps.tenancy import document_storage

    try:
        resolved = document_storage.backend()
    except document_storage.StorageNotConfigured as refusal:
        # The store's own sentence, verbatim. It already names the settings and
        # says why there is no fallback; paraphrasing it here would give this
        # product two explanations of one fact that can disagree.
        detail = f"{_HEADLINE}. {refusal}"
        if getattr(settings, "DEBUG", False):
            return [CheckWarning(detail, hint=_HINT, id=WARNING_ID)]
        return [Error(detail, hint=_HINT, id=ERROR_ID)]
    except Exception as exc:  # noqa: BLE001
        # Anything else is this CHECK being wrong about the world rather than the
        # world being misconfigured — a missing dependency, a client factory that
        # raises. Say so as a warning and never block a boot on our own bug.
        return [
            CheckWarning(
                f"the document-storage boot check could not run: {type(exc).__name__}: {exc}",
                hint=(
                    "This is the CHECK failing, not the store. The store's own "
                    "refusal still fires at the first document either way."
                ),
                id=WARNING_ID,
            )
        ]
    return _check_no_default_retention(resolved)


#: A bucket with a DEFAULT retention rule — refused at every DEBUG level.
RETENTION_ERROR_ID = "smartbillhub.E002"

_RETENTION_HINT = (
    "Remove the bucket's default retention rule (S3 console: the bucket → "
    "Properties → Object Lock → Edit → Default retention: Disable). Object Lock "
    "itself may stay enabled on the bucket; only the DEFAULT rule must go. Files "
    "already written under the rule stay locked until it ends — nothing can undo "
    "that for COMPLIANCE. To lock files on purpose later, type "
    "DOCUMENT_STORAGE_OBJECT_LOCK_MODE on the host, which locks each new file "
    "itself (PO 2026-10-02, CR-160-BRC10)."
)


def _check_no_default_retention(resolved: Any) -> list[Any]:
    """Refuse a bucket that would lock every file by default (`CR-160-BRC10`).

    Asked only of a backend that can answer (`default_retention`); the
    filesystem backend has no buckets and is skipped, which is correct rather
    than a blind spot — there is no such rule to have.
    """
    ask = getattr(resolved, "default_retention", None)
    if ask is None:
        return []
    try:
        rule = ask()
    except Exception as exc:  # noqa: BLE001 — "could not ask" is a warning, never a pass
        return [
            CheckWarning(
                "the document-storage boot check could not ask the bucket whether it "
                f"has a default retention rule: {type(exc).__name__}: {exc}",
                hint=(
                    "Grant s3:GetBucketObjectLockConfiguration to this host's identity, "
                    "or confirm by hand that the bucket has NO default retention rule. "
                    + _RETENTION_HINT
                ),
                id=WARNING_ID,
            )
        ]
    if not rule:
        return []
    return [
        Error(
            "this deployment's bucket has a DEFAULT retention rule "
            f"({rule}), so every file written to it — every bill, every upload, every "
            "export — would be locked for that whole period, and in COMPLIANCE mode "
            "nobody, not even the account root, could delete one before it ends. The "
            "Product Owner ruled that no file is locked for now (2026-10-02).",
            hint=_RETENTION_HINT,
            id=RETENTION_ERROR_ID,
        )
    ]


# ═══════════════════════════════════════════════════════════════════════════
# DEF-TEN-9190 — CAN THIS PROCESS STORE AN EXPORT? ASKED WHEN IT STARTS.
# ═══════════════════════════════════════════════════════════════════════════
#
# The system check above runs on `manage.py` commands. **A celery worker and
# gunicorn run none**, so on 2026-10-02 a worker that could not reach S3
# accepted an export, built 73 rows and then sat in `running` with nothing in
# its log. Since 2.455.0 the worker is the process that WRITES every export to
# S3, so it is the one that must say, at start, where it will write — and
# refuse to start when it has nowhere (hard-won law 3).
#
# Two questions, answered differently on purpose:
#   1. Is export storage CONFIGURED? (no network) — a refusal: the process
#      exits, naming the setting. Under DEBUG it is a warning, as above.
#   2. Can this process REACH it? (one HEAD of the bucket, bounded by the
#      client's own timeouts) — never a refusal, because a slow bucket must
#      not stop a deploy; it is one ERROR line saying exactly that, at start,
#      where the person deploying will read it. Any HTTP answer at all — a 403
#      included, since the app may hold no ListBucket permission — proves the
#      path is open.

EXPORT_STORAGE_ERROR_ID = "smartbillhub.E003"


def _probe_client(store: Any) -> Any:
    """The client the start-up HEAD uses: the real one's endpoint and region, SHORT timeouts.

    The upload client may wait about four minutes on a silent path (see
    `DOCUMENT_STORAGE_READ_TIMEOUT`); a worker's start must not. One attempt,
    3 s to connect, 5 s to answer. A client injected for tests is used as is.
    """
    from apps.tenancy import document_storage, export_storage

    if export_storage._client_factory is not None:
        return store.client  # injected (tests): used as given
    return document_storage.probe_client(store.client)


def export_storage_line(*, probe_network: bool = True) -> tuple[bool, str]:
    """(configured, one log line) for THIS process's export storage. Never raises."""
    from apps.tenancy import document_storage, export_storage

    try:
        store = export_storage.backend()
    except document_storage.StorageNotConfigured as refusal:
        return False, f"export storage NOT CONFIGURED in this process: {refusal}"
    except Exception as exc:  # noqa: BLE001 — the check, not the store
        return False, f"export storage could not be resolved: {type(exc).__name__}: {exc}"
    where = store.describe()
    if not probe_network:
        return True, f"export storage: {where} (not probed)"
    try:
        _probe_client(store).head_bucket(Bucket=store.bucket)
        reach = "reachable"
    except Exception as exc:  # noqa: BLE001 — classify, never raise
        response = getattr(exc, "response", None)
        code = ""
        if isinstance(response, dict):
            code = str((response.get("Error") or {}).get("Code") or "")
        if code in {"404", "NoSuchBucket"}:
            reach = (
                "BUCKET NOT FOUND - S3 answered, and has no bucket of that name "
                "here: check DOCUMENT_STORAGE_BUCKET and DOCUMENT_STORAGE_REGION"
            )
        elif code:
            reach = f"reachable (the bucket answered {code})"
        else:
            reach = f"UNREACHABLE from this process - {type(exc).__name__}: {exc}"
    return True, f"export storage: {where} - {reach}"


def enforce_export_storage_at_startup(
    *, process: str, stream: Any = None, probe_network: bool = True
) -> None:
    """Print where exports go; refuse to start (SystemExit 1) when nowhere, outside DEBUG."""
    import logging

    log = logging.getLogger("smartbillhub.exports")
    # The log line is what a deployment reads; `stream` is for a caller (a test)
    # that wants the same sentence handed to it as well.
    out = stream
    ok, line = export_storage_line(probe_network=probe_network)
    try:
        from core import diagnostics

        version = f" (build {diagnostics.release()})"
    except Exception:  # noqa: BLE001 — a missing version never blocks a start
        version = ""
    message = f"{process}{version}: {line}"
    if out is not None:
        print(message, file=out, flush=True)
    if ok:
        loud = "UNREACHABLE" in line or "BUCKET NOT FOUND" in line
        (log.error if loud else log.info)(message)
        return
    if getattr(settings, "DEBUG", False):
        log.warning("%s - starting anyway because DEBUG is on", message)
        return
    log.error(message)
    refusal = (
        f"{process} REFUSES TO START ({EXPORT_STORAGE_ERROR_ID}): it would accept export "
        "jobs and have nowhere to store the file. Set DOCUMENT_STORAGE_BUCKET and "
        "DOCUMENT_STORAGE_REGION (and credentials, or a task role) on THIS container - "
        "web, celery and celery-billing all need them. Editing .env.example changes "
        "nothing on a host that already has a .env (hard-won law 4)."
    )
    if out is not None:
        print(refusal, file=out, flush=True)
    log.critical(refusal)
    raise SystemExit(1)

# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-019 (EP-TEN-03 — tenant sample data: seed it, tag it, report
#           it, remove it)   Screens: S8 (Settings → Company profile → Sample
#           data, BR-TEN-069)
# Change:   CR-039 wave B tasks 7 + 10 + "a stable error-code vocabulary" —
#           PO 2026-08-26, verbatim: *"we need to look at what of 1 job fails
#           and does not load the data - them what we do with rest of the jobs
#           - we should continue and should not lose entire setup"* and *"Can
#           we write all failed job detialsin audit log of that tenant along
#           wt=ith error code so that we can trace it back later?"*
# Rules:    BR-TEN-060 (an unwired seam is a NAMED line, not a skip) ·
#           BR-AUD-002 (the audit log is APPEND-ONLY) · BR-AUD-006 (PII enters
#           masked only) · CLAUDE.md rule 7
# Tests:    06-backend/tests/test_cr039_sample_block_reporting.py
# ───────────────────────────────────────────────────────
"""The sample-data failure VOCABULARY: a stable code beside every sentence.

WHY THIS FILE EXISTS
--------------------
Before CR-039 a failing sample block carried exactly two reason codes —
`seam_not_wired` and `exception` — and everything else it knew was PROSE in
`sample_data_runs.detail`. Prose is the right thing to show a person and the
wrong thing to count: *"how many tenants failed for THIS reason"* is not a
question a paragraph can answer, and the Product Owner's request is explicitly
about tracing failures back later, across tenants.

So every non-seeded block now carries BOTH:

  * the SENTENCE — the seeder's own words, for the operator, in
    `sample_data_runs.blocks[].detail`. Unchanged, and still rendered verbatim;
  * the CODE — one of the constants below, for counting.

WHY THE CODES ARE COARSE, AND WHY THAT IS DELIBERATE
-----------------------------------------------------
It would be easy to mine finer codes out of the seeders' sentences with a
handful of regexes — *"no bill template"*, *"no 2200-series liability
account"*. That would be a vocabulary this repo never agreed to, decided by
string matching, and it would go silently wrong the first time a seeder
reworded its own message. So the codes here are derived ONLY from facts the
orchestrator actually holds: whether the seam existed, and what TYPE the
exception was.

The finer codes have a home that is not a regex: `BlockCannotRun(…, code=…)`.
A seeder that wants to say WHICH precondition it lacked declares it at the
raise site, where the fact is known. `classify()` honours a declared code when
it is registered here and falls back to the type-derived one when it is not —
so a new code is a two-line diff (the raise site + a row in `CATALOGUE`) and
never a parser.

⚠ **THE CATALOGUE SENTENCE IS NOT THE OPERATOR SENTENCE, AND THE DIFFERENCE IS
THE WHOLE POINT OF `audit_safe_sentence()`.**
`audit_log` is APPEND-ONLY (BR-AUD-002, CLAUDE.md hard rule 4). A row written
there can never be deleted — not for an erasure request, not for a mistake. And
the seeders' own sentences interpolate live values: `payments` embeds
`invoice_no` and the raw `str(exc)` of whatever refused the payment,
`metering` embeds validation-row messages, `customers` embeds an account's
BALANCE. On the sample estate those are fixture rows, but the same code path
runs against a real tenant's configuration, and a sentence is not a promise
about what it will contain tomorrow.

So the audit row carries the CODE plus the fixed catalogue sentence for that
code — text that lives in this file, contains no interpolation of any kind, and
therefore cannot carry customer data into a record that has no delete. The
seeder's own sentence stays in `sample_data_runs`, which is an ordinary
tenant-scoped table that removal deletes.
"""

from typing import Any

#: The owning module publishes no seeder for this block at all. Identical on
#: every tenant of a given build — a platform gap, never a tenant's data.
CODE_SEAM_MISSING = "SD-SEAM-MISSING"

#: `core.sample_fixture.BlockCannotRun` with no declared code: the seeder
#: checked a precondition, found it absent, and refused rather than writing a
#: half-block or reporting a dishonest zero.
CODE_PRECONDITION = "SD-PRECONDITION"

#: A database constraint refused a row (IntegrityError and subclasses).
CODE_DB_INTEGRITY = "SD-DB-INTEGRITY"

#: Any other database-layer error — a deferred FK at commit, a lock timeout.
CODE_DB_ERROR = "SD-DB-ERROR"

#: A service refused one of the block's writes under a business rule
#: (core.errors.ApiError / BizError, DRF and Django validation, permissions).
CODE_REFUSED = "SD-REFUSED"

#: The block reached a stub. In this repo that means an OQ-### the Prime
#: Directive forbids a coder from answering — the fix is a ruling, not a retry.
CODE_NOT_BUILT = "SD-NOT-BUILT"

#: Everything else. Named rather than hidden: a code that says "we have no code
#: for this" is countable, and a rising count is the signal to add one.
CODE_UNEXPECTED = "SD-UNEXPECTED"

#: Code → the sentence written to the APPEND-ONLY audit log. Fixed text, no
#: interpolation, no tenant value, no customer value — see the file docstring.
CATALOGUE: dict[str, str] = {
    CODE_SEAM_MISSING: (
        "The owning module publishes no seeder for this block, so nothing could "
        "write it. This is a platform gap and is the same on every tenant of this "
        "build."
    ),
    CODE_PRECONDITION: (
        "The block refused because something it needs was not in place, and wrote "
        "nothing rather than writing a partial set. The operator sentence on "
        "Settings > Company profile > Sample data names what was missing."
    ),
    CODE_DB_INTEGRITY: (
        "A database constraint refused a row this block wrote; the block's own "
        "transaction was rolled back and every other block was unaffected."
    ),
    CODE_DB_ERROR: (
        "The database refused this block's transaction. The block's own "
        "transaction was rolled back and every other block was unaffected."
    ),
    CODE_REFUSED: (
        "A service refused one of this block's writes under a business rule. The "
        "refusal is the product working; the sample set simply cannot be planted "
        "until the tenant satisfies it."
    ),
    CODE_NOT_BUILT: (
        "The block reached a part of the product that is not built yet and that "
        "names an open question in its own code. Nothing here can be retried into "
        "success until that question is ruled on."
    ),
    CODE_UNEXPECTED: (
        "The block raised an error this vocabulary has no code for. The operator "
        "sentence on Settings > Company profile > Sample data carries the detail; "
        "a rising count of this code is the signal to add a code for it."
    ),
}

#: The fallback for a code this file does not hold. It exists because
#: `audit_safe_sentence` must ALWAYS return safe text: a KeyError inside the
#: audit write would take out the trail row and, before CR-039's own guard,
#: the run with it. Fixed text like every other sentence here.
#:
#: ⚠ Reaching this is a BUG, not a state — every writer classifies through
#: `classify()`, which only ever returns a catalogued code. If it appears in a
#: trail, something wrote a `sample_data_runs` row by another route.
_UNKNOWN_SENTENCE = (
    "This block did not load and reported a reason the vocabulary does not "
    "recognise. See Settings > Company profile > Sample data."
)


def audit_safe_sentence(code: str) -> str:
    """The fixed sentence for `code` — safe for an append-only record.

    ⚠ It takes ONLY the code. That is not a stylistic choice: a function that
    accepted the seeder's own message could be handed one containing an account
    number, a balance or a read value, and `audit_log` has no delete. The
    signature is the guarantee.
    """
    return CATALOGUE.get(code, _UNKNOWN_SENTENCE)


def declared_code(exc: BaseException) -> str | None:
    """A code the SEEDER declared at its raise site, if it registered one.

    `core.sample_fixture.BlockCannotRun` accepts `code=` so a block that knows
    exactly which precondition it lacked can say so where the fact is known.
    An unregistered code is ignored — a code that is not in `CATALOGUE` has no
    audit-safe sentence, and inventing one from the exception message is the
    thing this file exists to avoid.

    ⚠ ONLY `BlockCannotRun` is asked. `core.errors.ApiError` also carries a
    `.code`, and it is a B12 envelope code from a different catalogue entirely
    (`BIZ_…`, `AUTH_…`); reading it here would mix two vocabularies in one
    column the moment one of them added a string the other happened to hold.
    """
    from core import sample_fixture as fixture

    if not isinstance(exc, fixture.BlockCannotRun):
        return None
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code in CATALOGUE:
        return code
    return None


def classify(exc: BaseException) -> str:
    """The stable code for `exc` — from the seeder's declaration or its TYPE.

    Never from its MESSAGE. Deriving a code by matching words in a sentence
    would make the vocabulary depend on prose nobody agreed to keep stable, and
    would drift the first time a seeder reworded itself.
    """
    # Imported lazily so this module stays importable without Django loaded —
    # the vocabulary is also read by the audit-side tests.
    from django.core.exceptions import PermissionDenied, ValidationError
    from django.db import Error as DatabaseError
    from django.db import IntegrityError

    from core import errors as core_errors
    from core import sample_fixture as fixture

    declared = declared_code(exc)
    if declared is not None:
        return declared
    if isinstance(exc, fixture.BlockCannotRun):
        return CODE_PRECONDITION
    if isinstance(exc, NotImplementedError):
        return CODE_NOT_BUILT
    if isinstance(exc, IntegrityError):
        return CODE_DB_INTEGRITY
    if isinstance(exc, DatabaseError):
        return CODE_DB_ERROR
    if isinstance(exc, (core_errors.ApiError, ValidationError, PermissionDenied)):
        return CODE_REFUSED
    return CODE_UNEXPECTED


def is_known(code: Any) -> bool:
    """True when `code` is a member of this vocabulary."""
    return isinstance(code, str) and code in CATALOGUE


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-TEN-019@c3b7d18 (EP-TEN-03 — the sample-data orchestrator and its honest report) + CR-039 wave B tasks 7/10 and the error-code vocabulary (12-governance/11-change-requests.md)
# generated: 2026-08-26 by story-coder (CR-039 wave B lane)
# checklist: A✔ B=deferred(this file draws nothing — the codes reach a person through SettingsSampleData.tsx, shipped in the same lane) C✔ D=deferred(no endpoint of its own — the codes are served on GET /settings/sample-data) E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report
# exceptions: the codes are DELIBERATELY coarse — every finer code available today would have to be mined out of a seeder's prose, which is a vocabulary nobody ratified decided by regex. `BlockCannotRun(code=…)` is the declared route for a finer code and no seeder uses it yet; adopting it is one line per raise site and is REPORTED rather than done here, because those files are other modules' territory
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2379 — a deployment with no document storage boots happily and
#          reports it eight steps into the first tenant anybody creates.
# Rules:   PO 2026-09-02 ("Yes - please add the check") · NFR-35 · CLAUDE.md
#          hard-won law 3 (defaults fail closed) · law 4 (a template change
#          never reaches a host that already has a .env) · law 7 (prove a new
#          guard goes RED before trusting it green)
# ───────────────────────────────────────────────────────
"""**THE GUARD THAT WOULD HAVE SAVED A DAY, AND THE PROOF THAT IT BITES.**

The Product Owner's deployment had `DOCUMENT_STORAGE_BUCKET` unset. It booted,
served, accepted a signup, and seeded seven steps before stopping on the step
that issues bills — because that is the first moment anything asks for a
document. Steps 9, 10 and 11 then failed behind it.

Law 7: *"prove a new guard goes RED before trusting it green."* Every case here
drives the check to a verdict rather than asserting it was registered, because a
check that cannot fail is worse than no check — it is trusted.

The four cases are the four things this guard has to get right:

  1. it FIRES, as an **Error**, on the PO's exact configuration;
  2. it is **silent** when the store resolves, so a working deployment is not
     nagged into ignoring it;
  3. it degrades to a **Warning** under `DEBUG`, so a half-finished developer
     `.env` does not block `manage.py shell` — the failure mode is a serving
     process, not a console;
  4. it never blocks a boot on **its own** bug: a check that raises reports a
     warning about itself rather than taking the deployment down.
"""

from __future__ import annotations

import pytest
from django.core.checks import Error
from django.core.checks import Warning as CheckWarning

from apps.tenancy import document_storage
from core import storage_guard


def test_it_fires_on_the_po_s_own_configuration(settings) -> None:
    """`DOCUMENT_STORAGE_BUCKET` unset, on a deployment — an Error at boot.

    RED FIRST: with `register_check(storage_guard.check_document_storage)`
    removed from `TenancyConfig.ready()`, a deployment in this state passes
    `manage.py check` with *"System check identified no issues"* and says
    nothing until the first bill.
    """
    settings.DEBUG = False
    settings.DOCUMENT_STORAGE_BACKEND = "aws_s3"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = False
    settings.DOCUMENT_STORAGE_BUCKET = ""

    found = storage_guard.check_document_storage()

    assert len(found) == 1, found
    (issue,) = found
    assert isinstance(issue, Error)
    assert issue.id == storage_guard.ERROR_ID
    # The store's OWN sentence, verbatim — not a paraphrase this file invents.
    assert "DOCUMENT_STORAGE_BUCKET is not set" in str(issue.msg)
    # And the two settings a person has to go and set.
    assert "DOCUMENT_STORAGE_BUCKET" in issue.hint
    assert "DOCUMENT_STORAGE_REGION" in issue.hint
    # Law 4, said out loud where the person reading the boot log will see it.
    assert ".env.example" in issue.hint
    # ⚠ THE IRREVERSIBLE THING COMES FIRST (2026-09-02). Object Lock cannot be
    # switched on after a bucket exists, so a bucket created without it must be
    # thrown away. That fact is already in the AWS runbook twice, the deployment
    # architecture once and a comment in `.env.example` — all read at PLANNING
    # time, days before anyone is at a terminal making a bucket. This message
    # fires at the moment they are, which is the only moment it is worth
    # anything. Asserted, not merely written, because a hint nobody checks drifts
    # the first time somebody tidies the sentence.
    #
    # ⚠ AMENDED 2026-10-02 (`CR-160-BRC10`): no file is object-locked now, so the
    # first thing the hint says is the bucket's ONE remaining irreversible-ish
    # trap — a DEFAULT retention rule, which would lock every file written. It
    # read "Object Lock" (create the bucket with it ENABLED) until then.
    assert "default retention" in issue.hint
    assert issue.hint.index("default retention") < issue.hint.index("DOCUMENT_STORAGE_BUCKET"), (
        "the bucket rule must come before the two settings — a person who "
        "reads only the first line must still create the bucket correctly"
    )


def test_it_says_nothing_when_the_store_resolves(settings) -> None:
    """A configured deployment is not nagged. The test settings ARE such a
    deployment (filesystem backend, explicitly allowed), so this asserts the
    ordinary case rather than a contrived one."""
    assert storage_guard.check_document_storage() == []


def test_under_debug_it_warns_rather_than_blocks(settings) -> None:
    """A developer whose `.env` is half finished can still run a console."""
    settings.DEBUG = True
    settings.DOCUMENT_STORAGE_BACKEND = "aws_s3"
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = False
    settings.DOCUMENT_STORAGE_BUCKET = ""

    found = storage_guard.check_document_storage()

    assert len(found) == 1, found
    (issue,) = found
    assert isinstance(issue, CheckWarning)
    assert issue.id == storage_guard.WARNING_ID
    assert "DOCUMENT_STORAGE_BUCKET is not set" in str(issue.msg)


def test_it_never_blocks_a_boot_on_its_own_bug(monkeypatch) -> None:
    """If the CHECK breaks, the deployment still starts and the check says so
    about ITSELF. The store's own refusal still fires at the first document
    either way, so nothing is lost by being cautious here."""

    def exploding_backend() -> None:
        raise RuntimeError("boto3 is not installed")

    monkeypatch.setattr(document_storage, "backend", exploding_backend)

    found = storage_guard.check_document_storage()

    assert len(found) == 1, found
    (issue,) = found
    assert isinstance(issue, CheckWarning)
    assert "could not run" in str(issue.msg)
    assert "boto3 is not installed" in str(issue.msg)


def test_the_check_is_registered_and_runs_untagged() -> None:
    """It has to be REACHED, not merely written (hard-won law 2).

    `manage.py migrate` on the container entrypoint passes no tags, so an
    untagged check runs on every boot path. Asserting the registry directly
    means deleting the `register_check` line turns this red.
    """
    from django.core.checks import registry

    registered = list(registry.registry.get_checks(include_deployment_checks=True))
    assert storage_guard.check_document_storage in registered
    # Untagged: Django stores tags on the function, and an absent/empty set is
    # what makes it run when a caller passes none.
    assert not getattr(storage_guard.check_document_storage, "tags", ())

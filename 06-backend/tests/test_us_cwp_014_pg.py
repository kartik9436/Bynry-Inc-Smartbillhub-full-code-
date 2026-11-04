# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-014 (EP-CWP-04) TC-4 — ⚠ *"A consent row dated in the future
#           → Refused by a constraint. The blueprint shipped one dated nineteen
#           days after its own today and its §26 lists the repair."* · TC-6 —
#           the consent row is scoped to the tenant, RLS FORCE ·
#           US-CWP-013 TC-6 — a draft opened under another utility is not found
# Rules:    03-field-map.md `portal_consent.agreed_on` (*"May never be in the
#           future"*) · BR-CWP-087 (the wording version) · CLAUDE.md hard rule 1
#           · hard-won law 14 (the constraint is PostgreSQL's and a green
#           SQLite run proves NOTHING about it)
# Tests:    this file
# Impacts:  apps/portal/migrations/0003_consent_draft_quick_service.py (the
#           CHECK, as first written) · migrations/0005_consent_not_future_by
#           _the_wall_clock.py (the CHECK as it now stands — DEF-CWP-3709) ·
#           migrations/0004_rls_consent_and_draft.py (the policies)
# ───────────────────────────────────────────────────────
"""US-CWP-014 on PostgreSQL — what SQLite cannot hold.

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
    DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/<db> \\
        pytest tests/test_us_cwp_014_pg.py

⚠ **THE FUTURE-DATE CHECK IS THE WHOLE REASON THIS FILE EXISTS.** `config/
settings/test.py` hardcodes in-memory SQLite (CLAUDE.md law 14), SQLite has no
`now()` a CHECK may call, and the constraint is therefore not created there at
all. A caller writing a consent dated next month would be ACCEPTED on the
default suite, green, on every machine — and refused the first time it reached
a real database. Every case here carries `requires_postgres` and SKIPS rather
than passing vacuously.
"""

from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from apps.portal import applications, models, wording
from core.tenancy import tenant_context
from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import switch_on


def _consent(tenant, **over):
    """Write one consent row — **with the SAVEPOINT on the inside.**

    ⚠ **AND THE CASES THAT USE IT ARE `django_db`, NOT
    `django_db(transaction=True)`.** The transactional form FLUSHES between
    tests, which takes the PLATFORM catalogue with it — the second case then
    failed at setup with `signup.plan_unknown`, which reads like a broken
    fixture and is a truncated `subscription_plans`. The savepoint below is
    what makes the ordinary form work: the refused INSERT rolls back to it and
    the surrounding test transaction survives.

    ⚠ **CLAUDE.md LAW 14, MET IN THIS FILE'S OWN FIXTURE ON THE FIRST RUN.**
    The obvious shape is `with transaction.atomic(): _consent(...)` around the
    call, and on PostgreSQL it does not work: the refused INSERT aborts the
    transaction, and `tenant_context`'s own exit query then raises
    `TransactionManagementError: An error occurred in the current transaction.
    You can't execute queries until the end of the 'atomic' block` — which
    reads like a broken test rather than like the constraint doing its job.
    Two of these cases failed exactly that way before the `atomic()` moved
    INSIDE the tenant context, where it is a SAVEPOINT the caller can roll back
    to. On SQLite none of this would have shown, because SQLite has no aborted-
    transaction state — which is the law's whole point.
    """
    with tenant_context(tenant.id):
        with transaction.atomic():
            return models.PortalConsent.objects.create(
                tenant_id=tenant.id,
                wording_version=wording.PAPERLESS_CURRENT,
                taken_on_screen=wording.SCREEN_NEW_CONNECTION,
                **over,
            )


@requires_postgres
@pytest.mark.django_db
def test_tc4_a_consent_dated_in_the_future_is_refused_by_the_database(pine_hill, sarah):
    """TC-4 — and the refusal comes from the DATABASE, not from Python.

    A Python check is a check one importer forgets. This one cannot be
    forgotten, because there is no code path around it.
    """
    switch_on(pine_hill, sarah)
    tomorrow = timezone.now() + timedelta(days=1)
    with pytest.raises(IntegrityError) as raised:
        _consent(pine_hill, agreed_on=tomorrow)
    # The database's own words, quoted so a reader can recognise them in a log.
    assert "ck_portal_consent_agreed_on_not_future" in str(raised.value)

    # ⚠ AND NINETEEN DAYS OUT — the blueprint's own defect, to the day.
    with pytest.raises(IntegrityError):
        _consent(pine_hill, agreed_on=timezone.now() + timedelta(days=19))

    # The lawful case still writes, so the constraint is a rule and not a wall.
    row = _consent(pine_hill, agreed_on=timezone.now() - timedelta(minutes=1))
    assert row.wording_version == wording.PAPERLESS_CURRENT


@requires_postgres
@pytest.mark.django_db
def test_a_consent_written_later_in_the_same_transaction_is_accepted(pine_hill, sarah):
    """DEF-CWP-3709 — the case the other one could not see.

    ⚠ **THE CONSTRAINT WAS FIRST WRITTEN `agreed_on <= now()`, AND IN
    POSTGRESQL `now()` IS THE TRANSACTION'S START TIME AND NEVER MOVES AGAIN.**
    The real submit numbers the service request and stamps the draft BEFORE it
    writes the consent, so Python's clock is a few milliseconds past that fixed
    instant by the time the row exists — and every honest submit was refused
    with the database's own words:

        new row for relation "portal_consent" violates check constraint
        "ck_portal_consent_agreed_on_not_future"

    **The case above cannot catch it**, and that is the point of this one: it
    writes the consent as the FIRST statement of its savepoint, where
    transaction start and wall clock are the same instant. This case does what
    the screen does — some other work first, the consent after — and it went
    RED on `portal 0003` and GREEN on `portal 0005`.
    """
    switch_on(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        with transaction.atomic():
            # Any other statement, and then a wait longer than the drift the
            # bug turned on. `now()` is frozen from here; the wall clock is not.
            models.PortalConsent.objects.count()
            connection.cursor().execute("SELECT pg_sleep(0.2)")
            row = models.PortalConsent.objects.create(
                tenant_id=pine_hill.id,
                wording_version=wording.PAPERLESS_CURRENT,
                taken_on_screen=wording.SCREEN_NEW_CONNECTION,
                agreed_on=timezone.now(),
            )
    assert row.agreed_on is not None

    # And the rule it exists for still holds in the same transaction shape: a
    # future date is refused whether it is the first statement or the tenth.
    with pytest.raises(IntegrityError) as raised:
        with tenant_context(pine_hill.id):
            with transaction.atomic():
                models.PortalConsent.objects.count()
                models.PortalConsent.objects.create(
                    tenant_id=pine_hill.id,
                    wording_version=wording.PAPERLESS_CURRENT,
                    taken_on_screen=wording.SCREEN_NEW_CONNECTION,
                    agreed_on=timezone.now() + timedelta(days=1),
                )
    assert "ck_portal_consent_agreed_on_not_future" in str(raised.value)


@requires_postgres
@pytest.mark.django_db
def test_a_consent_without_the_version_of_the_words_is_not_a_consent(pine_hill, sarah):
    """`03-field-map.md`, verbatim: *"The version of the words they actually
    saw. A consent without it is not a consent."* An empty string is not a
    version, and the CHECK holds on every engine."""
    switch_on(pine_hill, sarah)
    with pytest.raises(IntegrityError) as raised:
        with tenant_context(pine_hill.id):
            with transaction.atomic():  # the savepoint, for the reason above
                models.PortalConsent.objects.create(
                    tenant_id=pine_hill.id,
                    wording_version="",
                    taken_on_screen=wording.SCREEN_NEW_CONNECTION,
                )
    assert "ck_portal_consent_wording_version_present" in str(raised.value)


@requires_postgres
@pytest.mark.django_db
def test_tc6_no_context_sees_no_consent_and_no_draft(pine_hill, sarah, rls):
    switch_on(pine_hill, sarah)
    assert_denied_without_context(rls, "portal_consent", "portal_application_drafts")


@requires_postgres
@pytest.mark.django_db
def test_tc6_a_pine_hill_consent_is_invisible_under_oak_ridge(
    pine_hill, sarah, oak_ridge, elena, rls
):
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    row = _consent(pine_hill)
    assert_rls_scoped(
        rls,
        "portal_consent",
        owner=pine_hill,
        intruder=oak_ridge,
        owner_ids={str(row.id)},
    )


@requires_postgres
@pytest.mark.django_db
def test_us_cwp_013_tc6_a_draft_started_here_is_not_found_over_there(
    pine_hill, sarah, oak_ridge, rls
):
    """`US-CWP-013` TC-6 — *"A draft started on `/pine-hill` opened under
    `/oak-ridge` → Not found."* It is not found because the ROW is invisible,
    not because a view checked; that is the difference this test measures."""
    switch_on(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        applications.save_draft(pine_hill.id, "a" * 32, {"address_as_given": "31 Palm Ct"})
    assert_write_into_other_tenant_refused(
        rls, "portal_application_drafts", owner=pine_hill, intruder=oak_ridge
    )

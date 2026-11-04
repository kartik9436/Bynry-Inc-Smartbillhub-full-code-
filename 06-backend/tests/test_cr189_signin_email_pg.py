"""Who moves the portal sign-in email, on PostgreSQL — what SQLite cannot hold
(CLAUDE.md law 14).

    pytest tests/test_cr189_signin_email.py tests/test_cr189_signin_email_pg.py \\
        --ds=config.settings.pgtest --reuse-db

The SQLite file runs unchanged under `pgtest` too. This file adds the one case
that is transaction-shaped: a sign-in email clash met AT THE WRITE (the check
before it missed — a customer enrolling the same minute) is caught in a
SAVEPOINT, so the clerk's transaction survives to refuse by name instead of
dying with `InFailedSqlTransaction`.
"""

import pytest
from django.db import connection, transaction

from apps.customers import customer_edit
from apps.customers import models as customers_models
from apps.portal import credentials, email_update
from apps.portal import models as portal_models
from core import errors
from core.tenancy import tenant_context
from tests.isolation_helpers import requires_postgres
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import MARIA_EMAIL, elm_street_account, enrol_maria, switch_on

TAKEN = "someone.else@example.test"


def _maria_and_a_rival(tenant, actor):
    switch_on(tenant, actor)
    elm_street_account(tenant, actor)
    credential = enrol_maria(tenant, actor)
    with tenant_context(tenant.id):
        portal_models.PortalCredential.objects.create(
            tenant_id=tenant.id,
            customer=customers_models.Customer.objects.create(
                tenant_id=tenant.id, display_name="Other, Person", kind="person"
            ),
            email=TAKEN,
            password_hash="x",
        )
    return credential


@requires_postgres
@pytest.mark.django_db
def test_pg_a_clash_at_the_write_is_caught_in_a_savepoint_and_the_transaction_lives(
    pine_hill, sarah, monkeypatch
):
    credential = _maria_and_a_rival(pine_hill, sarah)
    # The pre-check misses (as it would in a race), so the UNIQUE index fires.
    monkeypatch.setattr(credentials, "credential_by_email", lambda tenant_id, email: None)
    with tenant_context(pine_hill.id):
        with transaction.atomic():
            answer = email_update.staff_move_sign_in(
                pine_hill.id,
                customer_id=credential.customer_id,
                email=TAKEN,
                actor_user_id=sarah.id,
            )
            # Without the savepoint this next statement raises
            # InFailedSqlTransaction on PostgreSQL.
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                assert cursor.fetchone() == (1,)
    assert answer == {"result": email_update.STAFF_TAKEN}
    with tenant_context(pine_hill.id):
        credential.refresh_from_db()
    assert credential.email == MARIA_EMAIL


@requires_postgres
@pytest.mark.django_db
def test_pg_the_clerks_save_refuses_by_name_and_keeps_nothing(pine_hill, sarah, monkeypatch):
    credential = _maria_and_a_rival(pine_hill, sarah)
    monkeypatch.setattr(credentials, "credential_by_email", lambda tenant_id, email: None)
    with tenant_context(pine_hill.id):
        before = set(
            customers_models.Contact.objects.filter(is_primary=True).values_list(
                "email", flat=True
            )
        )
        with pytest.raises(errors.ValidationError) as caught:
            customer_edit.update_customer(
                sarah, str(credential.customer_id), {"email": TAKEN, "portal_sign_in": True}
            )
        after = set(
            customers_models.Contact.objects.filter(is_primary=True).values_list(
                "email", flat=True
            )
        )
        credential.refresh_from_db()
    assert caught.value.message_key == "customers.customer.edit.signInTaken"
    assert after == before, "the contact write went back with the refusal"
    assert credential.email == MARIA_EMAIL


@requires_postgres
@pytest.mark.django_db
def test_pg_a_ticked_save_commits_the_login_the_notice_and_the_reset(
    pine_hill, sarah, settings
):
    settings.PUBLIC_APP_ORIGIN = "https://app.example.test"
    switch_on(pine_hill, sarah)
    elm_street_account(pine_hill, sarah)
    credential = enrol_maria(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        result = customer_edit.update_customer(
            sarah,
            str(credential.customer_id),
            {"email": "maria.new@example.test", "portal_sign_in": True},
        )
        credential.refresh_from_db()
        reset = portal_models.PortalOneTimeCode.objects.filter(
            purpose=portal_models.PURPOSE_RESET, portal_credential_id=credential.pk
        ).count()
    assert result["portal_sign_in_moved"] is True
    assert credential.email == "maria.new@example.test"
    assert reset == 1

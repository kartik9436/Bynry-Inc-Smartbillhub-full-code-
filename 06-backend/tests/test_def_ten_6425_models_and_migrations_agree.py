"""**The models and the migrations agree, and the database accepts every
document kind the model declares** (`DEF-TEN-6425`, `DEF-TEN-6107`).

WHAT WENT WRONG
───────────────
`tenancy/0045` wrote its list of document kinds out by hand and spelled three
of them wrong — `plan_instalment_due`, `plan_instalment_missed`, `plan_voided`
where the model says `payment_plan_instalment_due`, `payment_plan_instalment_missed`
and `payment_plan_voided`. So from `0045` onwards **PostgreSQL refused to store
a payment-plan reminder, a missed-instalment letter or a voided-plan notice**,
while every test here passed: the default suite runs on SQLite, which does not
enforce this CHECK (CLAUDE.md hard-won law 14's family).

The only signal was `makemigrations` offering to drop and recreate the
constraint. Two lanes saw it (`tenancy/0046` stripped it out and cited an id
that was never issued; `DEF-TEN-6107` filed it) and nothing ran the check.

WHAT THIS FILE DOES ABOUT IT
────────────────────────────
1. **`makemigrations --check`, on every run of the ordinary suite.** It fails
   on ANY app whose models moved without a migration, not only tenancy, which
   is the prevention both defect rows ask for. It runs on SQLite, so it is in
   the suite every lane runs.
2. **On PostgreSQL, the live constraint is read back** and compared with the
   model's own tuple. It walks `DOCUMENT_KINDS` rather than re-typing it: a
   third hand-written copy of the list is how the typo got in.

WHAT WOULD MAKE IT PASS WRONGLY (law 7, habit 2)
────────────────────────────────────────────────
* Case 1 passes if `makemigrations` cannot see an app — it can see every app in
  `INSTALLED_APPS`, which is every app with models.
* Case 2 passes wrongly if the regex found no literals at all (an empty set is
  equal to nothing it is compared with, but `DOCUMENT_KINDS` is never empty),
  and it SKIPS — says so, never passes — on SQLite.

PROVED RED FIRST, IN THE HARNESS THAT RUNS IT: both cases failed on the tip
`ecbb7ba92` before `tenancy/0047` existed (quoted in the commit message).
"""

import io
import re

import pytest
from django.core.management import call_command
from django.db import connection

from apps.tenancy.document_models import DOCUMENT_KINDS
from tests.isolation_helpers import requires_postgres


@pytest.mark.django_db
def test_every_model_change_has_its_migration():
    out = io.StringIO()
    try:
        call_command("makemigrations", "--check", "--dry-run", stdout=out, stderr=out)
    except SystemExit as exc:  # --check exits 1 when a migration is owed
        pytest.fail(
            f"makemigrations --check exited {exc.code}: a model changed without its "
            f"migration.\n{out.getvalue()}"
        )


@requires_postgres
@pytest.mark.django_db
def test_the_database_accepts_every_document_kind_the_model_declares():
    with connection.cursor() as cur:
        cur.execute(
            "select pg_get_constraintdef(oid) from pg_constraint "
            "where conname = 'ck_stored_documents_kind'"
        )
        (definition,) = cur.fetchone()
    in_the_database = set(re.findall(r"'([a-z_]+)'::text", definition))
    in_the_model = set(DOCUMENT_KINDS)
    assert in_the_database, f"no kinds read out of {definition!r}"
    assert sorted(in_the_model - in_the_database) == [], "the database refuses these kinds"
    assert sorted(in_the_database - in_the_model) == [], "the database allows kinds the model dropped"

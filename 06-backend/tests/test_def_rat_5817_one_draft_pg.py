# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-5817 — a discount could be edited exactly ONCE. The second
#          *Save new version* hit `uq_discount_versions_one_draft` as a raw 500,
#          and the draft blocking it was visible nowhere in the product.
# Rules:   BR-RAT-031 (one draft at a time — the partial-unique shape taken from
#          `tariff_versions`) · BR-RAT-037 (append-only versions) ·
#          DEF-RAT-6447 (the same index on the TARIFF, and the fix that worked:
#          see it, discard it) · CLAUDE.md hard rule 4 · hard-won law 14
# Fix in:  06-backend/apps/rating/discount_services.py
#          06-backend/apps/rating/api.py
# ───────────────────────────────────────────────────────
"""**A second edit is refused in words, and the draft can be seen and withdrawn.**

════════════════════════════════════════════════════════════════════════════
WHY PostgreSQL-ONLY, AND WHY THE RACE CASE IS HERE AND NOT IN THE MAIN SUITE
════════════════════════════════════════════════════════════════════════════
Two different things need a real database, and the second is the one CLAUDE.md
hard-won law 14 is written about.

  1. **The partial unique index itself.** `uq_discount_versions_one_draft` is
     `UNIQUE (discount_id) WHERE status = 'draft'`.

  2. **The aborted-transaction state.** `create_discount_version` now catches
     that index inside a SAVEPOINT — a nested `transaction.atomic()` — and
     converts it into a refusal. On PostgreSQL the failed INSERT poisons the
     whole transaction, so WITHOUT the savepoint the refusal could not be
     raised cleanly and the audit write after it would die on
     `InFailedSqlTransaction`. **SQLite has no such state**, so the version
     without the savepoint passes the entire default suite, green, on every
     machine — which is exactly the trap law 14 records two lanes falling into
     in one week.

════════════════════════════════════════════════════════════════════════════
PROVED RED FIRST, IN THE HARNESS THAT RUNS IT (hard-won law 7)
════════════════════════════════════════════════════════════════════════════
Run at the pristine tip `ca3050616` — this file over the tip's source, through
`pytest` against real PostgreSQL. **All six failed**, in two distinct ways,
and both are the defect rather than a missing import:

    the second edit …            IntegrityError: duplicate key value violates
    a half-built first version…  unique constraint
    the index itself …           "uq_discount_versions_one_draft"
        (the raw 500 a clerk met as "Something went wrong on our side.")

    the blocking draft is served    AttributeError: module
                                    'apps.rating.discount_services' has no
                                    attribute 'discount_version_chain'
    discarding … reopens the door   AttributeError: … no attribute
    an issued version is never …    'discard_discount_version_draft'
        (there was no way to see a draft and no way to remove one)

════════════════════════════════════════════════════════════════════════════
THE RACE CASE IS PROVED BY REMOVING THE PRE-CHECK, WHICH IS THE ONLY WAY
════════════════════════════════════════════════════════════════════════════
The service asks *does a draft already exist?* before inserting, and that
branch answers the reported defect and every single-clerk case. The savepoint
exists for the OTHER path — two requests that both read *no draft* and both
insert — and that path is unreachable while the pre-check works.

So `test_the_index_itself_refuses_in_words_when_the_pre_check_misses` blinds
the pre-check for one call. **Without that, the savepoint would be a guard
proved by nothing** (law 7: a check whose failure mode you cannot describe is
a check you do not understand), and the next lane to "simplify" the nested
`atomic()` away would take the whole suite green with them.
"""

from datetime import date

import pytest

from apps.rating import discount_services
from apps.rating import discounts as discount_models
from core import errors

from tests.isolation_helpers import requires_postgres
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared W1 fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]


def _a_discount(env, code="EDITME", live=True):
    """A discount whose first version is IN FORCE, which is the state the
    reported defect was met in — the walk edited `SENIOR`, an active programme.

    ⚠ **`live=True` IS NOT FIXTURE DECORATION, AND GETTING IT WRONG IS HOW THE
    FIRST DRAFT OF THIS FILE FAILED.** `create_discount` files V1 as a DRAFT,
    so a discount straight out of the door already holds the one draft the
    index allows — and *Save new version* on it is refused, correctly, by the
    same rule. That is the product working, not the defect: `BR-RAT-031` is
    *one draft at a time*, and a half-built V1 is a draft like any other.
    The defect is what happens to a discount whose versions are LIVE, which is
    every discount a utility is actually running.

    The status is set directly rather than walked through submit → approve →
    activate: this file is about the draft index, and three lifecycle acts in a
    fixture would make a failure here ambiguous between the two.
    """
    row = discount_services.create_discount(
        env.admin,
        {
            "code": code,
            "name": "Senior programme",
            "discount_type": "percentage",
            "value": "15",
            "applies_to": "whole_bill",
            "effective_from": date(2026, 10, 1),
        },
    )
    if live:
        discount_models.DiscountVersion.objects.filter(discount_id=row["id"]).update(
            status=discount_models.VERSION_ACTIVE
        )
    return row


def test_a_half_built_first_version_is_itself_the_one_draft(env):
    """The boundary the fixture above exists to state, asserted rather than
    assumed: a discount whose V1 has never been filed cannot draft a V2, and
    the refusal is the same sentence. `BR-RAT-031` counts DRAFTS, not
    lifecycles."""
    with tenant_ctx(env.tenant):
        row = _a_discount(env, code="STILLDRAFT", live=False)
        with pytest.raises(errors.ApiError) as caught:
            _new_version(env, row["id"], "16")
        assert caught.value.message_key == "rating.discounts.draft_already_open"
        assert caught.value.params == {"version_no": 1}


def _new_version(env, discount_id, value, reason="raised after the rate case"):
    return discount_services.create_discount_version(
        env.admin,
        discount_id,
        {
            "discount_type": "percentage",
            "value": value,
            "applies_to": "whole_bill",
            "effective_from": date(2026, 11, 1),
            "change_reason": reason,
        },
    )


def test_the_second_edit_is_refused_with_a_sentence_and_not_a_500(env):
    """The reported symptom, exactly as the walk met it: edit once, 201; edit
    again, and before this fix `IntegrityError: duplicate key value violates
    unique constraint "uq_discount_versions_one_draft"` → HTTP 500 →
    *"Something went wrong on our side. Nothing was saved."*"""
    with tenant_ctx(env.tenant):
        row = _a_discount(env)
        first = _new_version(env, row["id"], "16")
        assert first["version_no"] == 2 and first["status"] == "draft"

        with pytest.raises(errors.ApiError) as caught:
            _new_version(env, row["id"], "17")
        refusal = caught.value
        assert refusal.code == errors.BIZ_STATE
        assert refusal.message_key == "rating.discounts.draft_already_open"
        # It names WHICH draft, so the sentence can point the clerk at a row.
        assert refusal.params == {"version_no": 2}
        # And nothing was written by the refused call.
        assert (
            discount_models.DiscountVersion.objects.filter(discount_id=row["id"]).count() == 2
        )


def test_the_index_itself_refuses_in_words_when_the_pre_check_misses(env, monkeypatch):
    """THE SAVEPOINT, proved by making the race real.

    The pre-check is blinded for one call, so the INSERT reaches the index —
    which is what two simultaneous clerks would do. The assertion is in two
    halves and the second is the one that needs PostgreSQL: the refusal is a
    sentence, AND **the connection is still usable afterwards**, which it would
    not be if the failed INSERT had aborted the outer transaction.
    """
    with tenant_ctx(env.tenant):
        row = _a_discount(env, code="RACEME")
        _new_version(env, row["id"], "16")

        real = discount_models.DiscountVersion.objects
        seen = {"n": 0}

        class _Blind:
            """Answers *no draft* to the pre-check, and is the real manager for
            everything else — including the `create()` that must then reach the
            index. A stub that intercepted more than one call would be proving
            something about the stub."""

            def filter(self, *args, **kwargs):
                if kwargs.get("status") == discount_models.VERSION_DRAFT:
                    seen["n"] += 1
                    return real.filter(pk=None)
                return real.filter(*args, **kwargs)

            def __getattr__(self, name):
                return getattr(real, name)

        monkeypatch.setattr(
            discount_models.DiscountVersion, "objects", _Blind(), raising=False
        )
        try:
            with pytest.raises(errors.ApiError) as caught:
                _new_version(env, row["id"], "17")
        finally:
            monkeypatch.undo()

        assert seen["n"] >= 1, "the pre-check was never blinded; this proves nothing"
        assert caught.value.message_key == "rating.discounts.draft_already_open"
        # The transaction survived the constraint violation — the savepoint's
        # entire job. On the version without it this line raises
        # `InFailedSqlTransaction`.
        assert discount_models.DiscountVersion.objects.filter(discount_id=row["id"]).count() == 2


def test_the_blocking_draft_is_served_so_a_clerk_can_see_it(env):
    """Half the fix. A refusal saying *finish it or discard it* names an act
    nobody can perform while the draft is invisible — DIS-02's Audit tab said
    *"no endpoint serves those versions yet"* and the header read `V1`."""
    with tenant_ctx(env.tenant):
        row = _a_discount(env, code="SEEME")
        _new_version(env, row["id"], "16")
        discount = discount_models.Discount.objects.get(pk=row["id"])
        chain = discount_services.discount_version_chain(discount)
        assert [(item["version_no"], item["status"]) for item in chain] == [
            (2, "draft"),
            (1, "active"),
        ], "newest first, and the draft is in it"
        assert chain[0]["change_reason"] == "raised after the rate case"


def test_discarding_the_draft_reopens_the_edit_door(env):
    """The other half, and the end-to-end shape of the defect: stuck, unstuck."""
    with tenant_ctx(env.tenant):
        row = _a_discount(env, code="UNSTICK")
        draft = _new_version(env, row["id"], "16")

        discount_services.discard_discount_version_draft(env.admin, draft["id"])
        assert (
            discount_models.DiscountVersion.objects.filter(discount_id=row["id"]).count() == 1
        )

        # The door is open again, and the number is REUSED rather than skipped.
        again = _new_version(env, row["id"], "18", reason="second attempt at the rate case")
        assert again["version_no"] == 2


def test_an_issued_version_is_never_discarded(env):
    """Hard rule 4 — the discard is a DRAFT door and the status is the guard.
    A discard that reached an active version would delete a priced state bills
    still resolve to."""
    with tenant_ctx(env.tenant):
        row = _a_discount(env, code="KEEPME")
        live = discount_models.DiscountVersion.objects.get(discount_id=row["id"], version_no=1)
        assert live.status == discount_models.VERSION_ACTIVE

        with pytest.raises(errors.ApiError) as caught:
            discount_services.discard_discount_version_draft(env.admin, live.id)
        assert caught.value.message_key == "rating.discounts.discard_not_a_draft"
        assert discount_models.DiscountVersion.objects.filter(pk=live.id).exists()

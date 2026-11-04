# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-019/021/022 (EP-CUS-07 account onboarding)
#           Screens: S81 (Accounts → Imports tab — the `↺` row action)
# Change:   CR-030 W1 task 1.7 — "Rollback: refuse when any account in the run
#           has been billed"
# Rules:    BR-MET-090 (the rollback point, stored never recomputed) ·
#           BR-CUS-030 (closing an account is a flow) · BR-CUS-049 (opening
#           balances post as balanced immutable JEs) · CLAUDE.md rule 4
#           (financial immutability) · rule 5 (only the posting service writes
#           journal lines) · rule 7 (audit)
# Golden:   GT-16 ❄️ FROZEN — A-12103's 84.20 / 62.10 / 0.00 / 121.00 = 267.30
# Tests:    this file
# Impacts:  apps/metering/import_runs.py (the accounts rollback branch) ·
#           apps/customers/services.py (`rollback_from_import`)
# ───────────────────────────────────────────────────────
"""CR-030 W1 — the accounts rollback branch, and the ledger half it REFUSES.

RED-FIRST PROOF (r11 step 2d) — quoted from the run against the tree as it
stood before this lane touched it, when `rollback()` had a branch for the
assets targets and NOTHING for `accounts`, so every accounts run fell through
to the premises/units path:

    FAILED tests/test_cr030_w1_accounts_rollback.py::
        test_a_clean_accounts_run_reverses_every_account_it_created
        - assert 0 == 2
    FAILED ... ::test_a_BILLED_account_is_kept_and_says_why_without_an_id
        - assert 0 == 1
    FAILED ... ::test_an_account_that_is_gone_is_counted_separately
        - assert 0 == 1
    FAILED ... ::test_a_run_that_posted_OPENING_BOOKS_refuses_and_keeps_its_point
        - DID NOT RAISE <class 'core.errors.BizError'>

The first three are the silent no-op: `_key_of` builds a
`f"{premises_ref}|{label}"` key for any target that is neither premises nor
assets, an accounts row carries NEITHER field, so the key is None, the loop
`continue`d on every row — and the run still marked its rollback point `used`,
set `status = "rolled_back"`, wrote `rolled_back: 0` and emitted
`import_run.rolled_back`. **A success that reversed nothing and spent the one
rollback point the run had.**

**And the case that PASSED in that run is the worst part of the defect:**
`test_the_rollback_point_is_spent_exactly_once` was GREEN against the broken
tree — the point really was marked `used` and the run really was marked
`rolled_back`, on a rollback that had reversed nothing at all.

The fourth failure is the ledger half, and it is a REFUSAL rather than code: see
`test_a_run_that_posted_OPENING_BOOKS_refuses_and_keeps_its_point`.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from apps.customers import models as customers_models
from apps.customers import seams as customers_seams
from apps.ledger import models as ledger_models
from apps.metering import import_runs, models as metering_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)
from tests.test_cr030_w1_accounts_import import (  # noqa: E402 — the W1 harness
    CUTOVER,
    MAPPING,
    _csv_for,
    _run,
    _two_units,
)

pytestmark = pytest.mark.django_db

#: The same two rows as the W1 import suite with **every bucket column blank**.
#: US-CUS-021 TC-5's shape: balance 0.00, no bucket rows, NO opening JE — so a
#: rollback of this run touches no books at all, which is the only case the
#: signed rules answer today (see the OQ-352 case at the bottom of this file).
NO_OPENING_CSV = (
    "UNIT_REF,ACCT,NAME,CUST_ID,TYPE,OPENED,CURRENT,31-60,61-90,90+,DEPOSIT,DEPOSIT_DATE\n"
    '{u1},A-12103,"Harmon, Luis",CUST-118,residential,2024-02-12,,,,,,\n'
    '{u2},A-12140,"Alvarez, Rosa",CUST-119,residential,2025-06-01,,,,,,\n'
)


def _unbilled_run(actor, tenant):
    """Two accounts loaded from a file carrying no opening position at all."""
    units = _two_units(actor, tenant)
    content = NO_OPENING_CSV.format(u1=units[0]["unit_no"], u2=units[1]["unit_no"])
    run_id = _run(actor, content, options={"cutover_on": CUTOVER})
    receipt = import_runs.load(actor, run_id, {"write_mode": "insert", "approved": True})
    assert receipt["counts"]["created"] == 2
    assert receipt["counts"]["with_opening_balance"] == 0
    return run_id


def _account(tenant, account_no):
    return customers_models.Account.objects.get(tenant_id=tenant.id, account_no=account_no)


def _point(run_id):
    return metering_models.RollbackPoint.objects.get(run_id=run_id)


def _row_for(run_id, account_id):
    return metering_models.ImportRunRow.objects.get(
        run_id=run_id, created_record_id=str(account_id)
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · a clean account REVERSES
# ══════════════════════════════════════════════════════════════════════════


def test_a_clean_accounts_run_reverses_every_account_it_created(brazos, marcus):
    """The defect, inverted. Every account this run created is CLOSED as of the
    tenant's today and counted on the receipt.

    Closed, never deleted (BR-CUS-030 + hard rule 4): the row still exists, its
    creation is still on the audit trail, and a corrected re-import can address
    the unit again.
    """
    with tenant_ctx(brazos):
        run_id = _unbilled_run(marcus, brazos)
        actor = staff_actor(brazos, "system_admin", "rb-accounts@brazos.test")

        result = import_runs.rollback(actor, run_id)

        assert result["status"] == "rolled_back"
        assert result["counts"]["rolled_back"] == 2
        assert result["counts"]["kept_billed"] == 0
        assert result["counts"]["kept_missing"] == 0

        for account_no in ("A-12103", "A-12140"):
            account = _account(brazos, account_no)
            assert account.closed_at is not None, f"{account_no} was not closed"
        # Nothing was deleted — both rows are still on file.
        assert (
            customers_models.Account.objects.filter(
                tenant_id=brazos.id, account_no__in=["A-12103", "A-12140"]
            ).count()
            == 2
        )


# ══════════════════════════════════════════════════════════════════════════
# 2 · a BILLED account is KEPT, and the row says why in a clerk's words
# ══════════════════════════════════════════════════════════════════════════


def test_a_BILLED_account_is_kept_and_says_why_without_an_id(brazos, marcus, monkeypatch):
    """⚠ **HARD RULE 4, NOT A POLICY CHOICE.** There is no lawful way to delete
    an issued invoice, so there is no lawful way to un-create the account it was
    issued to. B18 §5.9.4's *"30 days · unbilled accounts only"* states the
    courtesy; this is the law, and it holds on day one as firmly as on day 30.

    The sentence carries **no internal reference** — no rule id, no story id, no
    route (CR-016's ruling, gate G28).
    """
    from datetime import date

    with tenant_ctx(brazos):
        run_id = _unbilled_run(marcus, brazos)
        billed = _account(brazos, "A-12103")
        clean = _account(brazos, "A-12140")

        real = customers_seams.last_issued_invoice_date

        def one_is_billed(account_id):
            if str(account_id) == str(billed.id):
                return date(2026, 7, 31)
            return real(account_id)

        monkeypatch.setattr(customers_seams, "last_issued_invoice_date", one_is_billed)

        actor = staff_actor(brazos, "system_admin", "rb-billed@brazos.test")
        result = import_runs.rollback(actor, run_id)

        assert result["counts"]["rolled_back"] == 1
        assert result["counts"]["kept_billed"] == 1
        assert result["counts"]["kept_missing"] == 0

        assert _account(brazos, "A-12103").closed_at is None, "a billed account is KEPT"
        assert _account(brazos, "A-12103").balance is not None
        assert _account(brazos, "A-12140").closed_at is not None

        row = _row_for(run_id, billed.id)
        assert row.problem.startswith("Kept on rollback")
        assert "billed" in row.problem
        assert row.fix_hint
        for text in (row.problem, row.fix_hint):
            assert "BR-" not in text and "OQ-" not in text and "US-" not in text
            assert "hard rule" not in text.lower()
        assert clean.id is not None


# ══════════════════════════════════════════════════════════════════════════
# 3 · an account that is gone is counted SEPARATELY, never as reversed
# ══════════════════════════════════════════════════════════════════════════


def test_an_account_that_is_gone_is_counted_separately(brazos, marcus):
    """`missing` is the assets branch's `kept_other` posture: the recorded id
    no longer resolves, so it is REPORTED rather than invented around. It must
    never be counted as reversed — that would tell an operator a row came back
    when nothing did."""
    with tenant_ctx(brazos):
        run_id = _unbilled_run(marcus, brazos)
        gone = _account(brazos, "A-12103")
        row = _row_for(run_id, gone.id)
        row.created_record_id = str(uuid4())  # the id no longer resolves
        row.save(update_fields=["created_record_id", "updated_at"])

        actor = staff_actor(brazos, "system_admin", "rb-missing@brazos.test")
        result = import_runs.rollback(actor, run_id)

        assert result["counts"]["rolled_back"] == 1
        assert result["counts"]["kept_missing"] == 1
        assert result["counts"]["kept_billed"] == 0
        assert _account(brazos, "A-12103").closed_at is None


# ══════════════════════════════════════════════════════════════════════════
# 4 · the rollback point is spent EXACTLY once
# ══════════════════════════════════════════════════════════════════════════


def test_the_rollback_point_is_spent_exactly_once(brazos, marcus):
    """BR-MET-090 — one run, one point. After the reversal the point reads
    `used` and a second attempt is refused, so a run cannot be rolled back
    twice and a spent point cannot be re-spent."""
    with tenant_ctx(brazos):
        run_id = _unbilled_run(marcus, brazos)
        assert _point(run_id).status == "available"

        actor = staff_actor(brazos, "system_admin", "rb-once@brazos.test")
        result = import_runs.rollback(actor, run_id)
        assert result["receipt"]["rollback_point"]["status"] == "used"
        assert _point(run_id).status == "used"

        with pytest.raises(errors.BizError) as caught:
            import_runs.rollback(actor, run_id)
        assert caught.value.message_key == "metering.import.not_loaded"
        assert _point(run_id).status == "used"


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE LEDGER HALF — a refusal, because no signed rule covers it (OQ-352)
# ══════════════════════════════════════════════════════════════════════════


def test_a_run_that_posted_OPENING_BOOKS_refuses_and_keeps_its_point(brazos, marcus):
    """⛔ **OQ-352 — REFUSED, NOT GUESSED (the prime directive).**

    The load posted BALANCED OPENING JOURNAL ENTRIES (BR-CUS-049, ❄️ GT-16:
    DR AR 267.30 / CR opening-balance clearing 267.30). Hard rule 4 forbids
    UPDATE or DELETE on a journal entry — a correction is a NEW row — so a
    rollback that removed the opening buckets and closed the account would
    leave the books asserting receivables for an account that no longer
    trades, and the trial balance would stop tying out.

    **No signed document says what the mirror is, or what date it takes.**
    BR-CUS-049 says *"immutable; corrections via J6 only"* and J6 is the
    bill-correction journey — credit note, rebill, re-allocation — which has
    nothing to say about un-migrating a cutover batch. So this refuses by
    name, and the refusal is worth more than the alternative: **the run stays
    `loaded` and its rollback point stays `available`**, so the day the rule
    is ruled the operator can still roll the run back.

    ⚠ **AMENDED 2026-08-30 — THIS COUNTED `1` OPENING ENTRY AND THE ANSWER IS
    `2`, WHICH IS A SECOND MONEY COLUMN AND NOT A DOUBLE POST.** `DEF-1713`
    added the migrated DEPOSIT to the same handoff: this fixture's `A-12103`
    row carries `DEPOSIT 150.00` as well as its four aged buckets, so the load
    posts the AR entry (DR AR / CR opening clearing, ❄️ GT-16's 267.30) **and**
    a deposit entry (DR opening clearing / CR deposit liability, BR-CUS-670).
    Both ride `source_type='opening_balance'` deliberately — B2 Addendum r9 #3
    admits that one value for the cutover and nothing signs a second, and the
    two are told apart by their EVENT, not by a new source type.
    **GT-16 is untouched:** the deposit does not enter the AR tie-out, which is
    why `opening_ar` below is still exactly 267.30.

    So the count is pinned as two NAMED entries rather than as a bare number.
    A bare `== 2` would go green again the day the AR half stopped posting and
    something else posted twice.
    """
    with tenant_ctx(brazos):
        units = _two_units(marcus, brazos)
        run_id = _run(marcus, _csv_for(units), options={"cutover_on": CUTOVER}, mapping=MAPPING)
        receipt = import_runs.load(marcus, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["counts"]["with_opening_balance"] == 1
        assert Decimal(receipt["counts"]["opening_ar"]) == Decimal("267.30")
        opening = ledger_models.JournalEntry.objects.filter(
            tenant_id=brazos.id, source_type="opening_balance"
        )
        keys = sorted(entry.posting_key or "" for entry in opening)
        entries_before = opening.count()
        assert entries_before == 2, (
            "one AR entry (GT-16's 267.30) and one migrated-deposit entry "
            f"(BR-CUS-670, DEF-1713); got {keys}"
        )
        # The event half of the posting key is what separates the two; there is
        # no second `source_type` and deliberately so (B2 Addendum r9 #3).
        assert sum(1 for key in keys if "cutover-deposit:" in key) == 1, keys

        actor = staff_actor(brazos, "system_admin", "rb-books@brazos.test")
        with pytest.raises(errors.BizError) as caught:
            import_runs.rollback(actor, run_id)
        assert caught.value.br_ref == "OQ-352"
        assert caught.value.params.get("oq") == "OQ-352"

        # NOTHING moved: not the books, not the buckets, not the account, and
        # — the part that matters — not the one rollback point the run has.
        run = metering_models.ImportRun.objects.get(pk=run_id)
        assert run.status == "loaded"
        assert _point(run_id).status == "available"
        assert _account(brazos, "A-12103").closed_at is None
        assert (
            customers_models.AccountOpeningBucket.objects.filter(
                account=_account(brazos, "A-12103")
            ).count()
            == 4
        )
        assert (
            ledger_models.JournalEntry.objects.filter(
                tenant_id=brazos.id, source_type="opening_balance"
            ).count()
            == entries_before
        )


def test_the_refusal_sentence_resolves_for_a_utility_to_read():
    """G32's rule, asserted at the raise site: a `message_key` that resolves to
    nothing renders as SILENCE — the user clicks and nothing happens."""
    import json
    from pathlib import Path

    catalogue = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "07-frontend"
            / "src"
            / "i18n"
            / "locales"
            / "en.json"
        ).read_text()
    )
    sentence = catalogue[import_runs.ROLLBACK_OPENING_UNRULED_KEY]
    assert isinstance(sentence, str) and sentence.strip()
    # G28 — no internal reference reaches a utility's screen.
    assert "OQ-" not in sentence and "BR-" not in sentence
    # G33 — at most two sentences, none over twelve words.
    parts = [part for part in sentence.replace("!", ".").split(". ") if part.strip()]
    assert len(parts) <= 2, parts
    assert max(len(part.split()) for part in parts) <= 12, parts

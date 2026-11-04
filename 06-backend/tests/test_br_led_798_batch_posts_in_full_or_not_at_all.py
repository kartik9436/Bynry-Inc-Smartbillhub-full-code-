# ── Trace ──────────────────────────────────────────────
# Rule:    BR-LED-798 — A BATCH OF MANUAL JOURNAL ENTRIES POSTS IN FULL OR NOT
#          AT ALL, AND EVERY ENTRY IS CHECKED BEFORE THE FIRST ONE IS
#          ATTEMPTED. PO ruling 2026-09-24, option (c) of three, closing
#          `OQ-LED-12630`. The rule's own Test column reads **"RATIFIED and
#          UNENFORCED until they are [written], and a lane building `P1.22`
#          owes a case that goes RED on a partially-posted batch"** — this file
#          is that case.
# Task:    Finance blueprint `P1.22` (posting a batch) · `P1.21` (the screen
#          that shows the refusal) — 05-prototype/07 Finance Blueprint.pdf
#          p014, p029
# Rules:   BR-LED-003 (balanced + memo at post; drafts freely editable;
#          posted is immutable) · BR-LED-021 / BR-TEN-035 (the `JE-` number,
#          stamped AT POST) · CLAUDE.md hard rule 4 (no UPDATE/DELETE on a
#          posted entry) · hard rule 6 (idempotency — each entry keeps its own
#          `posting_key`) · hard rule 1 (tenant scoping) · hard-won law 14 (a
#          failed statement poisons the whole PostgreSQL transaction, and the
#          default suite is SQLite, which has no such state)
# Tests:   this file
# Impacts: 06-backend/apps/ledger/manual_je.py (`post_manual_je_batch`) ·
#          06-backend/apps/ledger/journal_api.py
#          (`POST /ledger/journal-entries/post-batch`)
# ───────────────────────────────────────────────────────
"""BR-LED-798 — five entries post together or none of them does.

⚠ **THIS FILE WANTS POSTGRESQL AND SAYS SO, BECAUSE THE RULE IT GUARDS CANNOT
BE PROVED ON THE DEFAULT SUITE (CLAUDE.md hard-won law 14).** `config/settings/
test.py` hardcodes in-memory SQLite. The behaviour under test is a TRANSACTION
that must roll back four good entries because a fifth was refused — and on
PostgreSQL a failed statement aborts the whole transaction, which is the
mechanism that makes all-or-nothing free here and the mechanism SQLite does not
have. The cases below run on either backend and MEAN something only on one:

    JOBS_EAGER=false pytest tests/test_br_led_798_batch_posts_in_full_or_not_at_all.py \\
        --ds=config.settings.pgtest --reuse-db

RED-FIRST PROOF, in the harness that runs it. Before `post_manual_je_batch`
existed, every case here failed with
`AttributeError: module 'apps.ledger.manual_je' has no attribute
'post_manual_je_batch'` — which proves a function was added and nothing about
what it does. **So the case that carries the rule is
`test_a_refused_batch_leaves_nothing_in_the_books`, and it is written against
the ENDPOINT and against the DATABASE**: it counts posted entries and journal
LINES before and after, so it would go red on an implementation that posted
four and reported five, or that looped in the client.

**THE WORKED CASE IS THE ONE THE PO WAS SHOWN, AND THE FIGURES ARE THEIRS.** A
signature covers only what was shown (CLAUDE.md, 🔒 sensitive paths):

    five month-end entries totalling $2,142.75 —
      depreciation              $812.00
      prepaid insurance released $415.50
      accrued utilities          $506.25   ← this one has NO MEMO
      payroll accrual            $268.00
      bank charges               $141.00

    Nothing posts. The rejected alternative would have put $1,227.50
    irreversibly into September (entries 1 and 2), removable only by two
    further reversing entries beside it forever.

⚠ **THE PRE-CHECK IS HALF THE RULING AND IT IS ASSERTED SEPARATELY.** Option (c)
was chosen over the otherwise-identical (a) for exactly one reason — *"Priya is
told about the missing memo before anything is attempted"* — so a build that
rolls back correctly and only reports afterwards has implemented (a) and passed
(c) off as done. `test_the_batch_is_refused_before_anything_is_attempted` is the
case that can tell them apart: it asserts the refusal NAMES the offending entry
and that no `posting_key` was ever written.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.db.models import Q

from apps.ledger import journal_api
from apps.ledger import manual_je
from apps.ledger import models as ledger_models
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    erin,
    lonestar,
    tenant_ctx,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

POSTED_AT = datetime(2026, 9, 30, 17, 0, tzinfo=timezone.utc)
SEPTEMBER = date(2026, 9, 30)

#: The PO's own five, in the PO's own order. Amount, then the memo — and the
#: third's memo is `None`, which is the refusal the worked case turns on.
THE_FIVE = (
    (Decimal("812.00"), "Depreciation, September"),
    (Decimal("415.50"), "Prepaid insurance released"),
    (Decimal("506.25"), None),
    (Decimal("268.00"), "Payroll accrual"),
    (Decimal("141.00"), "Bank charges"),
)
BATCH_TOTAL = Decimal("2142.75")
WOULD_HAVE_POSTED = Decimal("1227.50")  # entries 1 + 2, under the rejected (b)


def _accounts(tenant):
    """Two real chart accounts to move money between."""
    rows = list(
        ledger_models.LedgerAccount.objects.filter(tenant=tenant).order_by("code")[:2]
    )
    assert len(rows) >= 2, "the tenant's chart has fewer than two accounts"
    return rows[0], rows[1]


def _draft(actor, tenant, amount, memo):
    debit, credit = _accounts(tenant)
    return manual_je.save_manual_je(
        actor,
        entry_date=SEPTEMBER,
        memo=memo,
        lines=(
            manual_je.ManualLine(
                ledger_account_id=debit.id, side=ledger_models.SIDE_DEBIT, amount=amount
            ),
            manual_je.ManualLine(
                ledger_account_id=credit.id, side=ledger_models.SIDE_CREDIT, amount=amount
            ),
        ),
    )


def the_month_end_batch(actor, tenant, *, fix_the_third: bool = False):
    """The PO's five drafts. `fix_the_third` supplies the missing memo."""
    made = []
    for index, (amount, memo) in enumerate(THE_FIVE):
        if index == 2 and fix_the_third:
            memo = "Accrued utilities"
        made.append(_draft(actor, tenant, amount, memo))
    assert sum(amount for amount, _ in THE_FIVE) == BATCH_TOTAL
    return [row.entry_id for row in made]


def _signed_in(role="system_admin"):
    """Both halves of a role, deliberately — `require_role` reads `actor.role`
    and the permission class reads the request's, so a user carrying only one
    of them 403s with an `AUTH-002` that looks exactly like a real refusal."""
    import uuid
    from types import SimpleNamespace

    return SimpleNamespace(
        id=uuid.uuid4(), pk=uuid.uuid4(), role=role, is_authenticated=True
    )


def _post_batch(tenant, actor, entry_ids, *, role="system_admin"):
    return api_call(
        journal_api.journal_entries_post_batch,
        "post",
        user=_signed_in(role),
        role=role,
        tenant=tenant,
        data={"entry_ids": [str(one) for one in entry_ids], "posted_at": POSTED_AT.isoformat()},
    )


def _posted_count(tenant):
    """⚠ **ALWAYS CALL THIS INSIDE `tenant_ctx`, AND ON POSTGRESQL IT MATTERS
    IN THE DANGEROUS DIRECTION.** `api_call` leaves the tenant context on its
    way out, and `journal_entries` carries RLS `FORCE`: a read with no
    `app.tenant_id` sees **no rows at all**. So a count taken after the endpoint
    call returns 0 — which, in a case asserting *"nothing was written"*, is a
    PASS for entirely the wrong reason. On SQLite there is no row-level security
    and the same read sees everything, so the trap is invisible on the default
    suite. It is `DEF-LED-6484`'s shape, which the P0 lane recorded on
    2026-09-24 from the other side."""
    return ledger_models.JournalEntry.objects.filter(
        tenant=tenant, status=ledger_models.JE_POSTED
    ).count()


def _line_count(tenant):
    """Inside `tenant_ctx` — see `_posted_count`."""
    return ledger_models.JournalLine.objects.filter(tenant=tenant).count()


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE RULE — a refused batch leaves the books exactly as it found them
# ══════════════════════════════════════════════════════════════════════════
def test_a_refused_batch_leaves_nothing_in_the_books(brazos, dana):
    """BR-LED-798 (1) — ALL-OR-NOTHING, asserted against the DATABASE.

    The PO's worked case: entry 3 of 5 has no memo. Under the rejected (b),
    $1,227.50 would be irreversibly in September and hard rule 4 means it could
    only be removed by two further reversing entries standing beside it for
    ever.

    ⚠ **THE ASSERTION IS A BEFORE/AFTER COUNT OF POSTED ENTRIES AND OF JOURNAL
    LINES, NOT THE RESPONSE BODY.** A client loop over the one-entry endpoint
    would report a failure too; what tells the two apart is whether entries 1
    and 2 are in the books when the dust settles.
    """
    with tenant_ctx(brazos):
        entry_ids = the_month_end_batch(dana, brazos)
        posted_before, lines_before = _posted_count(brazos), _line_count(brazos)

    response = _post_batch(brazos, dana, entry_ids)

    with tenant_ctx(brazos):
        assert response.status_code == 409, "a refused batch is a business-state refusal"
        assert _posted_count(brazos) == posted_before, (
            "entries posted from a batch that was refused: this is the rejected "
            "option (b), and $1,227.50 is irreversibly in September"
        )
        assert _line_count(brazos) == lines_before, (
            "journal LINES were written by a batch that was refused"
        )
        still_drafts = ledger_models.JournalEntry.objects.filter(
            tenant=brazos, pk__in=entry_ids
        )
        assert still_drafts.count() == 5
        assert all(row.status == ledger_models.JE_DRAFT for row in still_drafts)


def test_a_refused_batch_allocates_no_number_and_leaves_no_gap(brazos, dana):
    """BR-LED-798 — *"a refused batch costs the sequence nothing"*.

    A draft carries NO number: the `JE-` number is stamped at POST (BR-LED-021).
    So a refused batch must leave the series where it found it, and there must
    be no gap a reader of the books would later have to explain.
    """
    with tenant_ctx(brazos):
        entry_ids = the_month_end_batch(dana, brazos)
        before = _series_next(brazos)

    _post_batch(brazos, dana, entry_ids)

    with tenant_ctx(brazos):
        assert _series_next(brazos) == before, (
            "the batch consumed numbers it did not use — a gap in the JE series "
            "with nothing to point at"
        )
        # ⚠ `exclude(number__in=("", None))` WOULD PASS WRONGLY AND DID: SQL's
        # `IN` never matches NULL, so a NULL number survives the exclude and the
        # case reports "a number was allocated" over five perfectly clean
        # drafts. `Q(...isnull=True)` is the only form that asks the question.
        assert not (
            ledger_models.JournalEntry.objects.filter(tenant=brazos, pk__in=entry_ids)
            .exclude(Q(number__isnull=True) | Q(number=""))
            .exists()
        ), "the batch stamped a JE- number on an entry it did not post"


def _series_next(tenant):
    """The `journal_entry` series' next value, or None where none is seeded.

    ⚠ The column is `series`, not `code` — a first draft read `code=` and died
    with `FieldError: Cannot resolve keyword 'code'`, which is a test failing
    for its own reason rather than for the rule's."""
    from core import numbering as core_numbering

    from apps.tenancy import models as tenancy_models

    series = tenancy_models.NumberSeries.objects.filter(
        tenant=tenant, series=core_numbering.JOURNAL_ENTRY
    ).first()
    return None if series is None else series.next_number


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE PRE-CHECK — the half that separates option (c) from option (a)
# ══════════════════════════════════════════════════════════════════════════
def test_the_batch_is_refused_before_anything_is_attempted(brazos, dana):
    """BR-LED-798 (2) — the WHOLE-BATCH PRE-CHECK.

    ⚠ **THIS IS THE CASE THAT CAN TELL (c) FROM (a).** Both roll back; only (c)
    tells the officer about the missing memo *before anything is attempted*,
    and that single difference is the entire reason the PO chose it. An
    implementation that posts, fails and rolls back passes the case above and
    must fail this one.

    Two things are asserted: the refusal NAMES the offending entry, and NO
    `posting_key` was ever written — a key is written by `post_draft`, so its
    absence is the evidence that nothing was attempted.
    """
    with tenant_ctx(brazos):
        entry_ids = the_month_end_batch(dana, brazos)
        third = entry_ids[2]

    response = _post_batch(brazos, dana, entry_ids)

    with tenant_ctx(brazos):
        body = response.data
        refused = body["error"]["params"] if "error" in body else body
        blob = str(refused)
        assert str(third) in blob, (
            "the refusal did not name the entry that caused it — the officer is "
            "told a batch failed and has to find out which one themselves"
        )
        # ⚠ **THE EVIDENCE IS `posted_at`, NOT `posting_key`.** A first draft
        # asserted the absence of a `posting_key` and that is not evidence of
        # anything: measured on this fixture, a saved draft carries
        # `number=None`, `posting_key=None` and `posted_at=None`, and the key is
        # written BY THE POST. Asserting its absence over drafts that never had
        # one is a case that cannot fail — law 7's own shape, in a case written
        # to enforce a rule.
        assert not (
            ledger_models.JournalEntry.objects.filter(tenant=brazos, pk__in=entry_ids)
            .exclude(posted_at__isnull=True)
            .exists()
        ), (
            "an entry carries a posted_at, so it WAS attempted: this is option "
            "(a) wearing option (c)'s answer"
        )

    # And the pre-check is a SEPARATE, CALLABLE STEP rather than a branch
    # inside the posting loop — which is the only structural difference between
    # the option the PO chose and the one they did not.
    #
    # ⚠ **RE-ENTERED, BECAUSE `api_call` LEAVES THE TENANT CONTEXT ON ITS WAY
    # OUT.** Calling the read model after it raises `AUTH-003` — a real rule
    # (hard rule 1) refusing correctly, and a failure that looks exactly like
    # a defect in the code under test. The P0 lane recorded the same trap for
    # `provision_tenant` on 2026-09-24.
    with tenant_ctx(brazos):
        problems = manual_je.precheck_manual_je_batch(entry_ids)
        assert {row.entry_id for row in problems} == {str(third)}
        assert "memo" in problems[0].reason


def test_the_pre_check_reports_every_bad_entry_not_only_the_first(brazos, dana):
    """*"refused in ONE answer that names the offending entry"*.

    A batch with two problems that is refused twice is two round trips for a
    person who could have fixed both at once, which is the experience the
    pre-check exists to remove.
    """
    with tenant_ctx(brazos):
        entry_ids = the_month_end_batch(dana, brazos)
        # Break a second one: an unbalanced draft is lawful (BR-LED-003) and
        # unpostable.
        fifth = ledger_models.JournalEntry.objects.get(tenant=brazos, pk=entry_ids[4])
        line = fifth.lines.filter(side=ledger_models.SIDE_CREDIT).first()
        ledger_models.JournalLine.objects.filter(pk=line.pk).update(amount=Decimal("1.0000"))

        response = _post_batch(brazos, dana, entry_ids)
        blob = str(response.data)
        assert str(entry_ids[2]) in blob and str(entry_ids[4]) in blob, (
            "the batch was refused on the first problem only, so the officer "
            "fixes one, resubmits, and is refused again"
        )


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE HAPPY CASE, AND IDEMPOTENCY
# ══════════════════════════════════════════════════════════════════════════
def test_a_clean_batch_posts_every_entry(brazos, dana):
    """*"A batch in which nothing fails is unaffected."*"""
    with tenant_ctx(brazos):
        entry_ids = the_month_end_batch(dana, brazos, fix_the_third=True)
        before = _posted_count(brazos)

    response = _post_batch(brazos, dana, entry_ids)

    with tenant_ctx(brazos):
        assert response.status_code == 200
        assert _posted_count(brazos) == before + 5
        assert len(response.data["results"]) == 5
        posted = ledger_models.JournalEntry.objects.filter(tenant=brazos, pk__in=entry_ids)
        assert all(row.status == ledger_models.JE_POSTED for row in posted)


def test_retrying_the_whole_batch_does_not_double_post(brazos, dana):
    """CLAUDE.md hard rule 6 — *"each entry keeps its own `posting_key`, so
    retrying the whole batch is idempotent"*.

    This is the case that matters after a refusal: the officer fixes the memo
    and submits the SAME five again. A partially-attempted batch must not be
    able to double-post on that retry.
    """
    with tenant_ctx(brazos):
        entry_ids = the_month_end_batch(dana, brazos, fix_the_third=True)
    _post_batch(brazos, dana, entry_ids)
    with tenant_ctx(brazos):
        after_first = _line_count(brazos)

    second = _post_batch(brazos, dana, entry_ids)

    with tenant_ctx(brazos):
        assert second.status_code == 200
        assert _line_count(brazos) == after_first, "the retry wrote journal lines again"
        assert all(row["created"] is False for row in second.data["results"])


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE ORDINARY GUARDS
# ══════════════════════════════════════════════════════════════════════════
def test_a_batch_cannot_reach_another_tenants_entry(brazos, lonestar, dana, erin):
    """CLAUDE.md hard rule 1. The batch takes a LIST of ids, which is a wider
    door than one id in a path, so the tenant predicate is asserted here."""
    with tenant_ctx(lonestar):
        theirs = the_month_end_batch(erin, lonestar, fix_the_third=True)
    with tenant_ctx(brazos):
        mine = the_month_end_batch(dana, brazos, fix_the_third=True)
    response = _post_batch(brazos, dana, [mine[0], theirs[0]])
    assert response.status_code == 409
    with tenant_ctx(lonestar):
        assert (
            ledger_models.JournalEntry.objects.get(tenant=lonestar, pk=theirs[0]).status
            == ledger_models.JE_DRAFT
        )


def test_an_empty_batch_is_refused_rather_than_silently_succeeding(brazos, dana):
    """A batch of nothing that answers 200 is a screen telling an officer their
    month-end posted."""
    with tenant_ctx(brazos):
        assert _post_batch(brazos, dana, []).status_code == 409

# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-011 (manual JE: draft → post lifecycle, three types, balanced
#           at post — TC-1 the saved draft, TC-2 the balanced post, TC-3 the
#           three types, TC-4 the unbalanced/memo-less refusals, TC-5 the role
#           gate and the posted-entry mutation, TC-6 the deleted draft, TC-7
#           isolation)   Screens: S57 · S56
# Rules:    BR-LED-003 (drafts freely editable/deletable; balanced required AT
#           post; posted = immutable; reason + audit) · BR-LED-021 (the `JE-`
#           number, stamped AT POST — a draft has none) · BR-LED-025 (a posting
#           carrying more than two decimals is REFUSED, never rounded) ·
#           BR-LED-001 (source_type `manual_je` on every line) · BR-LED-015
#           (audit) · CLAUDE.md rule 4 · rule 5 · rule 6 · rule 7
# Golden:   LE-4's entry as the fixture (US-LED-011 §4 verbatim): Sep 30, 2026 ·
#           Accrual · DR 1210 Unbilled AR 500.00 / CR 4100 Electric Revenue
#           500.00 · unbalanced variant 500.00 / 480.00, gap 20.00
# ───────────────────────────────────────────────────────
"""A draft is worthless. That is the whole design, and it is the PO's word.

US-LED-011 §1: *"a **draft** is freely editable and deletable — it is worthless
until posted; **Post entry ✓** requires **balanced**, a **memo/reason**, and the
role; the posted entry is **immutable forever**"*.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_011_tc4__an_unbalanced_draft_saves_and_refuses_to_post`. Every other
assertion here follows from it: a draft that could not hold DR 500.00 / CR 480.00
could not be edited into that state, S57's *Must balance* footer would have no
20.00 gap to show, and "balanced at post" would be indistinguishable from
"balanced always".
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest

from apps.ledger import manual_je, models, posting, reporting
from apps.tenancy import models as tenancy_models
from core import errors, numbering as core_numbering

from tests.ledger_le_fixtures import gl
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import executive_actor, tenant_ctx

pytestmark = pytest.mark.django_db

# ── LE-4 / US-LED-011 §4, transcribed ──────────────────────────────────────
ACCRUAL_DATE = date(2026, 9, 30)  # "Sep 30, 2026 · Accrual"
ACCRUAL_AMOUNT = Decimal("500.00")  # "DR 1210 Unbilled AR 500.00 / CR 4100 500.00"
UNBALANCED_CREDIT = Decimal("480.00")  # "Unbalanced variant: 500.00/480.00"
GAP = Decimal("20.00")  # US-LED-011 §7: "gap 20.00 shown, post refused"
MEMO = "Accrue Sep unbilled revenue"  # §4 verbatim
POSTED_AT = datetime(2026, 9, 30, 17, 5, tzinfo=dt_timezone.utc)

#: The `JE-` series row BR-LED-021 allocates from. Created HERE, in the fixture,
#: because `apps.tenancy.services.SERIES_DEFAULTS` seeds five series at
#: provisioning and the journal one is not among them — the gap this lane
#: REPORTS rather than fixes (apps/tenancy/** is another lane's in this session).
#: `test_us_led_011_br_led_021__an_unseeded_series_posts_unnumbered_and_says_so`
#: is the case with no row, and it is the state of every real tenant today.
JE_FORMAT = "JE-{000000}"


def seed_je_series(tenant, next_number=104):
    """LE-8 opens at **JE-104**, so the counter starts there and the workbook's
    own numbers come out of the product.

    ⚠ `update_or_create` since CR-005 (2026-08-17), and the change is the whole
    story of that CR for this file: provisioning now seeds the `JE-` row for
    every tenant, so `get_or_create` FOUND a row already standing at 1 and threw
    its `next_number=104` away — the ratified BR-LED-021 figure went from
    **JE-000104** to **JE-000001** with nothing else altered. The helper's job
    is to OPEN the series at 104; it now does that whether or not the row is
    there.
    """
    tenancy_models.NumberSeries.objects.update_or_create(
        tenant=tenant,
        series=core_numbering.JOURNAL_ENTRY,
        defaults={"format": JE_FORMAT, "next_number": next_number},
    )


def accrual_lines(tenant, credit=ACCRUAL_AMOUNT):
    """LE-4's two lines: DR 1210 Unbilled AR / CR 4100 Electric revenue."""
    return (
        manual_je.ManualLine(
            ledger_account_id=gl(tenant, "1210", "asset").id,
            side=models.SIDE_DEBIT,
            amount=ACCRUAL_AMOUNT,
        ),
        manual_je.ManualLine(
            ledger_account_id=gl(tenant, "4100", "revenue").id,
            side=models.SIDE_CREDIT,
            amount=credit,
        ),
    )


def save(tenant, actor, **overrides):
    values = {
        "entry_date": ACCRUAL_DATE,
        "entry_type": models.JE_ACCRUAL,
        "memo": MEMO,
        "lines": accrual_lines(tenant),
    }
    values.update(overrides)
    return manual_je.save_manual_je(actor, **values)


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the saved draft posts nothing to the books
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_011_tc1__a_saved_draft_is_a_row_that_moves_no_money(brazos, dana, audit_rows):
    """US-LED-011 TC-1 verbatim: *"Draft row on S56 (status draft); editable;
    deletable; posts nothing to the books yet."*

    "Posts nothing" is asserted against the TRIAL BALANCE, not against a status
    column: `reporting.trial_balance` sums POSTED lines only, so a draft that
    leaked into the books would show up as 500.00 where the month holds 0.00.
    """
    with tenant_ctx(brazos):
        result = save(brazos, dana)

        assert result.created is True
        assert result.balanced is True
        assert result.debits == ACCRUAL_AMOUNT and result.credits == ACCRUAL_AMOUNT
        assert result.entry_type == models.JE_ACCRUAL

        entry = models.JournalEntry.objects.get(pk=result.entry_id)
        assert entry.status == models.JE_DRAFT
        # BR-LED-021: *"a DRAFT has NO number"*.
        assert entry.number is None
        # BR-LED-001: every line names its source document.
        assert set(entry.lines.values_list("source_type", flat=True)) == {"manual_je"}
        assert all(line.source_id is not None for line in entry.lines.all())

        books = reporting.trial_balance()
        assert books["total_debit"] == Decimal("0")
        assert books["total_credit"] == Decimal("0")

        # It IS on the S56 list, which is the one surface that shows drafts.
        listed = reporting.journal_entry_list(status=models.JE_DRAFT)["rows"]
        assert [row.entry_id for row in listed] == [result.entry_id]
        assert listed[0].balanced is True and listed[0].number is None

        assert "journal.draft_saved" in {row["action"] for row in audit_rows}


def test_us_led_011_tc1b__a_draft_edits_freely_and_the_lines_are_replaced(brazos, dana):
    """*"Drafts freely editable"* (BR-LED-003) — including adding a line and
    changing an amount in one save, which is what a replace does and an update
    of the existing rows could not."""
    with tenant_ctx(brazos):
        first = save(brazos, dana)
        cash = gl(brazos, "1000", "asset")
        second = manual_je.save_manual_je(
            dana,
            entry_id=first.entry_id,
            entry_date=ACCRUAL_DATE,
            entry_type=models.JE_STANDARD,
            memo="reclassified",
            lines=(
                manual_je.ManualLine(
                    ledger_account_id=cash.id,
                    side=models.SIDE_DEBIT,
                    amount=Decimal("120.00"),
                ),
                manual_je.ManualLine(
                    ledger_account_id=gl(brazos, "4100", "revenue").id,
                    side=models.SIDE_CREDIT,
                    amount=Decimal("120.00"),
                ),
            ),
        )
        assert second.entry_id == first.entry_id
        assert second.created is False
        entry = models.JournalEntry.objects.get(pk=first.entry_id)
        assert entry.type == models.JE_STANDARD
        assert entry.memo == "reclassified"
        assert entry.lines.count() == 2
        assert {line.amount for line in entry.lines.all()} == {Decimal("120.000000")}
        # The document id survives the edit — the entry and its lines still
        # trace to the same thing (see manual_je._draft_source_id).
        assert {line.source_id for line in entry.lines.all()} == {entry.source_id}


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — the post, and the JE- number stamped AT it
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_011_tc2__the_post_balances_stamps_the_number_and_freezes(
    brazos, dana, audit_rows
):
    """US-LED-011 TC-2: *"'Must balance' footer 500.00 = 500.00; posting service
    writes the entry; S56 shows posted, immutable; audit `journal.posted`."*

    BR-LED-021 adds the number: LE-8 opens the series at **JE-104**, so this
    tenant's first posted entry is exactly that — the workbook's own number, out
    of the product rather than out of a document.
    """
    with tenant_ctx(brazos):
        seed_je_series(brazos)
        draft = save(brazos, dana)
        result = manual_je.post_manual_je(dana, entry_id=draft.entry_id, posted_at=POSTED_AT)

        assert result.created is True
        assert result.debits == ACCRUAL_AMOUNT == result.credits  # 500.00 = 500.00
        assert result.number == "JE-000104"

        entry = models.JournalEntry.objects.get(pk=draft.entry_id)
        assert entry.status == models.JE_POSTED
        assert entry.posted_at == POSTED_AT
        assert entry.number == "JE-000104"
        assert entry.posting_key == f"manual_je|{entry.pk}|posted"

        # It is in the books now — and on ONE side, because the trial balance
        # nets each account (LE-1's own presentation).
        books = reporting.trial_balance()
        assert books["total_debit"] == ACCRUAL_AMOUNT == books["total_credit"]
        assert books["balanced"] is True

        posted = [row for row in audit_rows if row["action"] == "journal.posted"]
        assert posted and posted[-1]["after"]["number"] == "JE-000104"
        # The trail carries what the COLUMN holds — NUMERIC(18,6), six places
        # (CLAUDE.md rule 2). BR-LED-025 refuses a THIRD decimal of money; it
        # does not narrow the storage, and an audit row that quietly reformatted
        # the figure would be a second presentation of it.
        assert Decimal(posted[-1]["after"]["debits"]) == ACCRUAL_AMOUNT


def test_us_led_011_tc2b__posting_twice_is_one_entry(brazos, dana):
    """A double-submitted *Post entry* is not an error and is not two entries
    (CLAUDE.md rule 6, US-LED-001 TC-6's posture applied to a human clicking
    twice). The number is allocated ONCE, so the second click cannot consume a
    second one."""
    with tenant_ctx(brazos):
        seed_je_series(brazos)
        draft = save(brazos, dana)
        first = manual_je.post_manual_je(dana, entry_id=draft.entry_id, posted_at=POSTED_AT)
        second = manual_je.post_manual_je(dana, entry_id=draft.entry_id, posted_at=POSTED_AT)

        assert second.created is False
        assert second.entry_id == first.entry_id
        assert second.number == first.number == "JE-000104"
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 1
        assert (
            tenancy_models.NumberSeries.objects.get(
                tenant=brazos, series=core_numbering.JOURNAL_ENTRY
            ).next_number
            == 105
        )


def test_us_led_011_br_led_021__an_unseeded_series_posts_unnumbered_and_says_so(brazos, dana):
    """The entry POSTS when it cannot be numbered, and says by name that it did.

    ⚠ **THIS WAS "the state of EVERY real tenant today" UNTIL CR-005 (2026-08-17)
    AND IT NO LONGER IS — read the change, because it is the good news.**
    `SERIES_DEFAULTS` seeded five series and the journal one was not among them
    (BR-LED-021 (i)), so no tenant could number a manual JE at all. That map is
    now derived from `core.numbering.SERIES_CATALOG` and every tenant is seeded
    with all twenty-two, including `JE-{000000}` — the exact string BR-LED-021
    named as the fix.

    **The BEHAVIOUR under test is unchanged and is still worth asserting**, so
    the row is REMOVED here to reach the state rather than assumed to be absent:
    a series that cannot allocate must not stop the books (BR-LED-003's
    lifecycle does not depend on the number) and must not fake a number
    (`numbering_series_missing`, the `apps/metering/services.py` precedent). It
    is reachable still — an operator may deactivate or delete a row, and a
    tenant provisioned before today's seed keeps whatever it has until
    `manage.py seed_demo --tenant <subdomain>` runs.
    """
    with tenant_ctx(brazos):
        tenancy_models.NumberSeries.objects.filter(
            tenant=brazos, series=core_numbering.JOURNAL_ENTRY
        ).delete()
        draft = save(brazos, dana)
        result = manual_je.post_manual_je(dana, entry_id=draft.entry_id, posted_at=POSTED_AT)

        assert result.created is True
        assert result.number is None
        codes = {gap["code"] for gap in result.unavailable}
        assert "journal_number_series_is_not_seeded" in codes

        listed = reporting.journal_entry_list()
        assert {gap["code"] for gap in listed["unavailable"]} >= {
            "posted_entries_without_a_je_number"
        }


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — the three types
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "entry_type", [models.JE_STANDARD, models.JE_ACCRUAL, models.JE_REVERSING]
)
def test_us_led_011_tc3__all_three_types_are_selectable_and_recorded(brazos, dana, entry_type):
    """US-LED-011 TC-3: *"Standard / Accrual / Reversing selectable per
    prototype; type recorded on the entry (r13 #2)."* The choice is not
    cosmetic — only `accrual` schedules a day-1 mirror (BR-LED-005)."""
    with tenant_ctx(brazos):
        draft = save(brazos, dana, entry_type=entry_type)
        assert models.JournalEntry.objects.get(pk=draft.entry_id).type == entry_type


def test_us_led_011_tc3b__an_unknown_type_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(manual_je.ManualJournalError) as exc:
            save(brazos, dana, entry_type="adjusting")
        assert "Standard / Accrual / Reversing" in str(exc.value)


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — the two refusals at post (THE TEST THIS FILE EXISTS FOR)
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_011_tc4__an_unbalanced_draft_saves_and_refuses_to_post(brazos, dana):
    """US-LED-011 TC-4: *"Post attempted with DR 500.00 / CR 480.00 … Blocked
    client-side (footer shows the 20.00 gap) AND server-side — nothing
    partial."*

    Both halves. The draft SAVES holding the imbalance, because BR-LED-003 makes
    drafts freely editable and a draft that could not be wrong could not be
    corrected. §7's figure comes back on the result — **gap 20.00** — which is
    what S57's *Must balance* footer renders. And the POST is refused, naming
    both totals, with the entry still a draft afterwards.
    """
    with tenant_ctx(brazos):
        seed_je_series(brazos)
        draft = save(brazos, dana, lines=accrual_lines(brazos, credit=UNBALANCED_CREDIT))

        assert draft.balanced is False
        assert draft.debits == ACCRUAL_AMOUNT
        assert draft.credits == UNBALANCED_CREDIT
        assert draft.gap == GAP  # 500.00 - 480.00

        with pytest.raises(posting.PostingError) as exc:
            manual_je.post_manual_je(dana, entry_id=draft.entry_id, posted_at=POSTED_AT)
        message = str(exc.value)
        assert "UNBALANCED" in message and "500.00" in message and "480.00" in message

        entry = models.JournalEntry.objects.get(pk=draft.entry_id)
        assert entry.status == models.JE_DRAFT  # nothing partial landed
        assert entry.number is None
        assert reporting.trial_balance()["total_debit"] == Decimal("0")


def test_us_led_011_tc4b__a_post_with_no_memo_is_refused(brazos, dana):
    """US-LED-011 TC-4's other half: *"or with an empty memo … Blocked … server
    side (balanced + reason required, BR-LED-003)."*

    The entry is immutable the moment it posts, so the memo is the only place
    the WHY can ever be written.
    """
    with tenant_ctx(brazos):
        draft = save(brazos, dana, memo="   ")
        with pytest.raises(manual_je.ManualJournalError) as exc:
            manual_je.post_manual_je(dana, entry_id=draft.entry_id, posted_at=POSTED_AT)
        assert "MEMO" in str(exc.value)
        assert models.JournalEntry.objects.get(pk=draft.entry_id).status == models.JE_DRAFT


def test_us_led_011_br_led_025__a_third_decimal_is_refused_and_never_rounded(brazos, dana):
    """BR-LED-025 (PO 2026-08-12, verbatim *"Refuse and make the caller round"*).

    ⚠ **PROVED RED FIRST.** Before `_carries_more_than_two_decimals` existed,
    this draft SAVED and this entry POSTED carrying 500.005, and
    `apps/ledger/posting.py`'s own docstring said the refusal was *"a rule nobody
    has signed … raised as OQ-126"*. OQ-126 is CLOSED.

    The refusal NAMES the amount and the line, and the ledger rounds NOTHING —
    rounding is the caller's job and happens once, at finalization (B4 ❄️), and a
    ledger that rounded too would be a second rounding site.
    """
    with tenant_ctx(brazos):
        odd = (
            manual_je.ManualLine(
                ledger_account_id=gl(brazos, "1210", "asset").id,
                side=models.SIDE_DEBIT,
                amount=Decimal("500.005"),
            ),
            manual_je.ManualLine(
                ledger_account_id=gl(brazos, "4100", "revenue").id,
                side=models.SIDE_CREDIT,
                amount=Decimal("500.005"),
            ),
        )
        with pytest.raises(posting.PostingError) as exc:
            save(brazos, dana, lines=odd)
        message = str(exc.value)
        assert "MORE THAN TWO DECIMAL PLACES" in message
        assert "500.005" in message
        assert "BR-LED-025" in message
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 0

    # Six-place storage is UNCHANGED (CLAUDE.md rule 2): a caller handing back a
    # figure the database re-read as 500.000000 is not carrying a third cent and
    # must not be refused.
    assert posting._carries_more_than_two_decimals(Decimal("500.000000")) is False
    assert posting._carries_more_than_two_decimals(Decimal("0.001")) is True
    assert posting._carries_more_than_two_decimals(Decimal("1.2300")) is False


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — the role gate, and the posted entry that cannot be edited
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_011_tc5__an_executive_may_not_write_a_journal_entry(brazos, dana):
    """US-LED-011 TC-5, as the roles this product actually has.

    The story says *"Finance/Owner-only"* and there is no Finance and no Owner.
    PO 2026-08-12 (OQ-175): *"System Admin, Billing Clerk"* — **an executive
    reads the books, a clerk writes them.** That ruling was given about
    REVERSING, so it is carried here as a READING and said so on every result.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.AuthError):
            save(brazos, executive_actor())

        draft = save(brazos, dana)
        assert "manual_je_role_gate_is_a_reading_not_a_ruling" in {
            gap["code"] for gap in draft.unavailable
        }

        with pytest.raises(errors.AuthError):
            manual_je.post_manual_je(
                executive_actor(), entry_id=draft.entry_id, posted_at=POSTED_AT
            )


def test_us_led_011_tc5b__a_billing_clerk_may(brazos, marcus):
    """The other half of OQ-175 — both ruled roles get through the same gate."""
    with tenant_ctx(brazos):
        seed_je_series(brazos)
        draft = save(brazos, marcus)
        result = manual_je.post_manual_je(marcus, entry_id=draft.entry_id, posted_at=POSTED_AT)
        assert result.created is True


def test_us_led_011_tc5c__a_posted_entry_cannot_be_edited_or_deleted(brazos, dana):
    """Hard rule 4 / BR-LED-003, at the service layer — the DB trigger is the
    other half and skips on SQLite, so this is the guard the developer database
    still has. The only "edit" is US-LED-013's reverse + repost."""
    with tenant_ctx(brazos):
        seed_je_series(brazos)
        draft = save(brazos, dana)
        manual_je.post_manual_je(dana, entry_id=draft.entry_id, posted_at=POSTED_AT)

        with pytest.raises(posting.PostingError) as edit:
            save(brazos, dana, entry_id=draft.entry_id)
        assert "IMMUTABLE" in str(edit.value)
        assert "reverse + repost" in str(edit.value)

        with pytest.raises(posting.PostingError) as remove:
            manual_je.delete_manual_je(dana, entry_id=draft.entry_id)
        assert "cannot be deleted" in str(remove.value)


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — the deleted draft
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_011_tc6__a_deleted_draft_leaves_the_books_untouched_and_the_trail_intact(
    brazos, dana, audit_rows
):
    """US-LED-011 TC-6: *"Gone without trace in the books (it never touched
    them); audit `journal.draft_deleted` remains."*"""
    with tenant_ctx(brazos):
        draft = save(brazos, dana)
        manual_je.delete_manual_je(dana, entry_id=draft.entry_id)

        assert models.JournalEntry.objects.filter(pk=draft.entry_id).count() == 0
        assert models.JournalLine.objects.filter(journal_entry_id=draft.entry_id).count() == 0
        assert reporting.trial_balance()["total_debit"] == Decimal("0")
        assert "journal.draft_deleted" in {row["action"] for row in audit_rows}


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — isolation
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_011_tc7__a_draft_never_crosses_a_tenant_boundary(brazos, dana, lonestar, erin):
    """US-LED-011 TC-7: *"Its chart accounts only in the GL picker; its entries
    only on the list (RLS)."* Both directions are asserted — Lone Star cannot
    see Brazos Bend's draft, and cannot post to Brazos Bend's chart either."""
    with tenant_ctx(brazos):
        mine = save(brazos, dana)
        brazos_account = gl(brazos, "1210", "asset").id

    with tenant_ctx(lonestar):
        assert reporting.journal_entry_list()["rows"] == ()
        # Another tenant's entry id is not found — nothing is said about whose.
        with pytest.raises(posting.PostingError) as exc:
            manual_je.delete_manual_je(erin, entry_id=mine.entry_id)
        assert "not one of this tenant's entries" in str(exc.value)

        # And another tenant's ACCOUNT cannot be posted to.
        with pytest.raises(posting.PostingError) as forged:
            manual_je.save_manual_je(
                erin,
                entry_date=ACCRUAL_DATE,
                entry_type=models.JE_STANDARD,
                memo="forged",
                lines=(
                    manual_je.ManualLine(
                        ledger_account_id=brazos_account,
                        side=models.SIDE_DEBIT,
                        amount=Decimal("1.00"),
                    ),
                    manual_je.ManualLine(
                        ledger_account_id=gl(lonestar, "4110", "revenue").id,
                        side=models.SIDE_CREDIT,
                        amount=Decimal("1.00"),
                    ),
                ),
            )
        assert "LIVE account of this tenant's own chart" in str(forged.value)

    with tenant_ctx(brazos):
        assert len(reporting.journal_entry_list()["rows"]) == 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-011@0007led (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-04-manual-je.md US-LED-011 §1-§8 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-003/015/021/025 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-4 + LE-8 · 12-governance/02-decision-log.md 2026-08-12 "Approve a JE- series" / "System Admin, Billing Clerk" / "Refuse and make the caller round")
# generated: 2026-08-15 by the ledger close-the-books lane
# checklist: A✔ B✔ C✔ D=deferred(no API half in this lane) E=deferred(no frontend half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: BR-LED-025 was PROVED RED before it was trusted green — with
#         `_carries_more_than_two_decimals` removed from posting.py, the 500.005
#         draft SAVED and the entry POSTED carrying a third decimal
# exceptions: `seed_je_series` creates the tenancy `number_series` row that
#         provisioning does not, because apps/tenancy/** is another lane's in
#         this session; the un-seeded case is asserted on its own in
#         `test_us_led_011_br_led_021__an_unseeded_series_posts_unnumbered_and_says_so`
#         and is the state of every real tenant today · the DB-level immutability
#         and sole-writer triggers are Postgres-only and are covered by
#         tests/test_us_led_001_posting.py; this file asserts the SERVICE half,
#         which is what protects the SQLite developer database
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

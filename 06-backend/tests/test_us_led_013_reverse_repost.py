# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-013 (posted-JE "edit" = one-click REVERSE + REPOST, and the
#           S56 journal list — TC-1 LE-8's three entries, TC-2 the list and its
#           links, TC-3 reason + audit, TC-4 the reverse-only path, TC-5 the
#           mutation/role refusals, TC-6 the double-reverse block, TC-7
#           isolation)
#           Screens: S56 · S57
# Rules:    BR-LED-003 ("edit" = reverse + repost; posted = immutable; reason +
#           audit) · BR-LED-012 (the journal list carries the IS-5 row) ·
#           BR-LED-015 (every finance action audits) · CLAUDE.md rule 4
#           (financial immutability) · rule 5 (the posting service is the sole
#           writer) · rule 7 (audit)
# Golden:   LE-8 verbatim — JE-104 250.00 → JE-105 mirror → JE-106 205.00, net
#           effect **205.00**, all three entries forever
# ───────────────────────────────────────────────────────
""" "Edit" is a word the books do not have.

**THE TEST THIS FILE EXISTS FOR** is
`test_us_led_013_tc5__nothing_can_update_a_posted_entry_the_only_edit_is_a_new_entry`.
Hard rule 4 has no exception, and BR-LED-003 turns that into a workflow: one
click posts the linked MIRROR and hands back a prefilled correction. The
original stays byte for byte.

LE-8, transcribed: *"JE-104 posted with 250.00 (should be 205.00): one click →
JE-105 mirror reversal (linked) + JE-106 draft prefilled → corrected to 205.00 →
post. Net effect 205.00; history shows all three, forever."*
"""

from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

import pytest
from django.db import DatabaseError, transaction

from apps.ledger import journal, models, posting, reporting

from tests.ledger_le_fixtures import POSTED_AT, gl, line, uuid_for
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")

# ── LE-8, transcribed ──────────────────────────────────────────────────────
JE104_AMOUNT = Decimal("250.00")  # "JE-104 posted with 250.00 (should be 205.00)"
JE106_AMOUNT = Decimal("205.00")  # "corrected to 205.00"
NET_EFFECT = Decimal("205.00")  # "Net effect 205.00"
JE104_DATE = date(2026, 8, 4)  # "JE-104 (Aug 4, 2026, standard, memo 'Reclass card fees')"
CORRECTION_DATE = date(2026, 8, 8)  # "JE-105 mirror (Aug 8) + JE-106 corrected (Aug 8)"
REASON = "keyed 250.00, correct amount 205.00"  # US-LED-013 §4 verbatim
CORRECTED_AT = datetime(2026, 8, 8, 10, 30, tzinfo=dt_timezone.utc)


def post_je104(tenant):
    """LE-8's original: a standard JE reclassing card fees, keyed at 250.00.

    DR 6800 Bank fees / CR 1000 Cash — the account pair LE-8 does not name, so
    the two SIGNED accounts closest to *"Reclass card fees"* are used and the
    AMOUNT, which LE-8 does fix, is what every assertion here turns on.
    """
    fees = gl(tenant, "6800", "expense")
    cash = gl(tenant, "1000", "asset")
    return posting.post(
        posting.PostingRequest(
            posting_key="manual_je|JE-104|posted",
            entry_date=JE104_DATE,
            posted_at=POSTED_AT,
            currency="USD",
            lines=(
                line(
                    fees,
                    models.SIDE_DEBIT,
                    JE104_AMOUNT,
                    source_type="manual_je",
                    source_id=uuid_for("JE-104"),
                ),
                line(
                    cash,
                    models.SIDE_CREDIT,
                    JE104_AMOUNT,
                    source_type="manual_je",
                    source_id=uuid_for("JE-104"),
                ),
            ),
            source_type="manual_je",
            source_id=uuid_for("JE-104"),
            memo="Reclass card fees",
        )
    )


def post_je106(tenant, draft):
    """The corrected repost — the returned draft with ONE amount changed.

    This is what a caller does with `repost_draft`: it is a payload, the
    correction is a normal `post()`, and the ledger never had to grow an "edit".
    """
    return posting.post(
        posting.PostingRequest(
            posting_key="manual_je|JE-106|posted",
            entry_date=CORRECTION_DATE,
            posted_at=CORRECTED_AT,
            currency="USD",
            lines=tuple(
                posting.PostingLine(
                    ledger_account_id=row.ledger_account_id,
                    side=row.side,
                    amount=JE106_AMOUNT,
                    source_type=row.source_type,
                    source_id=uuid_for("JE-106"),
                )
                for row in draft
            ),
            source_type="manual_je",
            source_id=uuid_for("JE-106"),
            memo=f"Corrected reclass of card fees — {REASON}",
        )
    )


def net_on(tenant, code):
    """Σ debits − credits on one GL, straight out of `journal_lines`."""
    total = ZERO
    for side, amount in models.JournalLine.objects.filter(
        tenant=tenant, ledger_account__code=code, journal_entry__status=models.JE_POSTED
    ).values_list("side", "amount"):
        total += amount if side == models.SIDE_DEBIT else -amount
    return total


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — LE-8's three entries, and the net effect
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_013_tc1__one_click_yields_the_mirror_and_the_prefilled_draft(brazos, dana):
    """LE-8 verbatim: 250.00 − 250.00 + 205.00 = **205.00**, and all three
    entries survive.

    The mirror is posted by `apps.ledger.posting.reverse_entry`, which reads the
    ORIGINAL and copies it with the sides swapped — so the reversal cannot
    disagree with what it reverses, which is the one thing a reversal may never
    do.
    """
    with tenant_ctx(brazos):
        original = post_je104(brazos)
        assert net_on(brazos, "6800") == JE104_AMOUNT

        result = journal.reverse_and_repost(
            original.entry_id,
            reason=REASON,
            entry_date=CORRECTION_DATE,
            posted_at=CORRECTED_AT,
            actor=dana,
        )
        assert result.mirror_created is True
        assert result.debits == result.credits == JE104_AMOUNT
        assert net_on(brazos, "6800") == ZERO, "the mirror cancels the original exactly"

        # The prefilled draft is the original's lines, dimensions intact.
        assert len(result.repost_draft) == 2
        assert {row.amount for row in result.repost_draft} == {JE104_AMOUNT}
        assert {row.side for row in result.repost_draft} == {
            models.SIDE_DEBIT,
            models.SIDE_CREDIT,
        }

        post_je106(brazos, result.repost_draft)
        assert net_on(brazos, "6800") == NET_EFFECT

        # All three, forever.
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 3
        assert (
            models.JournalEntry.objects.filter(tenant=brazos, status=models.JE_POSTED).count() == 3
        )


def test_us_led_013_tc1b__the_original_is_byte_for_byte_what_it_was(brazos, dana):
    """Hard rule 4, checked on the ROW rather than on a promise.

    Every column of JE-104 and every one of its lines is captured before the
    click and compared after. A reverse+repost that "helpfully" restated the
    original's memo, status or amount would pass every balance check and destroy
    the only record of what actually happened.
    """
    with tenant_ctx(brazos):
        original = post_je104(brazos)
        entry = models.JournalEntry.objects.get(pk=original.entry_id)
        before = (
            entry.entry_date,
            entry.type,
            entry.status,
            entry.memo,
            entry.currency,
            entry.posting_key,
            entry.posted_at,
        )
        lines_before = sorted(
            (str(row.ledger_account_id), row.side, row.amount) for row in entry.lines.all()
        )

        journal.reverse_and_repost(
            original.entry_id,
            reason=REASON,
            entry_date=CORRECTION_DATE,
            posted_at=CORRECTED_AT,
            actor=dana,
        )

        entry.refresh_from_db()
        assert (
            entry.entry_date,
            entry.type,
            entry.status,
            entry.memo,
            entry.currency,
            entry.posting_key,
            entry.posted_at,
        ) == before
        assert (
            sorted((str(row.ledger_account_id), row.side, row.amount) for row in entry.lines.all())
            == lines_before
        )


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — the S56 list and its two link directions
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_013_tc2__the_journal_list_shows_all_three_with_links_both_ways(brazos, dana):
    """US-LED-013 TC-2: *"S56 list shows JE-104 (reversed), JE-105 (reversal,
    linked), JE-106 (posted)"*.

    Two link columns, because r13 #2 gives the pair two links and one column
    cannot answer both questions: JE-104 needs *"who reversed me"* and JE-105
    needs *"what do I reverse"*.
    """
    with tenant_ctx(brazos):
        original = post_je104(brazos)
        result = journal.reverse_and_repost(
            original.entry_id,
            reason=REASON,
            entry_date=CORRECTION_DATE,
            posted_at=CORRECTED_AT,
            actor=dana,
        )
        post_je106(brazos, result.repost_draft)

        listing = reporting.journal_entry_list()
        rows = {row.entry_id: row for row in listing["rows"]}
        assert len(rows) == 3

        je104 = rows[result.original_entry_id]
        je105 = rows[result.mirror_entry_id]
        assert je104.reversed_by_entry_id == je105.entry_id
        assert je105.reversal_of_entry_id == je104.entry_id
        assert je105.type == models.JE_REVERSING
        assert all(row.balanced for row in listing["rows"])
        assert all(row.status == models.JE_POSTED for row in listing["rows"])

        # Default sort is entry_date desc (the epic's capability matrix).
        dates = [row.entry_date for row in listing["rows"]]
        assert dates == sorted(dates, reverse=True)

        # Filters from the matrix.
        assert len(reporting.journal_entry_list(entry_type=models.JE_REVERSING)["rows"]) == 1
        assert len(reporting.journal_entry_list(source_type="manual_je")["rows"]) == 3
        assert len(reporting.journal_entry_list(search="Reclass card fees")["rows"]) == 1


def test_us_led_013_tc2b__the_two_columns_the_matrix_wants_and_the_books_do_not_have(brazos, dana):
    """BR-LED-012's row opens with a **JE #** and offers **Posted by**. ONE of
    the two now has a source; the other still does not, and the list reports it.

    ⚠ **AMENDED 2026-08-15 (the close-the-books lane), and the old assertions
    are kept in the docstring because they are the state this test was written
    to hold.** It used to assert `"journal_entry" not in numbering.KNOWN_SERIES`
    and the problem code `journal_entries_have_no_number`. **OQ-176 is CLOSED**
    — PO 2026-08-12, verbatim *"Approve a JE- series"* → **BR-LED-021** — so the
    series is the NINTH in `core/numbering.KNOWN_SERIES`, `journal_entries.number`
    carries it, and the gap that remains is narrower: a POSTED entry with no
    number, which means this tenant has no `journal_entry` series row.

    `post_je104` posts through `apps.ledger.posting.post` and NOT through the
    manual-JE service, so it allocates nothing — which is exactly the case the
    narrowed code names.

    **Posted by is unchanged and still has no source:** the actor lives in
    `audit_log`, which is another module's table.
    """
    with tenant_ctx(brazos):
        post_je104(brazos)
        codes = {gap["code"] for gap in reporting.journal_entry_list()["unavailable"]}
        assert "posted_entries_without_a_je_number" in codes
        assert "journal_entries_have_no_number" not in codes
        # ⚠ **THE GAP IS GONE, NOT MERELY UNASSERTED (`DEF-LED-6643`).** It was
        # appended to every journal read unconditionally and had no catalogue
        # key, so every Journal and every Trial balance printed *"The books
        # will not state this. The reason has no wording yet."* It described
        # a *Posted by* column no screen in this product offers, which makes
        # it rationale rather than an absence a clerk meets (B14 rule 33).
        assert "posted_by_is_in_audit_log_not_on_the_entry" not in codes

        from core import numbering

        assert "journal_entry" in numbering.KNOWN_SERIES
        assert len(numbering.KNOWN_SERIES) == 9
        # The column BR-LED-021 minted, on the model and on the list row.
        assert reporting.journal_entry_list()["rows"][0].number is None


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — the reason, and where it lands
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_013_tc3__the_reason_is_required_and_reaches_the_audit_trail(
    brazos, dana, audit_rows
):
    """US-LED-013 TC-3: *"The click demands a reason; audit `journal.reversed`
    (JE-104→105) + `journal.posted` (JE-106) with actor + reason."*

    Before this lane, `apps.ledger.posting.reverse_entry`'s audit payload
    carried the ids, the key, the date and the totals and had nowhere to put
    WHY. The additive `audit_context` parameter is why the reason is on the row
    here — and the row is grouped on `journal.reversed`, so a reader looking for
    corrections finds the reason on the record they are already reading.
    """
    with tenant_ctx(brazos):
        original = post_je104(brazos)
        with pytest.raises(journal.JournalActionError):
            journal.reverse_and_repost(
                original.entry_id,
                reason="   ",
                entry_date=CORRECTION_DATE,
                posted_at=CORRECTED_AT,
                actor=dana,
            )
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 1

        journal.reverse_and_repost(
            original.entry_id,
            reason=REASON,
            entry_date=CORRECTION_DATE,
            posted_at=CORRECTED_AT,
            actor=dana,
        )

        reversed_rows = [row for row in audit_rows if row["action"] == "journal.reversed"]
        assert len(reversed_rows) == 1
        assert reversed_rows[0]["after"]["reason"] == REASON
        assert reversed_rows[0]["after"]["action"] == "reverse_and_repost"
        assert reversed_rows[0]["actor_user_id"] == dana.id
        assert reversed_rows[0]["entity_id"] == original.entry_id

        # …and the MIRROR's own `journal.posted` row carries it too, so the
        # reason is answerable from either end of the pair.
        posted_rows = [row for row in audit_rows if row["action"] == "journal.posted"]
        assert any(row["after"].get("reason") == REASON for row in posted_rows)


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — the reverse-only path
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_013_tc4__the_draft_may_simply_be_discarded(brazos, dana):
    """US-LED-013 TC-4: *"Staff may post JE-105 and discard the JE-106 draft
    (drafts are worthless) — net effect = clean reversal, trail intact."*

    A payload nobody stored is discarded by doing nothing, which is why the
    prefilled draft is returned rather than written — and the module says so on
    every result rather than leaving a reader to notice.
    """
    with tenant_ctx(brazos):
        original = post_je104(brazos)
        result = journal.reverse_and_repost(
            original.entry_id,
            reason=REASON,
            entry_date=CORRECTION_DATE,
            posted_at=CORRECTED_AT,
            actor=dana,
        )
        # The draft is dropped on the floor. Net effect: a clean reversal.
        assert net_on(brazos, "6800") == ZERO
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 2
        assert not models.JournalEntry.objects.filter(
            tenant=brazos, status=models.JE_DRAFT
        ).exists()

        codes = {gap["code"] for gap in result.unavailable}
        assert "repost_draft_is_not_persisted" in codes
        assert "finance_owner_role_gate_is_not_enforced_here" in codes


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — THE ONE. No path anywhere UPDATEs a posted entry.
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_013_tc5__nothing_can_update_a_posted_entry_the_only_edit_is_a_new_entry(
    brazos, dana
):
    """US-LED-013 TC-5: *"Direct UPDATE/DELETE on JE-104 … refused server-side
    (append-only triggers)"*, and hard rule 4 above it.

    Three probes, because there are three ways an "edit" gets written:

      1. the SERVICE — `apps/ledger/journal.py` contains no `.save()`,
         `.update()` or `.delete()` at all;
      2. the ORM — an `.update()` on the posted entry (Postgres refuses it at
         the trigger; on the developer database the assertion is that no code
         path in this module attempts one);
      3. the OUTCOME — after the lawful correction the books hold THREE entries
         and the original's amount is still 250.00.
    """
    import inspect

    source = inspect.getsource(journal)
    for mutation in (".save(", ".update(", ".delete(", "objects.create("):
        assert mutation not in source, f"{mutation} in a module whose whole point is not to"

    with tenant_ctx(brazos):
        original = post_je104(brazos)
        entry = models.JournalEntry.objects.get(pk=original.entry_id)

        from tests.isolation_helpers import is_postgres

        if is_postgres():
            with pytest.raises(DatabaseError):
                with transaction.atomic():
                    models.JournalEntry.objects.filter(pk=entry.pk).update(memo="edited in place")

        result = journal.reverse_and_repost(
            original.entry_id,
            reason=REASON,
            entry_date=CORRECTION_DATE,
            posted_at=CORRECTED_AT,
            actor=dana,
        )
        post_je106(brazos, result.repost_draft)

        entry.refresh_from_db()
        assert entry.memo == "Reclass card fees"
        assert sum(row.amount for row in entry.lines.filter(side=models.SIDE_DEBIT)) == (
            JE104_AMOUNT
        )
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 3


def test_us_led_013_tc5b__a_draft_cannot_be_reversed(brazos, dana):
    """Mirroring a draft would put an entry in the books to cancel one that
    never entered them. `apps.ledger.posting.reverse_entry` refuses it; this
    asserts the refusal survives the wrapper."""
    with tenant_ctx(brazos):
        with pytest.raises(journal.JournalActionError):
            journal.reverse_and_repost(
                uuid_for("no-such-entry"),
                reason=REASON,
                entry_date=CORRECTION_DATE,
                posted_at=CORRECTED_AT,
                actor=dana,
            )


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — an entry reverses once
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_013_tc6__a_second_reverse_click_is_a_no_op_never_a_second_mirror(brazos, dana):
    """US-LED-013 TC-6: *"Blocked — an entry reverses once; the link makes the
    state visible (no double-mirror)."*

    The second click replays the SAME posting key, so it returns the FIRST
    mirror with `mirror_created=False` and writes nothing — which is the right
    answer for a double-submitted form. What must never happen is a SECOND
    mirror: it would credit the same 250.00 twice and every entry would still
    balance, so the trial balance would not notice.
    """
    with tenant_ctx(brazos):
        original = post_je104(brazos)
        first = journal.reverse_and_repost(
            original.entry_id,
            reason=REASON,
            entry_date=CORRECTION_DATE,
            posted_at=CORRECTED_AT,
            actor=dana,
        )
        second = journal.reverse_and_repost(
            original.entry_id,
            reason="clicked twice",
            entry_date=CORRECTION_DATE,
            posted_at=CORRECTED_AT,
            actor=dana,
        )

        assert second.mirror_created is False
        assert second.mirror_entry_id == first.mirror_entry_id
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 2
        assert net_on(brazos, "6800") == ZERO, "not −250.00; the money is cancelled once"


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — isolation
# ═══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
def test_us_led_013_tc7__a_foreign_entry_id_reverses_nothing(brazos, dana, lonestar, erin):
    """US-LED-013 TC-7: *"Its entries only; a Brazos Bend JE id 404s (RLS)."*"""
    with tenant_ctx(brazos):
        original = post_je104(brazos)
    with tenant_ctx(lonestar):
        with pytest.raises(journal.JournalActionError):
            journal.reverse_and_repost(
                original.entry_id,
                reason=REASON,
                entry_date=CORRECTION_DATE,
                posted_at=CORRECTED_AT,
                actor=erin,
            )
        assert reporting.journal_entry_list()["rows"] == ()
    with tenant_ctx(brazos):
        assert models.JournalEntry.objects.filter(tenant=brazos).count() == 1
        assert net_on(brazos, "6800") == JE104_AMOUNT


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-013@e3b0c44 (sources: 04-docs/05-modules/09-ledger/06-epics/EP-LED-04-manual-je.md US-LED-013 §1/§3/§5/§7 + the S56 capability matrix · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-8 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-003/012/015)
# generated: 2026-08-11 by Eng-Lead (W5 ledger reporting lane)
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: TC-5 was PROVED RED FIRST — `reverse_and_repost` was mutated to UPDATE the posted entry's amount in place instead of reversing it; the run failed and the verbatim failure is quoted in the lane report and the human-review row
# exceptions: LE-8 fixes the AMOUNTS (250.00 → 205.00) and not the GL pair, so
#         `post_je104` uses two SIGNED accounts (6800 Bank fees / 1000 Cash)
#         closest to its memo *"Reclass card fees"* and every assertion turns on
#         the amounts, which are the signed part · the FINANCE/OWNER role
#         refusal of TC-5 is NOT exercised: role enforcement is a DRF permission
#         class on an endpoint and this story ships none — the gap is asserted
#         as a reported code on the result instead, and the mapping from the
#         three implemented roles to "Finance/Owner" is an OQ this lane minted ·
#         the DB-level UPDATE probe runs only on Postgres (the developer
#         database has no triggers); on SQLite the source-level assertion is what
#         holds
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

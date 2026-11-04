# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (source-event posting contracts — TC-5's database half:
#           "unbalanced entry rejected by the B2 §3 constraint trigger") ·
#           US-LED-003 (reversal pairs — TC-3 links, TC-5's database half:
#           "UPDATE/DELETE on any posted journal row rejected outright") ·
#           US-LED-005 (chart of accounts — TC-1/TC-6: codes UNIQUE per
#           tenant, and the same code lawful in another tenant)
#           Screens: S56 · S36
# Rules:    CLAUDE.md rule 1 (tenant scoping) · rule 2 (money NUMERIC(18,6) +
#           CHAR(3)) · rule 4 (financial immutability) · rule 5 (balanced
#           pairs) · BR-LED-003 (posted immutable; drafts editable; balanced
#           at post) · BR-LED-005 (accrual auto-reverse link) · BR-LED-014
#           (export codes)
# ───────────────────────────────────────────────────────
"""The ledger journal core: the shape of the books, and the laws on them.

WHAT RUNS WHERE, stated because it changes what these tests are worth. The
default test database is SQLite, which has neither row-level security nor the
triggers `ledger/0002` installs. So:

  * SHAPE and CONSTRAINTS run everywhere — money precision, the currency
    partner, per-tenant unique GL codes, `amount >= 0`, the two-value `side`,
    one mirror per entry.
  * BALANCE and APPEND-ONLY are database triggers. Every one of those cases
    carries `requires_postgres` and SKIPS on SQLite rather than passing
    vacuously. Run them with:

        DJANGO_SETTINGS_MODULE=config.settings.local \\
          python -m pytest tests/test_us_led_journal_core.py -q

  * TENANT ISOLATION is the G5 suite's job (`-m isolation`), whose catalog
    sweep names any table that reached the schema without an RLS policy.
  * SOLE WRITER (hard rule 5) became a database trigger in `ledger/0004` on
    2026-08-11, so every raw write below now goes through
    `open_raw_write_window()` — read its docstring: the bypass is the point of
    this file, and the fence is proved in `tests/test_us_led_001_posting.py`.

The distinction matters more here than anywhere else in the codebase. "Debits
equal credits" is not a property these classes have; it is a property the
database enforces, and a green run on SQLite has proved nothing about it. That
is why the trigger cases fail loudly on Postgres rather than being asserted in
Python where a future `.update()` would walk straight past them.
"""

from datetime import date
from decimal import Decimal

import pytest
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils import timezone

from apps.ledger import models

from tests.isolation_helpers import requires_postgres
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ── fixtures: the smallest chart and the smallest entry ─────────────────────
def an_account(tenant, code="1200", name="Accounts receivable", type_="asset"):
    """The tenant's account for `code` — SEEDED OR CREATED.

    AMENDED 2026-08-11 (GL-designation lane). Provisioning now seeds the
    finance-signed chart of accounts (B5 line 74) into every tenant, so `1200`,
    `4100`, `4200` and most other codes these tests reach for ALREADY EXIST on
    a provisioned tenant and a plain `.create()` collides with
    `uq_ledger_accounts_code`. `get_or_create` keeps every caller below meaning
    what it always said — *"give me the AR account"* — rather than pretending
    the chart is empty.

    The two DUPLICATION cases create explicitly instead of calling this, because
    a duplicate is precisely what they are asserting.
    """
    row, _made = models.LedgerAccount.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": name, "type": type_}
    )
    return row


def open_raw_write_window():
    """Let the next raw INSERT past the SOLE-WRITER fence (ledger/0004).

    ADDED 2026-08-11 (posting-service lane). Since ledger/0004,
    `journal_entries` and `journal_lines` refuse an INSERT that did not come
    through `apps/ledger/posting.post()` — CLAUDE.md rule 5 made structural.

    **Every test in this file writes journal rows RAW, on purpose**, because
    what it asserts is the DATABASE's own law: that an unbalanced posted entry
    is refused, that a posted line cannot be updated, that a draft may sit
    unbalanced. Those are properties the schema must hold *independently of the
    service* — a suite that could only reach the tables through `post()` would
    be asserting that `post()` behaves, which is a different and much weaker
    claim. So the bypass is deliberate and it is spelled out at the call site
    rather than smuggled into a fixture.

    The fence itself is proved in `tests/test_us_led_001_posting.py`, which
    never calls this. `set_config(..., true)` is transaction-local, so pytest's
    rollback closes the window whatever the test does.
    """
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.ledger_posting', 'on', true)")


def an_entry(tenant, **overrides):
    """⚠ **`currency` BECAME REQUIRED ON 2026-09-24 (`P0.7`)** — the full
    reasoning is on `tests/test_us_led_001_posting.raw_entry`. In short:
    `JournalEntry.currency` no longer defaults to `USD`, and **removing a
    Django default does not make the write fail, it makes it write `""`** —
    which `tenancy/0050`'s foreign key into `currencies` then refuses at
    COMMIT, inside Django's teardown, naming the constraint and not the test.
    """
    values = dict(
        tenant=tenant,
        entry_date=date(2026, 7, 31),
        source_type="invoice",
        memo="WE-1 issue",
        currency="USD",
    )
    values.update(overrides)
    open_raw_write_window()
    return models.JournalEntry.objects.create(**values)


def a_line(tenant, entry, gl, side, amount, **overrides):
    open_raw_write_window()
    return models.JournalLine.objects.create(
        tenant=tenant,
        journal_entry=entry,
        ledger_account=gl,
        side=side,
        amount=Decimal(amount),
        **overrides,
    )


def post(entry):
    """The draft -> posted transition, which is where balance is asserted."""
    entry.status = models.JE_POSTED
    entry.save(update_fields=["status", "posted_at", "updated_at"])


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-005 — the chart of accounts
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_005_tc1__a_gl_code_is_unique_within_its_tenant(brazos, dana):
    """B2 §2 `UNIQUE (tenant_id, code)`.

    Two `4100`s in one tenant means every revenue figure has two possible
    homes and the trial balance stops being a statement about anything.
    """
    with tenant_ctx(brazos):
        seeded = an_account(brazos, code="4100", name="Electric usage", type_="revenue")
        assert seeded.pk is not None
        # Explicit `.create()`, not the helper: a SECOND 4100 is the thing
        # under test, and the helper now returns the tenant's existing one.
        with pytest.raises(IntegrityError), transaction.atomic():
            models.LedgerAccount.objects.create(
                tenant=brazos, code="4100", name="Electric usage (dup)", type="revenue"
            )


def test_us_led_005_tc6__the_same_code_is_lawful_in_another_tenant(brazos, lonestar, dana):
    """US-LED-005 TC-6 — *"Brazos Bend codes can repeat there"*.

    The unique constraint leads with `tenant` for exactly this reason: a chart
    of accounts is the tenant's own, and 4100 means whatever they say it means.
    """
    with tenant_ctx(brazos):
        mine = an_account(brazos, code="4100", name="Electric usage", type_="revenue")
    with tenant_ctx(lonestar):
        other = an_account(lonestar, code="4100", name="Power sales", type_="revenue")
    assert other.pk is not None
    # Both tenants are seeded with a 4100 since 2026-08-11, which makes the
    # point sharper rather than weaker: two rows, two tenants, one code.
    assert other.pk != mine.pk
    assert (mine.tenant_id, other.tenant_id) == (brazos.id, lonestar.id)


def test_us_led_005_tc3__deactivation_is_a_timestamp_not_a_delete(brazos, dana):
    """IS-1 deactivate-first: the row survives, `deleted_at` carries the state.

    A GL account a journal line points at is part of a financial record
    (CLAUDE.md rule 4's reasoning), so the chart has no hard-delete path.
    """
    with tenant_ctx(brazos):
        gl = an_account(brazos, code="6805", name="Card processor fees", type_="expense")
        gl.deleted_at = timezone.now()
        gl.save(update_fields=["deleted_at"])
        gl.refresh_from_db()
        assert gl.deleted_at is not None
        assert models.LedgerAccount.objects.filter(pk=gl.pk).exists()


def test_us_led_005_tc2__export_codes_ride_on_the_chart_row(brazos, dana):
    """r13 #5 / BR-LED-014 — `qbo_ref` and `xero_ref` are columns here, so an
    export can name the account the target system knows it by (LE-5)."""
    with tenant_ctx(brazos):
        gl = an_account(brazos, code="4100", name="Electric usage", type_="revenue")
        gl.qbo_ref = "QBO-4100"
        gl.xero_ref = "200"
        gl.save(update_fields=["qbo_ref", "xero_ref"])
        gl.refresh_from_db()
        assert (gl.qbo_ref, gl.xero_ref) == ("QBO-4100", "200")


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-001 — the shape a balanced entry is written into
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_001_tc2__a_line_keeps_six_decimals_and_the_entry_its_currency(brazos, dana):
    """CLAUDE.md rule 2 — NUMERIC(18,6) with a CHAR(3) partner.

    The partner sits on the ENTRY: a journal entry that mixed currencies could
    not balance in any meaningful sense, so one currency per entry is what
    "balanced" means, not a convenience.
    """
    with tenant_ctx(brazos):
        ar = an_account(brazos, code="1200")
        entry = an_entry(brazos)
        line = a_line(brazos, entry, ar, models.SIDE_DEBIT, "247.874321")
        line.refresh_from_db()
        assert line.amount == Decimal("247.874321")
        assert entry.currency == "USD" and len(entry.currency) == 3


def test_us_led_001_tc2__amount_carries_no_sign_direction_is_the_side(brazos, dana):
    """B2 §2 `CHECK (amount >= 0)`.

    A negative amount would be a second, invisible way to express a credit —
    and the balance sums would then agree with themselves while the books said
    something else.
    """
    with tenant_ctx(brazos):
        ar = an_account(brazos, code="1200")
        entry = an_entry(brazos)
        with pytest.raises(IntegrityError), transaction.atomic():
            a_line(brazos, entry, ar, models.SIDE_CREDIT, "-1.000000")


def test_us_led_001_tc5__an_unreadable_side_cannot_reach_the_books(brazos, dana):
    """`ck_journal_lines_side` — part of the BALANCE guarantee, not decoration.

    The balance check sums `FILTER (WHERE side='debit')` against
    `FILTER (WHERE side='credit')`. A row with `side='dbit'` falls into neither
    sum, so an entry holding it computes 0 = 0 and passes as balanced while
    real money sits in the books under a side nothing can read. The CHECK is
    what makes those two filters exhaustive.
    """
    with tenant_ctx(brazos):
        ar = an_account(brazos, code="1200")
        entry = an_entry(brazos)
        with pytest.raises(IntegrityError), transaction.atomic():
            a_line(brazos, entry, ar, "dbit", "100.000000")


def test_us_led_001_tc1__every_dimension_column_accepts_its_reference(brazos, dana):
    """r13 #1 / BR-LED-001 — the dimension set exists on the LINE.

    Shape only. The STAMPING (resolve account -> unit -> premises at posting,
    refuse a tax line with no authority) is US-LED-002 and belongs to the
    posting service, which this slice does not build.
    """
    with tenant_ctx(brazos):
        ar = an_account(brazos, code="1200")
        entry = an_entry(brazos)
        line = a_line(brazos, entry, ar, models.SIDE_DEBIT, "100.000000")
        for field in (
            "service_id",
            "account_id",
            "premises_id",
            "unit_id",
            "source_type",
            "source_id",
            "tax_authority_id",
        ):
            assert hasattr(line, field), f"r13 #1 dimension {field} missing from journal_lines"


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-003 — reversal links
# ═══════════════════════════════════════════════════════════════════════════
def test_us_led_003_tc3__an_entry_can_be_reversed_only_once(brazos, dana):
    """Ledger field map, r13 #2 row: the reversal link is *"once per entry"*.

    Two mirrors of one entry is the correction counted twice — LE-8's whole
    point is that the net effect stays right while all three entries survive.
    """
    with tenant_ctx(brazos):
        original = an_entry(brazos)
        an_entry(brazos, type=models.JE_REVERSING, reversal_of=original)
        with pytest.raises(IntegrityError), transaction.atomic():
            an_entry(brazos, type=models.JE_REVERSING, reversal_of=original)


def test_us_led_003_tc3__an_accrual_links_forward_to_its_mirror(brazos, dana):
    """r13 #2 gives TWO links and BR-LED-005 needs both directions.

    `reversal_of` is set on the mirror, pointing back. `auto_reverse_entry` is
    set on the ACCRUAL, pointing forward at the mirror BR-LED-005 posts on day
    1 of the next period (LE-4: Sep 30 JE-201 -> Oct 1 JE-202, "both linked").
    One column cannot carry both facts.
    """
    with tenant_ctx(brazos):
        accrual = an_entry(brazos, type=models.JE_ACCRUAL, entry_date=date(2026, 9, 30))
        mirror = an_entry(
            brazos,
            type=models.JE_REVERSING,
            entry_date=date(2026, 10, 1),
            reversal_of=accrual,
        )
        accrual.auto_reverse_entry = mirror
        accrual.save(update_fields=["auto_reverse_entry"])
        accrual.refresh_from_db()
        assert accrual.auto_reverse_entry_id == mirror.id
        assert mirror.reversal_of_id == accrual.id


# ═══════════════════════════════════════════════════════════════════════════
# BALANCE — live Postgres only (hard rule 5)
# ═══════════════════════════════════════════════════════════════════════════
def reach_commit():
    """Fire the DEFERRED constraint triggers without leaving the transaction.

    THIS CALL IS LOAD-BEARING AND THE TESTS ARE WORTHLESS WITHOUT IT. The
    balance triggers are DEFERRABLE INITIALLY DEFERRED, so they run at COMMIT
    — and pytest-django wraps every test in a transaction it ROLLS BACK, so a
    real COMMIT never happens. Written the obvious way, all four balance cases
    below pass while the trigger never fires once: the unbalanced ones by not
    raising (caught here as DID NOT RAISE), and the *balanced* one silently,
    which is the dangerous half — a green test asserting nothing.

    `SET CONSTRAINTS ALL IMMEDIATE` runs every pending deferred check right
    now. Same trigger, same entry, same verdict, one statement earlier.
    """
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


@requires_postgres
def test_us_led_001_tc5__the_database_refuses_an_unbalanced_posted_entry(brazos, dana):
    """CLAUDE.md rule 5, and US-LED-001 TC-5: *"unbalanced entry rejected by
    the B2 §3 constraint trigger — nothing partial lands"*.

    100.00 debit against 60.00 credit. Every individual statement succeeds —
    the refusal lands at the commit check, which is the only moment the whole
    entry exists to be judged.
    """
    with tenant_ctx(brazos):
        with pytest.raises(DatabaseError) as raised:
            with transaction.atomic():
                ar = an_account(brazos, code="1200")
                rev = an_account(brazos, code="4100", type_="revenue")
                entry = an_entry(brazos)
                a_line(brazos, entry, ar, models.SIDE_DEBIT, "100.000000")
                a_line(brazos, entry, rev, models.SIDE_CREDIT, "60.000000")
                post(entry)
                reach_commit()
        assert "UNBALANCED" in str(raised.value)
        assert "100.000000" in str(raised.value) and "60.000000" in str(raised.value)


@requires_postgres
def test_us_led_001_tc1__a_balanced_posted_entry_is_accepted(brazos, dana):
    """The other half of the proof: the trigger does not over-reach.

    A guard that refuses everything is not a guard, so the same fixture with
    100.00 against 100.00 must survive the same commit check.
    """
    with tenant_ctx(brazos):
        with transaction.atomic():
            ar = an_account(brazos, code="1200")
            rev = an_account(brazos, code="4100", type_="revenue")
            entry = an_entry(brazos)
            a_line(brazos, entry, ar, models.SIDE_DEBIT, "100.000000")
            a_line(brazos, entry, rev, models.SIDE_CREDIT, "100.000000")
            post(entry)
            reach_commit()
        entry.refresh_from_db()
        assert entry.status == models.JE_POSTED


@requires_postgres
def test_us_led_001_tc5__a_posted_entry_with_no_lines_is_refused(brazos, dana):
    """B2 §1: *journal_entry 1:N journal_lines (balanced)*.

    B2 §3's sketch fires per INSERTED LINE, so an entry with zero lines is
    never judged and 0 = 0 balances vacuously. The entry-side trigger closes
    it: an empty posted entry is not a journal entry.
    """
    with tenant_ctx(brazos):
        with pytest.raises(DatabaseError) as raised:
            with transaction.atomic():
                entry = an_entry(brazos)
                post(entry)
                reach_commit()
        assert "no lines" in str(raised.value)


@requires_postgres
def test_us_led_003_tc5__a_draft_may_sit_unbalanced_until_it_posts(brazos, dana):
    """BR-LED-003 verbatim: *"drafts freely editable/deletable before post;
    balanced required at post"*.

    A manual JE is authored one line at a time (S57). If the check bit on every
    insert, the first line of every entry would be illegal and no one could
    write a journal entry at all. So: one lonely debit, taken all the way
    through the commit check, and lawful.
    """
    with tenant_ctx(brazos):
        with transaction.atomic():
            ar = an_account(brazos, code="1200")
            entry = an_entry(brazos)
            a_line(brazos, entry, ar, models.SIDE_DEBIT, "100.000000")
            reach_commit()
        assert entry.lines.count() == 1  # unbalanced, un-posted, and lawful


# ═══════════════════════════════════════════════════════════════════════════
# APPEND-ONLY — live Postgres only (hard rule 4 / BR-LED-003)
# ═══════════════════════════════════════════════════════════════════════════
def _a_posted_entry(tenant):
    """A committed, balanced, posted entry: 100.00 DR AR / 100.00 CR revenue."""
    with transaction.atomic():
        ar = an_account(tenant, code="1200")
        rev = an_account(tenant, code="4100", type_="revenue")
        entry = an_entry(tenant)
        debit = a_line(tenant, entry, ar, models.SIDE_DEBIT, "100.000000")
        a_line(tenant, entry, rev, models.SIDE_CREDIT, "100.000000")
        post(entry)
        reach_commit()
    return entry, debit


@requires_postgres
def test_us_led_003_tc5__a_posted_journal_line_cannot_be_updated(brazos, dana):
    """US-LED-003 TC-5, first half. Hard rule 4.

    Not the ORM's refusal — the database's. `.update()` on a queryset issues
    raw SQL that no service guard and no model hook ever sees, which is exactly
    the door a data-fix script walks through.
    """
    with tenant_ctx(brazos):
        entry, debit = _a_posted_entry(brazos)
        with pytest.raises(DatabaseError) as raised, transaction.atomic():
            models.JournalLine.objects.filter(pk=debit.pk).update(amount=Decimal("1.000000"))
        assert "POSTED" in str(raised.value)
        debit.refresh_from_db()
        assert debit.amount == Decimal("100.000000")


@requires_postgres
def test_us_led_003_tc5__a_posted_journal_line_cannot_be_deleted(brazos, dana):
    """US-LED-003 TC-5, second half. Hard rule 4: corrections are new rows."""
    with tenant_ctx(brazos):
        entry, debit = _a_posted_entry(brazos)
        with pytest.raises(DatabaseError) as raised, transaction.atomic():
            models.JournalLine.objects.filter(pk=debit.pk).delete()
        assert "POSTED" in str(raised.value)
        assert models.JournalLine.objects.filter(pk=debit.pk).exists()


@requires_postgres
def test_us_led_003_tc5__a_line_cannot_be_appended_to_a_posted_entry(brazos, dana):
    """The quiet one. A BALANCED pair added to an already-posted entry passes
    the balance check and still changes money in a posted entry — which is the
    one thing hard rule 4 exists to prevent. So INSERT is blocked too."""
    with tenant_ctx(brazos):
        entry, _ = _a_posted_entry(brazos)
        extra = an_account(brazos, code="4200", type_="revenue")
        with pytest.raises(DatabaseError) as raised, transaction.atomic():
            a_line(brazos, entry, extra, models.SIDE_CREDIT, "5.000000")
        assert "POSTED" in str(raised.value)


@requires_postgres
def test_us_led_003_tc5__a_posted_entry_cannot_be_edited_or_deleted(brazos, dana):
    """BR-LED-003: an "edit" is a reverse + repost, never a change to this row.

    Three statements, all refused: moving the book date, un-posting, deleting.
    """
    with tenant_ctx(brazos):
        entry, _ = _a_posted_entry(brazos)
        for update in (
            {"entry_date": date(2026, 8, 31)},
            {"status": models.JE_DRAFT},
            {"memo": "rewritten"},
        ):
            with pytest.raises(DatabaseError) as raised, transaction.atomic():
                models.JournalEntry.objects.filter(pk=entry.pk).update(**update)
            assert "POSTED" in str(raised.value)
        with pytest.raises(DatabaseError), transaction.atomic():
            models.JournalEntry.objects.filter(pk=entry.pk).delete()
        entry.refresh_from_db()
        assert entry.entry_date == date(2026, 7, 31) and entry.status == models.JE_POSTED


@requires_postgres
def test_us_led_003_tc3__the_accrual_link_is_the_one_door_and_it_opens_once(brazos, dana):
    """BR-LED-005 — the mirror is created a period AFTER the accrual posted, so
    the forward link has to be writable on a posted row. Once."""
    with tenant_ctx(brazos):
        accrual, _ = _a_posted_entry(brazos)
        mirror = an_entry(brazos, type=models.JE_REVERSING, reversal_of=accrual)
        models.JournalEntry.objects.filter(pk=accrual.pk).update(auto_reverse_entry=mirror)
        accrual.refresh_from_db()
        assert accrual.auto_reverse_entry_id == mirror.id

        second = an_entry(brazos, type=models.JE_REVERSING)
        with pytest.raises(DatabaseError) as raised, transaction.atomic():
            models.JournalEntry.objects.filter(pk=accrual.pk).update(auto_reverse_entry=second)
        assert "written once" in str(raised.value)


@requires_postgres
def test_us_led_003_tc5__a_draft_entry_and_its_lines_edit_and_delete_freely(brazos, dana):
    """The other half again: BR-LED-003 gives drafts full freedom, and a guard
    that also froze drafts would make S57's manual JE unusable."""
    with tenant_ctx(brazos):
        with transaction.atomic():
            ar = an_account(brazos, code="1200")
            entry = an_entry(brazos)
            line = a_line(brazos, entry, ar, models.SIDE_DEBIT, "100.000000")
        models.JournalLine.objects.filter(pk=line.pk).update(amount=Decimal("205.000000"))
        line.refresh_from_db()
        assert line.amount == Decimal("205.000000")
        models.JournalLine.objects.filter(pk=line.pk).delete()
        models.JournalEntry.objects.filter(pk=entry.pk).delete()
        assert not models.JournalEntry.objects.filter(pk=entry.pk).exists()


@requires_postgres
def test_us_led_005_tc6__all_three_ledger_tables_carry_a_force_rls_policy(brazos):
    """CLAUDE.md rule 1. The G5 catalog sweep is the real gate; this is the
    named local check, so a `journal_lines` that lost its policy fails in the
    ledger's own file rather than only in a suite-wide list."""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relrowsecurity AND c.relforcerowsecurity "
            "AND c.relname IN ('ledger_accounts', 'journal_entries', 'journal_lines')"
        )
        guarded = {row[0] for row in cursor.fetchall()}
    assert guarded == {"ledger_accounts", "journal_entries", "journal_lines"}, (
        "ledger table(s) reached the schema without FORCE row-level security: "
        f"{sorted({'ledger_accounts', 'journal_entries', 'journal_lines'} - guarded)}"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-001@c7a1f30 (sha1[:7] of the four sources this slice was
#         authored from, concatenated in order:
#         02-database-design-brief.md — §2 ledger DDL + §3 RLS/balance
#         triggers + Addendum r13 — · EP-LED-01-posting-consumption.md ·
#         09-ledger/02-business-rules.md · 09-ledger/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W5 ledger journal-core schema slice)
# checklist: A✔ B✔ C✔ D=deferred(no API half) E=deferred(no UI half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: run on a LIVE Postgres cluster (config.settings.local) — the trigger
#         cases were each seen RED with the triggers dropped before being
#         trusted green (hard-won law 7)
# exceptions: this file asserts SCHEMA and DATABASE LAW only. The stamping of
#         dimensions (US-LED-002), the posting contracts themselves
#         (US-LED-001 TC-1..4/6), the sole-writer boundary (TC-5's first half)
#         and the tie-outs (US-LED-004) all belong to the posting service and
#         are NOT covered here · the trigger cases SKIP on SQLite by design: a
#         check that passes silently on the developer's own database is not a
#         check
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-001 (source-event posting contracts — the tables one
#           balanced entry is written INTO, and the DB half of its TC-5) ·
#           US-LED-003 (reversal pairs under append-only books — the
#           `reversal_of` link and the DB half of its TC-5) ·
#           US-LED-005 (chart of accounts: per-tenant unique codes,
#           deactivate-first) · US-LED-011 (the `JE-` number column stamped at
#           post — BR-LED-021) · US-LED-015 (`fiscal_period_closes`, the record
#           of which periods are shut) · US-LED-016 (`export_batches`, B2 r13 #4)
#           · US-LED-018 (`supplier_invoices` — the CAPTURED payable side:
#           supplier as FREE TEXT, an OPTIONAL volume with its explicit unit,
#           money NUMERIC(18,6)+CHAR(3)) · US-LED-019 (its void trail — void,
#           never delete)
#           Screens: S56 · S36 · S42 · S57 · S73
#           Other US-LED stories own columns that land here and are
#           deliberately NOT cited — see the docstring, where G10 reads prose
#           rather than a completion claim.
# Rules:    BR-LED-001 (every journal line carries its dimension set) ·
#           BR-LED-003 (posted entries are immutable; drafts are freely
#           editable; balanced required AT POST) · BR-LED-005 (accrual JEs
#           auto-reverse, linked both ways) · BR-LED-014 (export codes on the
#           GL mapping page) · BR-LED-015 (every finance action audits) ·
#           BR-LED-028 (capture, hold, reconcile, export — and process NOTHING:
#           no approvals, no payment runs, no vendor master, no ageing) ·
#           BR-LED-029 (what a captured supplier invoice holds) · BR-LED-030
#           (the volume is OPTIONAL) · BR-LED-033 (a captured volume carries an
#           EXPLICIT unit) · BR-LED-035 (void, never delete; reason required) ·
#           CLAUDE.md rule 2 (money NUMERIC(18,6) + CHAR(3)) · rule 4
#           (financial immutability) · rule 5 (balanced pairs; only the
#           posting service writes journal lines)
# Tests:    06-backend/tests/test_us_led_journal_core.py ·
#           06-backend/tests/test_us_led_011_manual_je.py ·
#           06-backend/tests/test_us_led_015_month_close.py ·
#           06-backend/tests/test_us_led_016_export.py ·
#           06-backend/tests/test_us_led_018_capture.py ·
#           06-backend/tests/test_us_led_019_register.py
# Impacts:  apps/billing (invoice_lines.gl_account_id / adjustments.
#           gl_account_id are plain uuids waiting on `ledger_accounts`) ·
#           apps/rating (taxes.liability_gl_account_id, same) ·
#           apps/ledger/posting.py (the sole writer, NOT built here)
# ───────────────────────────────────────────────────────
"""ledger models — the double-entry journal core, from B2 §2 as redlined by
Addendum r13 (the PO-approved ledger/Finance schema batch, 2026-08-08).

HUMAN-OWNED · HUMAN-REVIEW-PENDING — these three tables ARE the books, and
`journal_lines` is the row every money number in the product is eventually
summed from. AI-authored 2026-08-11 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

AMENDED 2026-08-11 (GL-designation lane): `ledger_accounts.designation` is
added here, and it is the one thing that lets a journal entry FIND its
accounts. PO ruling of the same day closing OQ-106 and OQ-110 — a designation
is an ATTRIBUTE on a ledger account (not rows in a designations table), the
LEDGER owns the GL maps, and there are ELEVEN of them. The values, the signed
seed chart they start on, and the reasoning live in `apps/ledger/chart.py`; the
column's own rules (uniqueness, the CHECK, why nothing is NOT NULL) are on
`LedgerAccount` below. The matching half — `revenue_account` /
`base_revenue_account` on the tenant's utility service — is a tenancy column,
because `tenant_services` is tenancy's table; `apps/ledger/selectors.py`
reaches it through a published tenancy read, never through tenancy's ORM.

WHAT THIS SLICE IS. Three tables and the laws the DATABASE can hold:
`ledger_accounts` · `journal_entries` · `journal_lines`. Nothing else. There is
no posting service here, no balance-computing Python, no tie-out view, no
export — this slice builds the surface CLAUDE.md rule 5 applies to, not the
service that rule names.

**AMENDED 2026-08-11 (posting-service lane) — the sentence above used to end
"`apps/ledger/posting.py` is still the NotImplementedError stub it was, and
CLAUDE.md rule 5's sole-writer boundary is a boundary this slice does not
implement", and BOTH halves are now out of date.** `apps/ledger/posting.py` is
built (US-LED-001/US-LED-003), and the sole-writer boundary is enforced by
`migrations/0004_posting_guard.py`: `journal_entries` and `journal_lines` refuse
an INSERT that did not come through `post()`. This slice still implements
neither — the correction is to the claim about the world, not to the claim about
this file. `journal_entries.posting_key` below arrived with that lane.

WHY NOW, stated because it is the reason the ordering is what it is:
`apps/billing/models.py` carries `invoice_lines.gl_account_id` as a plain
`uuid` and says so in its own comment — *"a plain uuid, not an FK:
`ledger_accounts` is W5 and does not exist"*. `apps/rating/models.py` carries
`taxes.liability_gl_account_id` the same way. Those columns are the B11 F-3
deferred-FK convention waiting for exactly this migration. Until it exists,
BR-BIL-011's "one bill = one balanced journal entry" has nothing behind it.

WHICH STORIES THIS HEADER CITES, AND WHICH IT DOES NOT. G10 reads a
Trace-header US-ID as "this file ships that story's test cases". Three stories
own columns that land here and are NOT cited, because none of their test cases
ships:

  * **US-LED-002** (dimension stamping) owns r13 #1 — `service`, `account_id`,
    `premises_id`, `unit_id`, `source_type`, `source_id`, `tax_authority_id` on
    every line. The COLUMNS are below. The stamping — resolving account → unit
    → premises at posting time, refusing a tax line with no authority — is the
    posting service's, and every one of US-LED-002's TCs asserts stamping.
  * **US-LED-006** (export codes) owns r13 #5 — `qbo_ref` / `xero_ref` on
    `ledger_accounts`. Columns below; the mapping page is not built.
  * **US-LED-011/012/013** (manual JE, accrual auto-reverse, reverse+repost)
    own r13 #2 — the JE `type`, the draft state and the two entry links. Same
    story: the columns are here, the lifecycle is not.

Schema law implemented here (signed, never invented):
- **B2 §2 ledger** — `ledger_accounts` · `journal_entries` · `journal_lines`,
  column for column, including `CHECK (amount >= 0)` and
  `UNIQUE (tenant_id, code)`.
- **B2 §3** — the RLS template and the `assert_balanced()` constraint trigger.
  Both live in `migrations/0002`, which is where they can actually bite.
- **Addendum r13 (PO-approved 2026-08-08)** — #1 the journal-line dimension
  set · #2 JE `type` (standard|accrual|reversing), the draft state, and the
  auto-reverse + reversal links · #5 `ledger_accounts.qbo_ref` / `.xero_ref`.
- **Addendum r9 #3** — `journal_entries.source_type` admits
  `'opening_balance'` (BR-CUS-049 / GT-16's cutover entry).
- **BR-LED-003 (PO LF-3, 2026-08-08)** — posted entries immutable, drafts
  freely editable/deletable, **balanced required AT POST**. That last clause is
  why the balance trigger is status-aware; see below.

────────────────────────────────────────────────────────────────────────────
BALANCE IS NOT IN THESE CLASSES, AND NEITHER IS IMMUTABILITY
────────────────────────────────────────────────────────────────────────────
Both live in the triggers `migrations/0002` installs. A Django model cannot
refuse a `.save()`, cannot see the other lines of an entry at save time, and is
bypassed entirely by a management command, a data fix, a `.update()` on a
queryset or a later migration. CLAUDE.md hard-won law 1 exists because a model
docstring once claimed a guarantee the schema did not have; this one claims the
opposite on purpose. **The fence is the database.** What is here is the shape
that fence is built around.

Three of the columns below are load-bearing for that fence, and they are the
reason two CHECK constraints exist:

  * `journal_lines.side` — the balance trigger sums
    `amount FILTER (WHERE side='debit')` against
    `amount FILTER (WHERE side='credit')`. A row with `side='dbit'` falls into
    NEITHER sum, so an entry holding it computes 0 = 0 and passes as balanced
    while real money sits in the books under an unreadable side. The CHECK is
    what makes the FILTER exhaustive.
  * `journal_entries.status` — the immutability and balance triggers both gate
    on `status = 'posted'`. A typo'd status is an entry that is never frozen
    and never balance-checked. Same CHECK, same reason.
  * `journal_lines.amount >= 0` — B2's own constraint. Sides carry direction;
    amounts never do, so a negative amount would be a second, invisible way to
    express a credit.

CURRENCY LIVES ON THE ENTRY (CLAUDE.md rule 2). `amount` is NUMERIC(18,6) and
its CHAR(3) partner is `journal_entries.currency`, not a per-line column —
following `invoices` / `invoice_lines`, where the document carries the currency
and the lines inherit it. There is a stronger reason here than consistency: a
journal entry that mixed currencies could not balance in any meaningful sense,
so one currency per entry is not a convenience, it is what "balanced" means.
"""

from django.db import models
from django.db.models import Q

from apps.ledger.chart import GL_DESIGNATIONS
from core.dbfields import uuid7_pk

#: B2 §1 `journal_side` — the two values, verbatim. Modelled as text with a
#: CHECK rather than a native enum, following the house pattern
#: (`invoices.status`, `adjustments.direction`), and load-bearing for the
#: balance trigger — see the module docstring.
SIDE_DEBIT = "debit"
SIDE_CREDIT = "credit"
JOURNAL_SIDES = (SIDE_DEBIT, SIDE_CREDIT)

#: Addendum r13 #2 — the JE types, enumerated exactly as the addendum states
#: them. `accrual` is the one BR-LED-005 auto-reverses on day 1 of the next
#: period; `reversing` is the mirror an accrual or a correction produces.
JE_STANDARD = "standard"
JE_ACCRUAL = "accrual"
JE_REVERSING = "reversing"
JE_TYPES = (JE_STANDARD, JE_ACCRUAL, JE_REVERSING)

#: Addendum r13 #2 gives `journal_entries` a "draft state"; BR-LED-003 gives it
#: its meaning — *"drafts freely editable/deletable before post; balanced
#: required at post"*, and once posted the entry is immutable (hard rule 4).
#: Two states, and the addendum names no third: an entry is either in the books
#: or it is not. "Edit a posted entry" is not a state, it is a reverse + repost
#: (BR-LED-003, LE-8), which is two more entries.
JE_DRAFT = "draft"
JE_POSTED = "posted"
JE_STATUSES = (JE_DRAFT, JE_POSTED)

#: EP-LED-02's S56 chart panel filters on these, and the finance-signed seed
#: chart needs all of them — 3000 Opening balance clearing is equity (LE-1),
#: which is the value B2's own `asset|liability|revenue|expense` comment was
#: missing when it still carried "UNKNOWN full COA (O-14)". O-14 is CLOSED
#: (r13 #7 / r16 #5). Not a DB CHECK: unlike `side` and `status`, nothing
#: structural reads this — it drives the trial-balance Type column.
#:
#: ⚠ **B2's DDL COMMENT IS NOW STALE BY TWO VALUES, NOT ONE, AND IS LEFT ALONE
#: DELIBERATELY.** It still reads `asset|liability|revenue|expense`, which has
#: been missing `equity` since the day it was written and is missing
#: `contra_revenue` as of 2026-09-01. The column it annotates is `text NOT
#: NULL` with no constraint, so the comment governs nothing and correcting it
#: is a change to a signed schema contract rather than a side effect of a lane
#: — REPORTED here, which is where a reader of this vocabulary will look.
#:
#: ⚠ **SIX SINCE 2026-09-01, AND IT READ FIVE FOR THE WHOLE LIFE OF THE
#: PRODUCT BEFORE THAT (CR-061, PO ruling).** PO verbatim: *"no, you cannot
#: file discount under revenue"* — said in answer to the question this
#: product's own review ledger had been holding open since 2026-08-28, which
#: asked in as many words *"is filing it under Revenue acceptable?"*. The
#: answer is no, so `contra_revenue` exists.
#:
#: **WHAT A CONTRA-REVENUE ACCOUNT IS, so the next reader does not have to
#: guess from the name:** a revenue account that runs the other way. It lives
#: in the revenue ladder, it carries a DEBIT balance, and it states a
#: reduction the utility GRANTED as its own figure rather than netting it
#: into what the utility EARNED. `4760 Customer discounts` is the only one
#: today. The PO's own reference chart (CR-061 §5) files six of them —
#: billing adjustment, leak adjustment, rate correction, customer credit,
#: refunds, bad-debt write-off — in a block called *Revenue Adjustments*,
#: every row marked **Normal Balance = Debit**, so this value is the shape
#: that whole block will take when it is sized and built.
#:
#: **NOT A DB CHECK, AND THAT IS WHY THIS WAS A ONE-LINE CHANGE.** `side` and
#: `status` are constrained in Postgres; `type` never has been, in any
#: `ledger/migrations/*`. Both gates on it are Python — `services._clean_type`
#: (a typed row) and `services.preview_chart_import` (a spreadsheet row) — and
#: both read this tuple, so a sixth value reaches them by being added here and
#: nowhere else. **No migration was written and none is needed.**
#:
#: ⚠ **ADDING A SEVENTH IS NOT FREE, AND THE THING TO CHECK IS THE ONE PLACE
#: THAT FILTERS ON A TYPE RATHER THAN PRINTING IT.** `reporting.revenue_by_
#: service` selects the lines a revenue report is built from. Every other
#: reader of this column — the trial balance, `gl_totals`, the accounting
#: export, the chart list — carries the string through as a LABEL and does no
#: arithmetic with it, so a new value shows up there and changes no figure. In
#: `revenue_by_service` a value this tuple knows and that function does not is
#: money silently leaving a report. See `REVENUE_REPORTING_TYPES`.
LEDGER_ACCOUNT_TYPES = (
    "asset",
    "liability",
    "equity",
    "revenue",
    "contra_revenue",
    "expense",
)

#: The account types whose lines ARE revenue for reporting — revenue and the
#: contra-revenue that reduces it. **This is the seam CR-061 turns on** and it
#: is declared here, beside the vocabulary, rather than inside the report that
#: reads it, so the next type added has to look at it.
#:
#: **WHY IT IS TWO NAMES AND NOT ONE.** Before 2026-09-01, `4300 Customer
#: discounts` was typed `revenue`, so the discount's 10.00 DEBIT was picked up
#: by `revenue_by_service`'s `type="revenue"` filter and correctly reduced
#: reported revenue. Re-typing it to `contra_revenue` and changing nothing
#: else would have dropped that line from the filter, and the S36 revenue
#: table, the *Revenue by service and rate* report and the dashboard's service
#: mix would every one of them have reported **10.00 MORE revenue than the
#: books hold**, on a bill whose journal entry did not move by a cent. That is
#: the "a sixth type half the surfaces do not know about is worse than five"
#: failure, and it is the only place in the product where it could happen.
REVENUE_REPORTING_TYPES = ("revenue", "contra_revenue")


class LedgerAccount(models.Model):
    """One line of the tenant's chart of accounts (B2 §2; r13 #5).

    `code` is UNIQUE per tenant and nothing more — two tenants may both run a
    `4100`, which is US-LED-005 TC-6 and the reason the unique constraint
    leads with `tenant`.

    Soft-deleted via `deleted_at`, never hard-deleted while referenced: IS-1's
    deactivate-first, and CLAUDE.md rule 4's reasoning applied to the chart
    itself — an account a journal line points at is part of a financial record.
    The REFERENCE COUNT that drives that lock is a query, not a column, and it
    is US-LED-005's service work, not this slice's.

    ── `designation`: WHAT IT IS, AND WHY IT IS A COLUMN ────────────────────
    PO ruling 2026-08-11 (OQ-106): a GL designation is an **ATTRIBUTE (a
    field)**, not rows in a designations table — *"option A"*, chosen so that
    *"which account IS accounts receivable"* is **unambiguous at posting
    time**. The eleven values are the PO's own enumeration (OQ-110, option A)
    and live in `apps/ledger/chart.py`.

    **CAN TWO ACCOUNTS CARRY THE SAME DESIGNATION? NO — and this class
    enforces it.** The reading is taken straight from the reason the PO gave
    for choosing a field over a table: a table permits N rows per designation,
    and "the AR account" then has to be disambiguated by something, at the
    moment a journal entry is being written. A field with no uniqueness rule
    reintroduces exactly that ambiguity through the back door — two accounts
    both designated `accounts_receivable` and a posting service picking one by
    `ORDER BY` accident. `uq_ledger_accounts_designation` is therefore a
    PARTIAL unique index: one live account per designation per tenant.

    Three deliberate properties of that constraint:

      * **`WHERE designation IS NOT NULL`** — most of the chart carries no
        designation at all (4100 is a revenue account a SERVICE points at, not
        a designated one), and a plain UNIQUE would allow exactly one
        undesignated account per tenant.
      * **`AND deleted_at IS NULL`** — IS-1 is deactivate-first, so re-pointing
        `accounts_receivable` from a deactivated 1200 to a new 1150 must be
        possible. Including soft-deleted rows would freeze a designation onto a
        dead account forever. `apps/ledger/selectors.py` filters the same way,
        so the constraint and the read agree on what "the AR account" means.
      * **A CHECK against the eleven.** A designation is resolved BY NAME, so a
        row designated `accounts_recievable` is an account nothing will ever
        find — the same silent hole `ck_journal_lines_side` closes for `side`,
        and closed the same way.

    Nothing here makes a designation REQUIRED. The seed points each one at its
    signed account (`apps/ledger/services.seed_chart_of_accounts`), and
    US-LED-005 leaves the chart the tenant's to re-point afterwards; a NOT NULL
    would be a claim about a tenant's chart that this product does not get to
    make.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    code = models.TextField()  # '1200', '4100', '6900'
    name = models.TextField()
    type = models.TextField()  # LEDGER_ACCOUNT_TYPES
    #: PO ruling 2026-08-11 (OQ-106 shape, OQ-110 enumeration) — see the class
    #: docstring. NULL for the great majority of the chart; at most one live
    #: account per tenant may carry any given value.
    designation = models.TextField(null=True, blank=True)  # chart.GL_DESIGNATIONS
    #: **CR-061 statement (1), PO 2026-09-01** — *"actually you need more GL code
    #: s and categories, I tried to assigned using existing code, they are not
    #: sufficiencnt"*. The chart HEADING this account is read under, one of
    #: `chart.CHART_CATEGORIES`.
    #:
    #: ⚠ **IT IS A GROUPING AND NEVER A POINTER, WHICH IS WHY IT CARRIES NO
    #: DATABASE `CHECK` WHERE `designation` DOES.** Nothing resolves an account
    #: by category, no money lands because of one, and `chart.py`'s own warning
    #: on `GL_DESIGNATIONS` says what a CHECK costs: Django INLINES the values
    #: into the constraint, so adding one needs a migration (`ledger/0006` is
    #: the one that paid for the twelfth designation). An eighteenth category is
    #: a one-line change in `chart.py` instead. Validated in Python by
    #: `services._clean_category`, the same posture `type` has carried since
    #: `LEDGER_ACCOUNT_TYPES` was written.
    #:
    #: NULL is lawful and means *uncategorised* — what a tenant's own hand-added
    #: account carries until somebody files it, and what EVERY account on a
    #: database provisioned before 2026-09-02 carries, because nothing
    #: backfills (hard-won law 4: a seed change never reaches a tenant that
    #: already has a chart). A screen renders that as its own group rather than
    #: hiding the row.
    category = models.TextField(null=True, blank=True)  # chart.CHART_CATEGORIES
    #: r13 #5 / BR-LED-014 — the target system's own account ref, carried so an
    #: export can name the account QuickBooks or Xero knows it by. Nullable:
    #: a tenant that never exports never fills these in, and BR-LED-014 makes
    #: them required PER TARGET AT EXPORT, which is US-LED-016's check, not a
    #: NOT NULL here.
    qbo_ref = models.TextField(null=True, blank=True)
    xero_ref = models.TextField(null=True, blank=True)
    #: **`CR-196-BRC10`, our judgment 5a (decision log 2026-10-29).** The code
    #: this account was SEEDED or MINTED under — `4150`, `2200-01` — and nothing
    #: else. Since the PO's ruling of that day a System Admin may change `code`
    #: even on a used account, so the code stopped being a stable name for "the
    #: seeded Solar account". This column is that name.
    #:
    #: ⚠ **INTERNAL. NEVER ON THE WIRE, NEVER ON A SCREEN, NEVER CHANGED BY A CODE
    #: EDIT.** Two readers, and only two: the seed (`services._create_missing_
    #: accounts` skips a seed row whose key is already held, so the reference
    #: sweep that runs on every `migrate` does not mint an empty duplicate `4150`
    #: beside a renamed one) and the tax-liability test (`chart.is_tax_payable_
    #: account` — a 2200-series key is tax whatever the code now reads). NULL on
    #: an account a human typed or imported. Back-filled by `ledger/0021`.
    seed_key = models.TextField(null=True, blank=True)
    #: **`CR-196-BRC10` (4)** — every change of `code`, oldest first:
    #: `{"old_code", "new_code", "changed_at", "changed_by"}`. Append-only by the
    #: one writer (`services.change_account_code`). On the ACCOUNT and not only
    #: in `audit_log`, because `audit_log` is pruned on its retention schedule
    #: (PO 2026-09-23, OQ-1340) and *"formerly 4150"* must not silently vanish
    #: from the chart a year later.
    code_history = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)  # IS-1 deactivate-first

    class Meta:
        db_table = "ledger_accounts"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="uq_ledger_accounts_code"),
            # CR-196-BRC10 — one account per seed slot per tenant, live or
            # retired, exactly as the code index counts retired rows.
            models.UniqueConstraint(
                fields=["tenant", "seed_key"],
                condition=Q(seed_key__isnull=False),
                name="uq_ledger_accounts_seed_key",
            ),
            # One LIVE account per designation per tenant — see the docstring.
            models.UniqueConstraint(
                fields=["tenant", "designation"],
                condition=Q(designation__isnull=False) & Q(deleted_at__isnull=True),
                name="uq_ledger_accounts_designation",
            ),
            # A designation is resolved BY NAME; a typo'd one is an account
            # nothing can ever find.
            models.CheckConstraint(
                condition=Q(designation__isnull=True) | Q(designation__in=GL_DESIGNATIONS),
                name="ck_ledger_accounts_designation",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "type"], name="ix_ledger_accounts_type"),
            # The posting service's own lookup: designation -> account, per
            # tenant, on every entry it writes.
            models.Index(fields=["tenant", "designation"], name="ix_ledger_accounts_desig"),
        ]


class JournalEntry(models.Model):
    """One journal entry — the header of a balanced pair (B2 §2; r13 #2).

    `entry_date` is the BOOK date and `posted_at` is the wall-clock moment the
    entry entered the books. They are different facts and LE-9 is the reason
    both are kept: July closes on Aug 5; on Aug 7 a payment dated Jul 30
    arrives and posts *into August* with an audit note. `entry_date` is what
    the trial balance groups by; `posted_at` is what answers "when did this
    become immutable".

    `source_type` + `source_id` are the polymorphic reference B2 §2 specifies
    ("validated in app; see O-4"). O-4's integrity approach is an OPEN
    Eng-Lead residue (r16 #5) and is NOT resolved here — the column ships in
    exactly the shape B2 signs, with no FK and no chosen vocabulary. r9 #3 adds
    `'opening_balance'` to the values it must admit (BR-CUS-049 / GT-16).

    `posting_key` is the PER-SOURCE POSTING GUARD (hard rule 6). Added
    2026-08-11 by the posting-service lane; the RULE is US-LED-001 TC-6 (*"the
    same issue handoff replayed twice → second replay no-ops … one entry,
    ever"*) and GT-16 (*"re-posting the same batch is idempotent"*), and the
    MECHANICS are the ones B2 r13 #8 delegates (*"posting-service mechanics =
    Eng-Lead 🔒"*). It is an EXTENSION beyond B2 §2's literal DDL, which gives
    `journal_entries` no unique key at all — DB-12 lists idempotency uniques for
    bill runs, payment webhooks, imports and export batches and NOT for the
    journal. Stated here rather than discovered: the column is nullable because
    an entry with no upstream source event (a manual JE, EP-LED-04) has no
    replay to guard against, and `uq_journal_entries_posting_key` is therefore
    PARTIAL — a plain UNIQUE would allow exactly one keyless entry per tenant.
    `apps/ledger/posting.py` composes the string and is the only writer of it.

    TWO LINKS, NOT ONE (r13 #2: *"auto_reverse link + reversal_of link"*). They
    answer different questions and one column cannot carry both:
      * `reversal_of` — set on the MIRROR, pointing back at what it reverses.
        A correction, an NSF, a void, a one-click reverse+repost (LE-8).
      * `auto_reverse_entry` — set on the ACCRUAL, pointing FORWARD at the
        mirror BR-LED-005 posts on day 1 of the next period (LE-4: Sep 30
        JE-201 accrual → Oct 1 JE-202, *"both linked"*). Written after the
        accrual is already posted, which is why the immutability trigger has
        to leave exactly this one door open.
    Both are UNIQUE where set: one mirror per entry, ever. LE-4's whole point
    is *"no double-count"*, and a second auto-reversal of one accrual is a
    double-count with a link to prove it.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    entry_date = models.DateField()  # the BOOK date (B2 §2)
    type = models.TextField(default=JE_STANDARD)  # r13 #2 — JE_TYPES
    status = models.TextField(default=JE_DRAFT)  # r13 #2 draft state — JE_STATUSES
    source_type = models.TextField(null=True, blank=True)  # 'invoice'|'payment'|… + r9 #3
    source_id = models.UUIDField(null=True, blank=True)  # polymorphic (B2 §2, O-4 residue)
    #: The per-source posting guard (hard rule 6; US-LED-001 TC-6 / GT-16).
    #: Written ONLY by `apps/ledger/posting.py`, which composes it. NULL for an
    #: entry with no upstream source event to replay — see the class docstring.
    posting_key = models.TextField(null=True, blank=True)
    #: BR-LED-021 (PO 2026-08-12, OQ-176 — *"Approve a JE- series"*). The
    #: human-readable number a finance officer can read aloud, quote in an email
    #: and find again, where the S56 list showed
    #: `019ff23d-13ee-7aba-a280-58058e492cb9` and three ratified documents say
    #: **JE-104** (LE-8) or **JE-201/JE-202** (LE-4).
    #:
    #: NULLABLE, and that is the ruling rather than a convenience: the number is
    #: allocated per tenant from the ninth `number_series` (BR-TEN-035) and
    #: **stamped when the entry POSTS — a DRAFT has NO number.** So it is NULL
    #: for the whole of a draft's life and for any entry posted while the
    #: tenant's `journal_entry` series row is missing (see
    #: `apps/ledger/manual_je.py`, which reports that gap rather than faking a
    #: number — the `numbering_series_missing` precedent of
    #: `apps/metering/services.py`).
    #:
    #: ⚠ **TWO CLAUSES OF BR-LED-021 ARE FLAGGED OPEN AND ARE NOT RESOLVED BY
    #: THIS COLUMN.** (a) The decision-log row justifies the post-time stamp as
    #: *"exactly as a draft bill does under BR-BIL-063"* and BR-BIL-063 says the
    #: OPPOSITE — a bill number is allocated at DRAFT CREATION. The rule AS
    #: RULED (number at post) is what is built; the analogy is backwards and both
    #: documents cannot be right. (b) The row calls the series *"gapless"* while
    #: BR-TEN-035 allocates from a monotonic counter where *"gaps ok, never
    #: reused"* — a rolled-back post consumes a number under one and must not
    #: under the other. This column is written by BR-TEN-035's allocator, so
    #: GAPS HAPPEN; that is the behaviour, stated so it is not discovered.
    number = models.TextField(null=True, blank=True)
    memo = models.TextField(null=True, blank=True)
    #: CLAUDE.md rule 2's CHAR(3) partner for every `amount` on this entry's
    #: lines. On the entry rather than the line: a mixed-currency entry cannot
    #: balance, so one currency per entry is what "balanced" means.
    #:
    #: ⚠ **THE `default="USD"` IS GONE (`P0.7`, 2026-09-24), AND IT WAS NOT
    #: HARMLESS.** The database column has been `NOT NULL` with no default for
    #: as long as it has existed — measured — so the default lived only in
    #: Python, where it meant *"a caller that forgets the currency silently
    #: gets US dollars"*. For a CAD utility that is its books quietly becoming
    #: USD, one entry at a time, with every total still footing and hard rule 4
    #: making each one permanent.
    #:
    #: `PostingRequest.currency` has never had a default, deliberately and for
    #: this exact reason (*"the source document always has one, and a defaulted
    #: currency is how a CAD tenant's books quietly become USD"*). This column
    #: now agrees with it: the caller says, or the write fails.
    #:
    #: **`posting._refuse_unless_postable` additionally requires it to equal
    #: the TENANT's currency**, and `tenancy/0050` makes it a foreign key into
    #: `currencies` — so a code that names no currency at all is refused by the
    #: database as well. Three layers, each catching what the others cannot:
    #: the missing value, the wrong value, and the impossible value.
    currency = models.CharField(max_length=3)
    reversal_of = models.ForeignKey(  # r13 #2 — set on the MIRROR
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversed_by",
        db_column="reversal_of",
    )
    auto_reverse_entry = models.ForeignKey(  # r13 #2 — set on the ACCRUAL
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="auto_reverses",
        db_column="auto_reverse_entry_id",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "journal_entries"
        indexes = [
            # The trial balance's own grouping (BR-LED-009, S56).
            models.Index(fields=["tenant", "entry_date"], name="ix_journal_entries_date"),
            # "Show me the entry this invoice produced" — drill-back, and the
            # posting service's own replay check.
            models.Index(
                fields=["tenant", "source_type", "source_id"], name="ix_journal_entries_source"
            ),
            models.Index(fields=["tenant", "status"], name="ix_journal_entries_status"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=JE_STATUSES), name="ck_journal_entries_status"
            ),
            # "once per entry" (ledger field map, r13 #2 row) — one mirror,
            # one accrual reversal, never two.
            models.UniqueConstraint(
                fields=["reversal_of"],
                condition=Q(reversal_of__isnull=False),
                name="uq_journal_entries_reversal",
            ),
            models.UniqueConstraint(
                fields=["auto_reverse_entry"],
                condition=Q(auto_reverse_entry__isnull=False),
                name="uq_journal_entries_autorev",
            ),
            # Hard rule 6, in the DATABASE. US-LED-001 TC-6 says "one entry,
            # ever"; a service-layer look-before-insert loses that race under
            # two workers, and the books would then hold the same bill twice.
            # PARTIAL: a keyless entry (manual JE) has no replay to guard.
            models.UniqueConstraint(
                fields=["tenant", "posting_key"],
                condition=Q(posting_key__isnull=False),
                name="uq_journal_entries_posting_key",
            ),
            # BR-LED-021 / BR-TEN-035: *"a number is NEVER reused"*. PARTIAL,
            # because every draft carries NULL and a plain UNIQUE would allow
            # exactly one draft per tenant, ever — the same trap
            # `uq_journal_entries_posting_key` sidesteps for the same reason.
            models.UniqueConstraint(
                fields=["tenant", "number"],
                condition=Q(number__isnull=False),
                name="uq_journal_entries_number",
            ),
        ]


class JournalLine(models.Model):
    """One side of a balanced pair (B2 §2; r13 #1 dimensions).

    `side` + a non-negative `amount` — never a signed amount. Direction is a
    column, so there is exactly one way to express a credit.

    THE DIMENSION SET (r13 #1 / BR-LED-001) is the whole of the product's
    reporting model: S36's KPI strip, the trial-balance expansion, the
    remittance report, the by-premises summary and every export drill-back are
    *the same query grouped differently* (BR-REP-002 — never a side-maintained
    number). That is why the dimensions live on the LINE and not on the entry:
    one entry's lines span several services, several authorities and — on a
    master-account transfer — two accounts.

    All seven are nullable at the schema level, and that is deliberate rather
    than lax. BR-LED-001 makes each one required *where it applies*: `service`
    is meaningless on a cash line, `tax_authority_id` is required only on tax
    lines (US-LED-002 TC-5), and the account → unit → premises chain is
    resolved AT POSTING. Encoding "required where applicable" as NOT NULL would
    forbid the lawful lines; the posting service is where US-LED-002 TC-5's
    "posting fails atomically naming the gap" belongs. **AMENDED 2026-08-11:
    that sentence used to end "and it is not built" — the posting service now
    exists and requires `source_type` + `source_id` on every line, but it still
    does NOT resolve the account → unit → premises chain (no published customers
    or metering read exists) and does not refuse an unauthorised tax line —
    [CORRECTED 2026-08-11: that clause read "(that needs OQ-116)" and OQ-116 is
    CLOSED. An invoice line names its tax now (`invoice_lines.tax_id`,
    BR-BIL-069), so the fact exists; the refusal waits on the stage-7 handoff,
    which nothing emits]. US-LED-002 remains unbuilt; the columns remain
    nullable.**

    The FKs to `customers`, `metering`, `tenancy` and `rating` are CROSS-MODULE
    (⚠ below) and are ADDITIONS to B2 §2's reviewed interface set — r16 #7
    puts such additions on the register "at DDL time", and this is that time.
    They are FKs rather than plain uuids because every target table already
    exists; the B11 F-3 deferred-uuid convention applies only where it does
    not. `on_delete=PROTECT` throughout: US-LED-002 TC-4 requires a historical
    line to keep its stamped premises/unit forever, and a real FK is what makes
    "forever" the database's problem rather than a convention.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    journal_entry = models.ForeignKey(
        JournalEntry, on_delete=models.PROTECT, related_name="lines", db_column="journal_entry_id"
    )
    ledger_account = models.ForeignKey(
        LedgerAccount, on_delete=models.PROTECT, db_column="ledger_account_id"
    )
    side = models.TextField()  # JOURNAL_SIDES — load-bearing, see the docstring
    amount = models.DecimalField(max_digits=18, decimal_places=6)  # >= 0 (B2 §2)

    # ── r13 #1 · the dimension set (BR-LED-001) ────────────────────────────
    service = models.ForeignKey(  # ⚠ cross-module FK → tenancy (r16 #7 addition)
        "tenancy.Service",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="service_id",
    )
    account = models.ForeignKey(  # ⚠ cross-module FK → customers (r16 #7 addition)
        "customers.Account",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="account_id",
    )
    premises = models.ForeignKey(  # ⚠ cross-module FK → metering (r16 #7 addition)
        "metering.Premises",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="premises_id",
    )
    unit = models.ForeignKey(  # ⚠ cross-module FK → metering (r16 #7 addition)
        "metering.Unit",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="unit_id",
    )
    #: ══════════════════════════════════════════════════════════════════
    #: WHO HELD THE ACCOUNT WHEN THIS LINE WAS POSTED — `P0.1` (ledger/0017)
    #: ══════════════════════════════════════════════════════════════════
    #: **THE LINE NAMES THE CUSTOMER, AND THE CUSTOMER IT NAMES NEVER MOVES.**
    #: Until 2026-09-24 this table carried an `account` and nothing else, so
    #: *"what did Rosa Pemberton owe us in August?"* could only be answered by
    #: walking `journal_lines → accounts → customer_accounts` and reading **who
    #: holds that account NOW**. A property sale or a move-in reassigns that
    #: link (`BR-CUS-1030`, `CustomerAccount.ended_at`), and every historical
    #: line then silently re-attributes itself to the new holder. Nothing goes
    #: red; the figures still foot; they are simply about the wrong person.
    #:
    #: ⚠ **THAT IS A HARD RULE 4 PROBLEM WEARING A JOIN'S CLOTHES.** A posted
    #: line is immutable, so a fact it reports has to be immutable too — and a
    #: fact you must RE-DERIVE from a mutable link is not recorded at all.
    #: Stamping it at post is what turns *"the customer who held the account
    #: then"* into a stored fact rather than a query that changes its mind.
    #:
    #: **NULLABLE, AND EVERY ROW WRITTEN BEFORE THIS COLUMN READS NULL.** There
    #: is no backfill and there must not be one: hard rule 4 forbids UPDATEing
    #: an issued journal line, and the only available source for a historical
    #: value would be today's link — the exact reading this column exists to
    #: stop trusting. So NULL means *"posted before the stamp existed; ask the
    #: account, and know what you are getting"*, and it is a real state every
    #: reader must handle. When this column landed: **661 of 661 live lines.**
    #:
    #: **PROTECT, like every other dimension on this line.** US-LED-002 TC-4
    #: requires a historical line to keep what it was stamped with forever, and
    #: a real FK is what makes "forever" the database's problem rather than a
    #: convention. A customer who has ever been on a posted line can no longer
    #: be deleted — the correct answer, and the same one `account`, `premises`
    #: and `unit` already give.
    #:
    #: ⚠ Cross-module FK → `customers` (r16 #7 addition to B2 §2's reviewed
    #: interface set), on exactly the same footing as the four beside it.
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
        db_column="customer_id",
    )
    #: Per-LINE source, distinct from the entry's: one issue entry's lines
    #: trace to individual `invoice_line` rows (US-LED-002 TC-1), which is what
    #: makes the S42 drill-back answer "what is the 506.31?" (LE-5).
    source_type = models.TextField(null=True, blank=True)
    source_id = models.UUIDField(null=True, blank=True)
    tax_authority = models.ForeignKey(  # ⚠ cross-module FK → rating (r16 #7 addition)
        "rating.TaxJurisdiction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="tax_authority_id",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "journal_lines"
        indexes = [
            models.Index(fields=["tenant", "journal_entry"], name="ix_journal_lines_entry"),
            # Trial balance: Σ per GL per period (BR-LED-009).
            models.Index(fields=["tenant", "ledger_account"], name="ix_journal_lines_gl"),
            # Account ledger S59 (BR-LED-010) and the AR tie-out (BR-LED-007).
            models.Index(fields=["tenant", "account"], name="ix_journal_lines_account"),
            # By-premises summary S60 (BR-LED-011).
            models.Index(fields=["tenant", "premises"], name="ix_journal_lines_premises"),
            models.Index(
                fields=["tenant", "source_type", "source_id"], name="ix_journal_lines_source"
            ),
            # ── CR-060 T8 · the three dimensions with no COMPOSITE index ───
            # r13 #1 gives this table FIVE dimensions and only two of them —
            # `account` and `premises` — had a (tenant, dimension) index.
            # CR-060 §0c finding 2 corrects the source document from one
            # unindexed dimension to three, and ledger/0010 corrects §0c in
            # turn: these were NOT sequential scans. Django indexes every FK,
            # so a dimension statement index-scanned ONE of its two columns and
            # filtered the other — 690 rows read to return 194, measured.
            #
            # Same shape as the four above on purpose — (tenant, dimension),
            # unconditional — so a reviewer compares seven identical things
            # rather than four of one kind and three of another. A PARTIAL
            # index (`WHERE <dim>_id IS NOT NULL`) was considered and NOT
            # taken; what each one holds today is measured in the migration's
            # docstring, and `tax_authority` is the one to read there.
            models.Index(fields=["tenant", "unit"], name="ix_journal_lines_unit"),
            # The service dimension: "the segment most utilities report on"
            # (CR-060 §0c) — `reporting.revenue_by_service` (LE-2).
            models.Index(fields=["tenant", "service"], name="ix_journal_lines_service"),
            # Tax by authority (LE-3). ⚠ NOTHING WRITES THIS COLUMN YET —
            # `reporting.py`'s own stated absence says rating publishes no
            # `tax_authority_id_for_tax`, so every line carries NULL. The index
            # is laid now because the table is small now; it serves the read
            # the day CR-060 C19/T7d fills the column, and not before.
            models.Index(fields=["tenant", "tax_authority"], name="ix_journal_lines_tax_authority"),
            # ── P0.1 · the SIXTH dimension ────────────────────────────────
            # Same shape as the six above — (tenant, dimension), unconditional
            # — so a reviewer compares seven identical things rather than six
            # of one kind and one of another. It serves the customer statement
            # (`/reports/customer-statement`, which today joins through
            # `accounts`) and the P4 debtor reads.
            #
            # ⚠ **IT HOLDS NOTHING ON THE DAY IT IS LAID, AND THAT IS STATED
            # RATHER THAN DISCOVERED** — exactly as `ix_journal_lines_tax_
            # authority` above was, for the same reason. `P0.3` is what starts
            # filling it; until then every row is NULL and the index is empty.
            # It is laid now because the table is small now: on a partitioned
            # parent `CREATE INDEX` takes an ACCESS EXCLUSIVE lock on every
            # partition, and doing it at 661 rows costs nothing.
            models.Index(fields=["tenant", "customer"], name="ix_journal_lines_customer"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="ck_journal_lines_amount_ge0"),
            models.CheckConstraint(
                condition=Q(side__in=JOURNAL_SIDES), name="ck_journal_lines_side"
            ),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-015 — the month close (BR-LED-006 · BR-LED-018 · BR-TEN-038)
# ═══════════════════════════════════════════════════════════════════════════
#: The two states a fiscal period can be in. A period with NO row here has never
#: been closed and is therefore OPEN — absence is the open state, so a tenant who
#: has never closed anything carries no rows rather than twelve.
PERIOD_OPEN = "open"
PERIOD_CLOSED = "closed"
PERIOD_STATES = (PERIOD_OPEN, PERIOD_CLOSED)


class FiscalPeriodClose(models.Model):
    """Whether one fiscal period is CLOSED, and what was true when it was.

    **WHY THIS TABLE EXISTS AT ALL.** `apps/ledger/posting.py` said it plainly
    on 2026-08-11: *"`tenant_settings.lock_closed_periods` is a boolean and
    there is no record of which periods are closed — no fiscal period table
    exists anywhere in the schema. US-LED-015 owns close."* This is that record.
    B2 names no such table; the field map delegates it — *"Close / reopen
    actions + period lock | fiscal period close state (**storage mechanics
    🔒**)"* — so the shape below is authored under the same B2 r13 #8 delegation
    that produced `journal_entries.posting_key`, and is REPORTED as an extension
    beyond B2 §2's literal DDL rather than presented as signed schema.

    **THE PERIOD IS NOT STORED AS A NAME.** `period_start` / `period_end` are
    the two dates BR-TEN-022 computes from the tenant's fiscal settings
    (`apps.tenancy.selectors.current_period`), so a tenant on quarterly close
    and a tenant on monthly close both fit and neither has to be parsed out of
    a label. The pair is UNIQUE per tenant: a period is closed once at a time.

    **ONE ROW PER PERIOD, AND THE TRAIL IS `audit_log`.** A reopen flips
    `status` back to `open` on the same row rather than appending a second one,
    because the signed field map puts the history exactly where hard rule 7 puts
    it: *"Audit | `audit_log` `period.closed`/`period.reopened`"*. The row
    answers *"is July closed?"* in one indexed read on the posting path; the
    append-only ledger answers *"who closed it, when, and why over which
    incomplete items"* forever. Keeping the state in the row and the history in
    audit_log is what stops a close/reopen/close cycle from needing a
    self-joining query on the one table the posting service consults per entry.

    **`incomplete_items` IS THE WARN+CONFIRM RECEIPT (BR-LED-018).** A close
    over an incomplete checklist is lawful — *"Finance may close anyway with
    reason (audited) — never a silent close, never a hard lockout"* — so the
    items that were incomplete AT CLOSE are snapshotted here beside the reason.
    Recomputing them later would answer a different question: the registers move
    on, and J19 step 1's *"reason + incomplete-item snapshot recorded on the
    close"* is a statement about the moment, not about now.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    period_start = models.DateField()
    period_end = models.DateField()
    status = models.TextField(default=PERIOD_CLOSED)  # PERIOD_STATES
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by_user_id = models.UUIDField(null=True, blank=True)
    #: BR-LED-018's confirm reason. REQUIRED when anything on the checklist is
    #: incomplete and optional otherwise — the service decides, not the column,
    #: because "no reason given" and "nothing to explain" are the same NULL.
    close_reason = models.TextField(null=True, blank=True)
    #: The checklist items that were NOT complete at the moment of close, as
    #: `[{"code": …, "label_key": …, "detail": …}]`. `[]` = a clean close.
    incomplete_items = models.JSONField(default=list, blank=True)
    reopened_at = models.DateTimeField(null=True, blank=True)
    reopened_by_user_id = models.UUIDField(null=True, blank=True)
    reopen_reason = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fiscal_period_closes"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "period_start", "period_end"],
                name="uq_fiscal_period_closes_period",
            ),
            models.CheckConstraint(
                condition=Q(status__in=PERIOD_STATES), name="ck_fiscal_period_closes_status"
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=models.F("period_start")),
                name="ck_fiscal_period_closes_window",
            ),
        ]
        indexes = [
            # The posting path's own question: "which periods of this tenant are
            # closed right now?" — asked once per money event (BR-TEN-038).
            models.Index(fields=["tenant", "status"], name="ix_fiscal_period_closes_state"),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-016 — the accounting export (BR-LED-004 · BR-LED-017 · B2 r13 #4)
# ═══════════════════════════════════════════════════════════════════════════
#: The four targets BR-LED-004 names, verbatim: *"QBO/Xero/CSV/IIF"*.
EXPORT_QBO = "qbo"
EXPORT_XERO = "xero"
EXPORT_CSV = "csv"
EXPORT_IIF = "iif"
EXPORT_TARGETS = (EXPORT_QBO, EXPORT_XERO, EXPORT_CSV, EXPORT_IIF)

#: BR-LED-017, PO L-1 (*"keep it flexible"*): one summary JE per CLOSED period
#: (the default) OR weekly JEs over that closed period — chosen PER EXPORT, and
#: both idempotent per covered window. The granularity changes how many journal
#: rows the ERP receives; it never changes WHICH window was handed over, which
#: is why it is not part of the idempotency key (T5-07 step 3).
EXPORT_SUMMARY = "summary"
EXPORT_WEEKLY = "weekly"
EXPORT_GRANULARITIES = (EXPORT_SUMMARY, EXPORT_WEEKLY)


#: `P5.4` — what an accounting package's operator can tell us about a handover.
#:
#: ⚠ **THREE VALUES AND NOT FOUR.** There is no `pending`: a batch nobody has
#: answered for carries `ack_state = NULL`, and that is a different fact from
#: *the import is in progress*. `DEF-127` is the register's own record of what
#: it costs to spell *nobody looked* and *the answer is no* the same way.
#:
#: `partial` exists because it is the answer that actually arrives: an
#: accounting package refuses the two lines whose account codes it does not
#: recognise and takes the other thirty, which is neither accepted nor
#: rejected and is the case a finance officer most needs to see.
ACK_ACCEPTED = "accepted"
ACK_REJECTED = "rejected"
ACK_PARTIAL = "partial"
ACK_STATES = (ACK_ACCEPTED, ACK_REJECTED, ACK_PARTIAL)


class ExportBatch(models.Model):
    """One recorded handover of one closed window to one accounting system.

    B2 Addendum r13 #4 names the table and its four facts — *"period, target,
    idempotency, who/when, content hash"* — and DB-12 lists it in the signed
    idempotency register as UNIQUE per period+target. Both are honoured below;
    the money totals, the granularity and the stored payload are this lane's
    additions and are REPORTED as such in the migration's trailer.

    **THE UNIQUE KEY IS THE WINDOW AND THE TARGET, AND THE GRANULARITY IS NOT IN
    IT.** T5-07 step 3 is explicit: a second export of an already-covered window
    *"under the OTHER granularity"* is refused too, because *"idempotency is per
    covered window, whichever granularity was chosen; the window is handed over
    once"*. A second QuickBooks handover of July is how a tenant's ERP books
    July's revenue twice, and SMARTBillHub would have caused it. A DIFFERENT
    target for the same window is its own batch (US-LED-016 TC-2) — QuickBooks
    and a generic CSV are two accountants, not one double-handover.

    **`payload` IS STORED, AND THAT IS WHY THE FILE IS HASH-STABLE.** J19 step 7
    requires that *"the export file re-generated from the batch is identical"*.
    Regenerating it from the BOOKS would satisfy that only by accident: an
    entry auto-forwarded into an open period after the close (BR-TEN-038) does
    not change the closed window's figures, but a re-derivation would still have
    to make the same choices about rounding, ordering and export codes, forever.
    So the rows that were handed over are kept exactly as they were handed over,
    and `content_hash` is taken over them — US-LED-006 TC-4 in one column: *"the
    recorded batch (content hash) is unchanged; only FUTURE exports use the new
    ref"*.

    **MONEY IS `NUMERIC(18,6)` HERE TOO** (CLAUDE.md rule 2). These are not
    display figures: `total_debits` / `total_credits` are the footing the ERP
    was told, and LE-5's payload balances at **598.69 = 598.69**.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: The `EXP-` number (BR-LED-004; LE-5's **EXP-2607-QBO**), allocated from
    #: the tenant's `export_batch` series (BR-TEN-041 named it; tenancy seeds no
    #: default format for it, so it may be NULL — the service reports that gap
    #: by name rather than composing a number of its own).
    batch_no = models.TextField(null=True, blank=True)
    period_start = models.DateField()
    period_end = models.DateField()
    target = models.TextField()  # EXPORT_TARGETS
    granularity = models.TextField(default=EXPORT_SUMMARY)  # EXPORT_GRANULARITIES
    content_hash = models.TextField()
    row_count = models.IntegerField(default=0)
    total_debits = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    total_credits = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    currency = models.CharField(max_length=3, default="USD")
    #: The summary rows exactly as handed over — see the class docstring.
    payload = models.JSONField(default=list, blank=True)
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ── P5.4 · THE HANDOVER'S ANSWER ─────────────────────────────────────
    #
    # ⚠ **THE BLUEPRINT'S OWN SENTENCE IS THE WHOLE TASK:** *"Nothing reports
    # back whether the accounting package accepted it."* This table recorded
    # WHO sent WHAT and WHEN, in full, and then the handover ended. A finance
    # officer asked *"did QuickBooks take July?"* and the product could not
    # say — which is `finance.export.noAckStatus`, a sentence the screen has
    # been rendering as a stated absence since the screen shipped.
    #
    # ⚠ **THIS IS A RECORDED ANSWER, NOT A LIVE ONE, AND THE DIFFERENCE IS THE
    # DESIGN.** `BR-LED-020` makes v1 a FILE/batch handover and direct connect
    # v2, so there is no callback to listen for and no status to poll. What
    # closes the loop today is a PERSON: the accountant imports the file, says
    # whether it took, and a clerk records that against the batch. Inventing a
    # live status would be three green "Connected" chips over nothing, which is
    # `DEF-007`.
    #
    # ⚠ **THREE STATES, AND `None` IS THE FOURTH AND MOST COMMON.** `None`
    # means NOBODY HAS SAID — not *pending*, not *failed* — and it is what
    # every batch ever recorded carries. `DEF-127` is what happens when a
    # product spells *nobody looked* and *the answer is no* the same way.
    #: What the accounting package's operator told us (`ACK_STATES`), or `None`
    #: when nobody has said. Never inferred, never defaulted to a state.
    ack_state = models.TextField(null=True, blank=True)
    #: WHEN they said it. `BR-TEN-043` — an INPUT, never a clock read here: the
    #: import happened when it happened and a clerk may be recording it a day
    #: later.
    ack_at = models.DateTimeField(null=True, blank=True)
    #: Their reference for it — QuickBooks' import id, a Xero batch reference,
    #: an email subject. Free text, because it is THEIR identifier in THEIR
    #: system and we do not get to shape it.
    ack_reference = models.TextField(null=True, blank=True)
    #: What they said, in their words, when the answer is `rejected` or
    #: `partial`. The reason a handover was refused is the only thing that makes
    #: the refusal actionable.
    ack_note = models.TextField(null=True, blank=True)
    #: The clerk who recorded it — which is NOT the person who sent the batch,
    #: and keeping them apart is the point of a second column.
    ack_by_user_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "export_batches"
        constraints = [
            # DB-12's signed row for this table, and T5-07's whole point.
            models.UniqueConstraint(
                fields=["tenant", "period_start", "period_end", "target"],
                name="uq_export_batches_period_target",
            ),
            models.CheckConstraint(
                condition=Q(target__in=EXPORT_TARGETS), name="ck_export_batches_target"
            ),
            # `P5.4` — a state the product does not know is a state a screen
            # cannot render. NULL is lawful and is the common case (nobody has
            # said); anything else must be one of the three.
            models.CheckConstraint(
                condition=Q(ack_state__in=ACK_STATES) | Q(ack_state__isnull=True),
                name="ck_export_batches_ack_state",
            ),
            models.CheckConstraint(
                condition=Q(granularity__in=EXPORT_GRANULARITIES),
                name="ck_export_batches_granularity",
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=models.F("period_start")),
                name="ck_export_batches_window",
            ),
            models.UniqueConstraint(
                fields=["tenant", "batch_no"],
                condition=Q(batch_no__isnull=False),
                name="uq_export_batches_no",
            ),
        ]
        indexes = [
            # S42's export history: newest first, per tenant.
            models.Index(fields=["tenant", "created_at"], name="ix_export_batches_sent"),
            # The overlap check the service runs before every export.
            models.Index(fields=["tenant", "target", "period_start"], name="ix_export_batches_win"),
        ]


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-018/019 — the CAPTURED payable side (BR-LED-028..036 · EP-LED-06)
# ═══════════════════════════════════════════════════════════════════════════
#: BR-LED-035 — **void, never delete.** Two states and no third: there is no
#: `approved`, no `scheduled`, no `paid`, because BR-LED-028 forbids every one
#: of the workflows that would set them. A state machine with an approval state
#: in it is an approval workflow whether or not anything drives it, so the
#: enum itself is where that rule is enforced.
#:
#: ⚠ A5 (the signed enum contract) does not carry this state machine — the
#: ledger field map records it as **D-12**, owed to A5 on the schema route.
#: A-docs are design-session-owned (HUMAN-GUIDE §6) so no lane edits them; the
#: values live here and in `04-flows.md` §7 meanwhile.
SUPPLIER_INVOICE_CAPTURED = "captured"
SUPPLIER_INVOICE_VOIDED = "voided"
SUPPLIER_INVOICE_STATUSES = (SUPPLIER_INVOICE_CAPTURED, SUPPLIER_INVOICE_VOIDED)


class SupplierInvoice(models.Model):
    """One supplier invoice the utility was sent, CAPTURED and never processed.

    **THE TABLE NAME IS PROPOSED, NOT SIGNED.** B2 defines no payable table at
    all; the ledger field map's D-11 says so in as many words — *"the payable
    table does not exist … the name is PROPOSED"* — and a B2 addendum is owed on
    the schema route (the r13 #8 pattern: exact DDL, keys, RLS policy and
    immutability shape = Eng-Lead 🔒). The shape below matches the field map's
    `supplier_invoices.*` rows column for column so the addendum has one thing to
    ratify rather than two things to reconcile.

    ── WHAT IT HOLDS, AND WHAT IT REFUSES TO HOLD ──────────────────────────
    BR-LED-029: invoice date · service or cost category · **supplier name as
    FREE TEXT** · amount `NUMERIC(18,6)` + `CHAR(3)` · an **optional** volume
    with its explicit unit · a GL account · the accounting period · a reference
    and a memo.

    **`supplier_name` IS A TEXT COLUMN AND THERE IS NO VENDOR TABLE.** That is
    the rule, not a shortcut. BR-LED-028 (PO 2026-08-12, OQ-188 verbatim: *"we
    can make this system of record and capture Ap, AR both ; we dont have to
    process anything just capture and help Utility, Sub metering copany or HOA
    reconcile both sides as system of record"*) forbids a vendor master, so
    *"City of Rosenberg"* and *"City of Rosenberg - Water Dept"* are both stored
    as typed, with no FK, no dedupe and no merge prompt (US-LED-018 TC-4). A
    later lane reading this column as a missing normalisation would be undoing a
    ruling.

    **THERE IS NO `approved_by`, NO `due_date`, NO `paid_at` AND NO
    `payment_run_id`**, and their absence is BR-LED-028 as well: no approval
    workflow, no payment run, no ageing chase, no cheque printing, no paying
    anything. Option (c) *full accounts payable* was put to the PO and DECLINED.

    ⚠ **AMENDED 2026-09-02 (CR-060 C1 / task T6, PO ruling) — `paid_on` EXISTS,
    AND THE FOUR ABSENCES ABOVE STAND UNCHANGED.** This paragraph is amended
    rather than rewritten because the distinction it draws is the whole ruling
    and a later reader must be able to see both halves.

    What BR-LED-028 declined is **full accounts payable**: an approval workflow,
    a payment run, an ageing chase, cheque printing, *paying anything*. **A date
    recording that payment happened SOMEWHERE ELSE is none of those.** The
    utility pays its water bill by cheque or by bank transfer, in its bank, and
    then tells this product it did — the PO's own words, 2026-09-02: *"why cant
    to add the check that whether this is paid or unpaid and allow clark to
    udpaet it - that way we can reconcicle - again system of record we dont have
    to match we can take input from Clark and close it"*. **The clerk's input is
    the authority and no automatic matching is required**, which is the same
    *"system of record"* sentence already quoted at the top of this docstring.

    So: still no `approved_by` (nothing approves), still no `due_date` (nothing
    chases), still no `payment_run_id` (nothing pays) — and deliberately
    **`paid_on`, a DATE, not `paid_at`, a timestamp**. The four names above are
    the ones a payables system needs; a date is what a reconciliation needs.

    **ITS PRESENCE IS WHAT MAKES THE ROW POSTABLE.** Unset, nothing posts and the
    books do not move — which is why this column could land on a live database
    without moving one signed figure. Set, `apps/ledger/cost_capture.
    record_settlement` posts **DR cost / CR cash** through the one posting
    service (hard rule 5), and no accounts payable is created at any point —
    which is precisely why the PO's original objection to posting (a liability
    this product can never drain) does not apply to it.

    ── THE VOLUME IS NULLABLE **BY RULE** ──────────────────────────────────
    BR-LED-030 (PO 2026-08-12, OQ-190 verbatim: *"I dont know but we can make a
    provision and make it optional"*). A cost-only invoice — CI-8's $1,845.50 of
    pipe, CI-9's $12,500.00 of meters — is refused by nothing. What the optional
    volume costs is paid at the REPORT, not here: BR-LED-031 makes the
    unaccounted-for percentage all-or-nothing per service per period, because a
    partial denominator turns July's honest **9.00%** into **−13.75%**.

    `ck_supplier_invoices_volume_unit` is the half CLAUDE.md rule 3 does demand:
    a volume without an explicit unit, or a unit with no quantity, is refused by
    the DATABASE and not only by the service. Omitting BOTH is legal, and that
    is the whole point of the column pair being nullable together.

    ── WHY THIS TABLE HAS NO IMMUTABILITY TRIGGER, AND DOES HAVE A DELETE ONE ──
    Hard rule 4 lists issued invoices, invoice lines, payments and journal
    entries. **A captured supplier invoice is on none of those lists** — it is
    not a document anybody was sent, and BR-LED-034 makes it EDITABLE while its
    own period is open, with before/after audit. So no `_immutable()` trigger.

    **Deletion is a different question and it is ruled.** BR-LED-035: *"void,
    never delete"* — derived from hard rule 4's *"corrections are new rows"* and
    IS-1's *"financial records never delete"*. The row keeps its place in the
    register with its reason so a clerk can reconcile against a supplier
    statement, and it leaves every aggregate from that moment: after CI-4 is
    voided the July footer moves **51,902.50 → 51,747.50** and water's figure
    moves **9.00% → 4.21%**, correctly, because those 50,000 gallons were never
    bought. `ledger_supplier_invoice_no_delete()` in `ledger/0008` is the
    database's half of that; `apps/ledger/cost_capture.py` publishes no delete
    function at all, which is the application's half.

    **AN EDIT AND A VOID ARE BOTH LAWFUL AFTER THE PERIOD CLOSES — RULED
    2026-08-16 (OQ-203, PO verbatim: _"Yes it can be corrected"_), with a REASON
    and an audit row rather than frozen.** Nothing in this class changed for it,
    which is why the question could be answered without a migration: the
    correction is an ordinary UPDATE, its reason rides the append-only audit
    payload as `after_close_correction`, and the consequence the PO accepted —
    an exported batch that no longer matches — is NAMED on the export screen
    rather than hidden (`apps/ledger/exports.stale_batches`).

    ── THE PERIOD IS TWO DATES, NOT A LABEL ────────────────────────────────
    `period_start` / `period_end`, exactly as `FiscalPeriodClose` carries them
    and for the same reason (BR-TEN-022): a tenant on quarterly close and a
    tenant on monthly close both fit, and nothing has to parse a month out of a
    string. A capture dated into a CLOSED period never lands there — the service
    asks `close.resolve_entry_date`, the rule already built for LE-9, and the
    row records the period it actually landed in with an audit note saying why.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: BR-TEN-081: a typed date is midnight in the utility's OWN timezone.
    #: ⚠ DEF-082 — Company settings has no timezone field yet, so the caller's
    #: date is taken as given. Named rather than silently assumed UTC.
    invoice_date = models.DateField()
    #: The tenant's LIVE service code, or one of `chart.COST_CATEGORIES`
    #: (`operations_maintenance` / `infrastructure`). **No CHECK constraint and
    #: no FK**: BR-REP-006 makes the vocabulary the tenant's live service list,
    #: which is per-tenant data, and a CHECK inlined at migration time would
    #: freeze a ten-service platform catalogue into the database (the same trap
    #: `GL_DESIGNATIONS` documents). `cost_capture.py` validates against the
    #: live list on every write.
    service = models.TextField()
    #: FREE TEXT — see the class docstring. No FK, by rule.
    supplier_name = models.TextField()
    #: ⚠ **CR-060 C3 / task T4 — WHICH BUILDING THIS COST WAS BOUGHT FOR.**
    #:
    #: NULLABLE, and the null is a real state rather than an unfilled field: a
    #: tenant-wide purchase (the office insurance premium, the payroll run) has
    #: no building, and a utility that runs one distribution system never fills
    #: it at all. **For a sub-metering company it is the product** — CR-060's
    #: own words — because bought-versus-billed at forty buildings blended into
    #: one average *"describes neither and points at nothing anyone can go and
    #: fix"*.
    #:
    #: **A REAL FK, NOT A DEFERRED UUID, AND THAT IS THIS MODULE'S OWN RULE.**
    #: CR-060 §9's table says *"deferred FK to metering, matching how every
    #: other cross-module pointer here is declared"* — and read from the code,
    #: how every other cross-module pointer here is declared is a REAL FK with
    #: `PROTECT`. `JournalLine.premises` says why in its own docstring: *"They
    #: are FKs rather than plain uuids because every target table already
    #: exists; the B11 F-3 deferred-uuid convention applies only where it does
    #: not."* `metering.Premises` exists, so the convention does not apply, and
    #: the two halves of the same figure — the journal line's stamped premises
    #: and the purchase's — should not be declared two different ways.
    #:
    #: `PROTECT` for the same reason as `ledger_account` above: a building a
    #: captured purchase points at must not be deleted out from under the
    #: register, and the database is a better keeper of "forever" than a query
    #: somebody has to remember to run.
    #:
    #: ⚠ This is an ADDITION to B2 §2's reviewed cross-module interface set,
    #: which r16 #7 puts on the register at DDL time — the same posture
    #: `JournalLine`'s four cross-module FKs took when they landed.
    premises = models.ForeignKey(  # ⚠ cross-module FK → metering (r16 #7)
        "metering.Premises",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="premises_id",
    )
    #: CLAUDE.md rule 2 / DB-3. Never float, never cents, and never rounded
    #: here: BR-LED-025 makes the ledger refuse to be a second rounding site,
    #: so the amount is stored exactly as keyed at six decimals.
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3)
    #: NULLABLE BY RULE (BR-LED-030) — see the class docstring.
    volume = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    #: Required whenever `volume` is present (CLAUDE.md rule 3, BR-LED-033).
    #: TEXT and not an enum: **the per-service purchase-unit vocabulary is
    #: OQ-201, OPEN**, and an enum would be this lane answering it. The
    #: reconciliation compares it to the billed unit as an exact string and
    #: reports `purchase_unit_does_not_match_billed_unit` when they differ —
    #: no conversion factor is applied, because whether one may be is the other
    #: half of OQ-201.
    volume_unit = models.TextField(null=True, blank=True)
    #: The cost account this purchase is classified to. `PROTECT`, so an account
    #: a captured invoice points at cannot be deleted out from under it —
    #: US-LED-017 TC-6 (IS-1's audit lock) enforced by the database rather than
    #: by a query somebody has to remember to run.
    ledger_account = models.ForeignKey(
        LedgerAccount, on_delete=models.PROTECT, db_column="ledger_account_id"
    )
    period_start = models.DateField()
    period_end = models.DateField()
    reference = models.TextField(null=True, blank=True)
    memo = models.TextField(null=True, blank=True)
    #: ⚠ **CR-060 C1 / task T6 — THE DAY THE UTILITY SETTLED THIS INVOICE, AND
    #: ITS PRESENCE IS WHAT MAKES THE ROW POSTABLE** (PO ruling 2026-09-02; see
    #: the amended BR-LED-028 paragraph in the class docstring above).
    #:
    #: NULLABLE, and the null is a REAL STATE and the overwhelming majority
    #: state: an invoice that arrived and has not been paid yet is unpaid, and
    #: "unpaid" is a fact rather than a field somebody forgot. **Unset, nothing
    #: posts** — `record_settlement` returns without touching the books, and a
    #: database on which no row carries this date has a trial balance that does
    #: not move by one cent when this column lands.
    #:
    #: **A DATE, NOT A TIMESTAMP, AND THE NAME IS LOAD-BEARING.** `paid_at` is
    #: one of the four names BR-LED-028 refuses (see the class docstring): it
    #: belongs to a system that PAYS things and records the instant it did.
    #: This is the day the utility's BANK moved the money, typed in by a clerk
    #: reading a bank statement, and a day is the granularity a bank statement
    #: has. It is also the BOOK date of the settlement entry, which is a date by
    #: rule (BR-TEN-043 — the caller names the business event's day).
    #:
    #: **NO CHECK CONSTRAINT, DELIBERATELY.** `paid_on` earlier than
    #: `invoice_date` looks wrong and is not: a utility on a standing order can
    #: be debited before the invoice is written, and a clerk correcting a
    #: mis-typed invoice date would meet a database refusal for a fact that is
    #: none of the database's business. The rules that DO bind it live where
    #: they can say why — `cost_capture.record_settlement` refuses to clear or
    #: to move it once the settlement has posted, because the entry is already
    #: in the books and hard rule 4 leaves no path to change it.
    paid_on = models.DateField(null=True, blank=True)
    status = models.TextField(default=SUPPLIER_INVOICE_CAPTURED)
    #: REQUIRED when the status is `voided` — enforced by
    #: `ck_supplier_invoices_void_reason`, because a void with no reason is a
    #: row a clerk cannot reconcile against a supplier statement, which is the
    #: only thing keeping the row visible is FOR.
    void_reason = models.TextField(null=True, blank=True)
    voided_by_user_id = models.UUIDField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    captured_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "supplier_invoices"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=SUPPLIER_INVOICE_STATUSES),
                name="ck_supplier_invoices_status",
            ),
            # BR-LED-029: an amount of zero or less is not an invoice anybody
            # was sent. Refused here as well as in the service, because a
            # negative purchase would silently reduce a bought-cost total.
            # ⚠ A supplier CREDIT NOTE has no path today and is named rather
            # than assumed — workbook V-12.
            models.CheckConstraint(condition=Q(amount__gt=0), name="ck_supplier_invoices_amount"),
            # CLAUDE.md rule 3 — both or neither. See the class docstring.
            models.CheckConstraint(
                condition=(
                    Q(volume__isnull=True, volume_unit__isnull=True)
                    | Q(volume__isnull=False, volume_unit__isnull=False)
                ),
                name="ck_supplier_invoices_volume_unit",
            ),
            models.CheckConstraint(
                condition=Q(volume__isnull=True) | Q(volume__gte=0),
                name="ck_supplier_invoices_volume_sign",
            ),
            models.CheckConstraint(
                condition=Q(period_end__gte=models.F("period_start")),
                name="ck_supplier_invoices_period",
            ),
            # BR-LED-035 — a void carries its reason or it is not a void.
            models.CheckConstraint(
                condition=(
                    ~Q(status=SUPPLIER_INVOICE_VOIDED)
                    | (Q(void_reason__isnull=False) & ~Q(void_reason=""))
                ),
                name="ck_supplier_invoices_void_reason",
            ),
        ]
        indexes = [
            # The register's default view and the reconciliation's denominator:
            # one tenant, one period, live rows.
            models.Index(
                fields=["tenant", "period_start", "status"], name="ix_supplier_invoices_period"
            ),
            # Per-service roll-up — the bought column of every S74 row.
            models.Index(
                fields=["tenant", "service", "period_start"], name="ix_supplier_invoices_svc"
            ),
            # CR-060 C9 / task T4 — the PER-BUILDING roll-up, which is the same
            # read one dimension over. Laid with the column rather than after
            # it, for T8's own argument: an index is free on a small table and
            # costs a maintenance window on a large one.
            models.Index(
                fields=["tenant", "premises", "period_start"], name="ix_supplier_invoices_prem"
            ),
            # S73's default sort: invoice date descending.
            models.Index(fields=["tenant", "invoice_date"], name="ix_supplier_invoices_date"),
        ]



#: `BR-LED-013` — each authority remits on ONE of these, and the TENANT chooses
#: which per authority. Written here beside the table that records it rather
#: than imported from `journal`, because a model must not import the service
#: that writes it.
REMIT_BASIS_BILLED = "billed"
REMIT_BASIS_COLLECTED = "collected"
REMIT_BASES = (REMIT_BASIS_BILLED, REMIT_BASIS_COLLECTED)


class TaxRemittance(models.Model):
    """ONE filing: what was paid to one authority, for one period, and its proof.

    **B2 Addendum r13 #3, built at last (`P4.4`, Finance blueprint p017).** The
    table has been named in this repository since the journal core landed and
    never built; `journal.REMITTANCE_REGISTER_NOT_BUILT` and
    `journal.RECEIPT_HAS_NO_HOME` are the two `unavailable` codes that said so
    on every remittance response, and both go with this class.

    What the missing table cost, in the blueprint's own words (p058): *"you can
    record a tax payment and never see it again"*. `POST
    /finance/taxes/remittances` posted a balanced journal entry and **stored
    nothing else** — no filing row, no filing reference a screen could show, and
    nowhere to keep the receipt `BR-LED-019` requires.

    ═══════════════════════════════════════════════════════════════════════
    THE BOOKS ARE STILL THE NUMBER THAT HAS TO BE RIGHT
    ═══════════════════════════════════════════════════════════════════════
    ⚠ **THIS REGISTER DOES NOT BECOME THE SOURCE OF `REMITTED`.**
    `reporting.remittance_by_authority` reads that column out of the JOURNAL —
    it sums remittance-sourced debits per 2200-nn account — and it goes on doing
    so. `BR-REP-002` makes the books the number that has to be right and a
    register is a convenience over them; two independent totals of one fact is
    how a screen and a trial balance come to disagree, and the one that would be
    wrong is the one nobody posts to.

    So this table records what a JOURNAL ENTRY cannot: the filing reference, the
    date the money actually left, and the receipt. Every row points at the entry
    it posted, and the entry is what the money means.

    ═══════════════════════════════════════════════════════════════════════
    THE RECEIPT IS NOT A COLUMN HERE
    ═══════════════════════════════════════════════════════════════════════
    ⚠ **`tenancy/0051` settled this shape and it is followed rather than
    re-argued**: a document is found by WHAT IT BELONGS TO —
    `stored_documents.source_type` + `source_id` — which is how a bill, a
    payment receipt, a work order's photographs and an account's paperwork are
    all already found. A `receipt_document_id` column would be a second place
    one fact lives, it would be a second place one fact lives, free to
    disagree with the store the first time one was removed.
    `document_store.for_source()` answers the question without it.

    ⚠ **IT ANSWERS FOR ONE DOCUMENT, NOT SEVERAL — STATED BECAUSE THIS
    DOCSTRING CLAIMED OTHERWISE UNTIL IT WAS MEASURED.** `for_source` returns a
    `DocumentLookup` carrying a single `document`, so a filing keeps ONE
    receipt today. Holding the return and the authority's acknowledgement
    beside it is a real want and it is not built; `OQ-LED-12654` is where it
    belongs. A comment claiming a guarantee is not the guarantee (law 1).

    ═══════════════════════════════════════════════════════════════════════
    APPEND-ONLY, AND WHY THAT IS SAFE HERE
    ═══════════════════════════════════════════════════════════════════════
    ⚠ **HARD RULE 4 DOES NOT NAME THIS TABLE, AND THIS IS STILL APPEND-ONLY.**
    The rule lists issued invoices, invoice lines, payments and journal entries.
    A filing register is not one of them — but a row here is the auditor artefact
    for a payment that HAS moved money through a journal entry that can never be
    edited, so a register that could be rewritten afterwards would be a record
    that disagrees with the books it points at. `ledger/0020` carries the
    UPDATE and DELETE refusals as triggers, because a Django model cannot refuse
    a `.save()`.

    ⚠ **THAT MEANS A MISTYPED CONFIRMATION REFERENCE IS A NEW ROW, NOT AN
    EDIT** — and there is deliberately no `POST .../correct-reference` here.
    The PO's 2026-09-02 narrowing of hard rule 4 is for THREE COLUMNS OF
    `payments` and for nothing else; CLAUDE.md says `payments/0014` is the only
    place that allow list moves, and widening it anywhere else is a new ruling.
    **`OQ-LED-12653` is OPEN** and carries the worked case.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    #: `BR-BIL-069` — the authority's own 2200-nn account IS the authority's
    #: identity in the books. There is no `tax_authorities` table to point at
    #: and none is invented here.
    tax_account = models.ForeignKey(
        "ledger.LedgerAccount", on_delete=models.PROTECT, db_column="tax_account_id"
    )
    #: The return's period — what the filing COVERS, which is not when it was
    #: paid and routinely differs by a month.
    period_start = models.DateField()
    period_end = models.DateField()
    #: **What left the bank** (`amount`), to 6 places like every other money
    #: column in this schema — CLAUDE.md rule 2 governs what is WRITTEN, and
    #: nothing writes more than 4.
    amount = models.DecimalField(max_digits=18, decimal_places=6)
    currency = models.CharField(max_length=3)
    #: `BR-LED-013` — which basis this authority files on. Never defaulted: LE-3
    #: has State on COLLECTED and County on BILLED, so a default would be wrong
    #: for one of them in its first month.
    basis = models.TextField()
    #: `BR-LED-019` — *"remittance records carry a filing CONFIRMATION REF +
    #: receipt file attachment (auditor artifact)"*. REQUIRED: recording the
    #: payment without it drains the liability and leaves nothing proving the
    #: return was filed.
    confirmation_ref = models.TextField()
    #: `BR-TEN-043` — the day the money left, as STATED by the person recording
    #: it. Never a clock read here: a clerk files on Monday and records it on
    #: Wednesday, and stamping our own date would put our clock on their act.
    paid_on = models.DateField()
    #: The balanced entry this filing posted. `PROTECT`, because a register row
    #: pointing at nothing is worse than no register row.
    journal_entry = models.ForeignKey(
        "ledger.JournalEntry", on_delete=models.PROTECT, db_column="journal_entry_id"
    )
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tax_remittances"
        constraints = [
            models.CheckConstraint(
                condition=Q(basis__in=REMIT_BASES), name="ck_tax_remittances_basis"
            ),
            # A zero remittance moves no money and a negative one is a REFUND
            # from the authority — a different source event with a different
            # DR/CR contract. `journal.record_tax_remittance` refuses both; the
            # database says so too, because a service check is not a guarantee.
            models.CheckConstraint(condition=Q(amount__gt=0), name="ck_tax_remittances_amount"),
            models.CheckConstraint(
                condition=Q(period_end__gte=models.F("period_start")),
                name="ck_tax_remittances_period",
            ),
            # `BR-LED-019` — a blank reference is the same absence as a missing
            # one, and the service already refuses it by name.
            models.CheckConstraint(
                condition=~Q(confirmation_ref=""), name="ck_tax_remittances_confirmation"
            ),
            # ⚠ **ONE REGISTER ROW PER JOURNAL ENTRY.** The posting service is
            # idempotent on (authority, period, amount), so a retried request
            # returns the SAME entry — and without this a second register row
            # would appear beside it and the filing history would list one
            # payment twice. It is the same reasoning `export_batches` applies
            # to a window and a target.
            models.UniqueConstraint(
                fields=["tenant", "journal_entry"], name="uq_tax_remittances_entry"
            ),
        ]
        indexes = [
            # The screen's own read: this tenant's filings, newest first.
            models.Index(
                fields=["tenant", "-paid_on"], name="ix_tax_remittances_tenant_paid"
            ),
        ]


#: The two halves of a service's revenue a class row can override — the same
#: usage/base split `tenant_services` carries (BR-BIL-010).
REVENUE_PARTS: tuple[str, ...] = ("usage", "base")


class ServiceClassRevenueAccount(models.Model):
    """ONE customer class's own revenue account for one service and one part.

    **`CR-197-BRC10`, BR-LED-801 — PO 2026-10-29, verbatim:** *"it should be as
    per utility service but some time utility wants track the seperate as per
    cutomer class also"*. The service's every-class account stays where it has
    always been (tenancy's `tenant_services.revenue_account_id` /
    `base_revenue_account_id`, read through the seam); THIS table holds only the
    overrides, and a row here wins for a bill whose account is of that class.

    **Why the LEDGER owns it:** it is a GL map, and the PO closed OQ-106 with the
    maps belonging to the ledger. Billing asks
    `selectors.revenue_account_id_for_service(code, base=…, customer_class=…)`
    and never reads this table.

    `customer_class` is the customers module's `account_types.code` as TEXT —
    the reading `rating.ChargeCodeAmount.customer_class` already uses — because
    a class is a tenant-owned code and a cross-module FK would be a new reviewed
    interface for a label. `service_code` is TEXT for the same reason
    `tenancy_seam` is keyed on it.

    No row is ever immutable here: a mapping is configuration, not a financial
    record. What protects history is that an issued line's `gl_account_id` is
    stamped at issue and frozen (hard rule 4); changing or removing a row here
    reaches the NEXT bill only. Removal IS this row's Disable (BR-LED-802).

    HUMAN-OWNED · HUMAN-REVIEW-PENDING — it decides which account a bill's
    revenue lands in (🔒 GL resolution). Row in
    `12-governance/09-human-review-ledger.md`.
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    service_code = models.TextField()
    part = models.TextField()
    customer_class = models.TextField()
    ledger_account = models.ForeignKey(
        LedgerAccount, on_delete=models.PROTECT, db_column="ledger_account_id", related_name="+"
    )
    created_by_user_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ledger_service_class_revenue_accounts"
        constraints = [
            models.CheckConstraint(
                condition=Q(part__in=REVENUE_PARTS), name="ck_ledger_class_revenue_part"
            ),
            models.CheckConstraint(
                condition=~Q(customer_class=""), name="ck_ledger_class_revenue_class"
            ),
            # One account per (service, part, class): two rows would leave the
            # bill to pick one by accident.
            models.UniqueConstraint(
                fields=["tenant", "service_code", "part", "customer_class"],
                name="uq_ledger_class_revenue",
            ),
        ]

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-001@c7a1f30 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — §2 ledger DDL + §3 RLS/balance triggers + Addendum r13, the PO-approved ledger schema batch — · 04-docs/05-modules/09-ledger/06-epics/EP-LED-01-posting-consumption.md · 04-docs/05-modules/09-ledger/02-business-rules.md · 04-docs/05-modules/09-ledger/03-field-map.md, so a later change to any of them makes this stamp findable as stale in one grep)
# generated: 2026-08-11 by Eng-Lead (W5 ledger journal-core schema slice) · AMENDED 2026-08-11 by Eng-Lead (OQ-116 tax-authority GL lane — BR-BIL-069: docstring corrections only — two stale claims citing OQ-116 as a live blocker) · AMENDED 2026-08-15 by the close-the-books lane (THREE ADDITIONS, all in ledger/0007: `journal_entries.number` — BR-LED-021's `JE-` series, nullable because a DRAFT has none and unique-where-set because BR-TEN-035 never reuses a number; `FiscalPeriodClose` — the record `apps/ledger/posting.py` said did not exist anywhere in the schema, authored under B2 r13 #8's *storage mechanics 🔒* delegation and REPORTED as an extension beyond B2 §2; `ExportBatch` — B2 Addendum r13 #4 with DB-12's signed UNIQUE(period, target). No existing column, index or constraint was changed) · AMENDED 2026-08-15 by the AP-capture lane (ONE ADDITION, in ledger/0008: `SupplierInvoice` — the CAPTURED payable side of EP-LED-06. The table name `supplier_invoices` is PROPOSED, not signed: B2 defines no payable table and this file's own field map records that as D-11, so the columns match the field map's `supplier_invoices.*` rows exactly and a B2 addendum is owed. No existing column, index or constraint was changed)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — models only) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the migrations' trailers — these classes, 0001 and 0002 ship together
# exceptions: SCHEMA ONLY — no posting service, no balance-computing Python, no
#         tie-out view, no export; CLAUDE.md rule 5's sole-writer boundary is NOT
#         implemented here [AMENDED 2026-08-11: this line used to add "posting.py
#         stays a NotImplementedError stub" and that is no longer true — the
#         posting-service lane built it and put the sole-writer boundary in
#         migrations/0004; the claim about THIS file is unchanged] ·
#         r13 items #3 (tax_remittances) and #4 (export_batches) are separate
#         tables belonging to EP-LED-05 and are NOT started · [SUPERSEDED
#         2026-08-11 — the candidate OQ became OQ-106/OQ-110 and both are
#         CLOSED] r10 #2's DESIGNATIONS are now BUILT as
#         `ledger_accounts.designation` (eleven values, chart.py) and r10 #2's
#         `service_gl_map` is realised as the `revenue_account` /
#         `base_revenue_account` attributes on `tenant_services` rather than as
#         a separate table, per the PO's "a field, not a table" ruling;
#         `tax_authority_gl_map` is DELIBERATELY NOT BUILT and never will be
#         [CORRECTED 2026-08-11 — this said "is OQ-116", and OQ-116 is CLOSED:
#         the PO ruled option A as amended (BR-BIL-069) and DECLINED option B,
#         which was exactly r10 #2's table. One home for the mapping,
#         `rating.taxes.liability_gl_account_id`, plus the tagging column
#         `invoice_lines.tax_id` (billing 0010). The 2200-series accounts the
#         map would have pointed at are minted per tenant per authority through
#         `apps.ledger.services.create_tax_authority_account` and seeded to
#         nobody, per B5 line 74 ❄️ *"tenant authorities mint their own"*] ·
#         `journal_entries.posted_at` is an EXTENSION beyond r13 #2's literal
#         text (it lists type + draft state + the two links): kept because LE-9
#         turns on entry_date and posting time being different facts, and
#         because `invoices.issued_at` is the same column in the same role —
#         REPORTED for the reviewer, not silently taken · currency sits on the
#         entry, not the line (see the docstring) · NFR-24 lists journal_lines
#         in the mandatory monthly-partition set and this table ships
#         UNPARTITIONED, matching invoice_lines (W3); core/partitioning.py
#         already registers it with wave W5 and key `created_at` but its
#         ACTIVE_TABLES is pinned by a core/-owned test — REPORTED, not
#         silently skipped · BALANCE AND IMMUTABILITY ARE NOT IN THESE CLASSES:
#         a Django model cannot refuse a .save() nor see its siblings, so both
#         live in the 0002 triggers, stated here rather than implied ·
#         `supplier_invoices` IS AN EXTENSION BEYOND B2 §2 AND ITS NAME IS
#         PROPOSED — the ledger field map's D-11 states it: *"the payable table
#         does not exist … a B2 addendum is owed on the schema route"*. The
#         columns transcribe the field map's `supplier_invoices.*` rows so the
#         addendum ratifies one shape rather than reconciling two. REPORTED,
#         not presented as signed schema · IT CARRIES NO IMMUTABILITY TRIGGER:
#         hard rule 4 lists issued invoices, invoice lines, payments and journal
#         entries and NOT this table, and BR-LED-034 makes a capture editable
#         while its period is open. What it does carry is a DELETE refusal
#         (BR-LED-035, `ledger/0008`) · its `status` enum is not in A5 — the
#         field map's D-12, owed to A5 on the schema route, and A-docs are
#         design-session-owned so no lane edits them · NO `approved_by`,
#         `due_date`, `paid_at` or `payment_run_id` column exists, BY RULE
#         (BR-LED-028); their absence is the ruling, not an omission
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

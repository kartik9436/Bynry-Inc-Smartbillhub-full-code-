# ── Trace ──────────────────────────────────────────────
# Change:  CR-110-BRC04 phase 2 wave 5 (2026-09-16) — the READ path: the books,
#          in a partner's shape, for `GET /api/{utility}/partner/v1/ledger`.
#          CR-083 (PO 2026-09-07) — the sample set's Integrations block records
#          one accounting handover, so `export_batches` stops reading 0 on a
#          freshly provisioned tenant. CR-069 §11: one seam file per module
#          integrations hands to or reads from.
# Rules:   BR-TEN-013 (a cross-module write is performed by the OWNING module's
#          own service function — this file is the ADDRESS, never the writer) ·
#          BR-LED-004 (one recorded, idempotent handover per period + target) ·
#          BR-LED-017 (a period is exported only once it is CLOSED) ·
#          BR-LED-018 (a month closes with WARN + CONFIRM — a reason always
#          gets through, and nothing here is a lockout) · BR-TEN-043
#          (`created_at` / `closed_at` are INPUTS; no clock is read here) ·
#          DEF-075 (a seam answering `None` means *this module cannot answer*,
#          never *this module has nothing*) · CLAUDE.md hard rule 1 ·
#          hard rule 5 (balanced pairs — the read hands both sides over and
#          moves neither) · hard rule 2 (money stored to 4, DISPLAYED to 2) ·
#          BR-LED-003 (a draft entry is not in the books and never leaves) ·
#          BR-LED-021 (the `JE-` number, and `DEF-LED-5540` where it is absent)
# Tests:   06-backend/tests/test_cr110_wave5_partner_ledger.py (the read path) ·
#          06-backend/tests/test_cr083_integrations_sample_data.py
#          ⚠ THAT SECOND LINE READ `test_cr082_…` FROM 2026-09-07 UNTIL
#          2026-09-16 AND NAMED A FILE THAT HAS NEVER EXISTED — a typo for the
#          CR-083 test this file's own Change line cites. `G95` and `G116` were
#          red on it for nine days, alongside `sample_data.py`, which carries
#          the SAME typo and is not this lane's to edit. A `Tests:` line is how
#          the next lane decides whether a change is already guarded, so one
#          pointing at nothing says *this is covered* and the case never gets
#          written (`DEF-RBS-4335`).
# Impacts: apps/integrations/partner_api.py (`partner_ledger`, wave 5) ·
#          apps/integrations/sample_data.py (the write path's only caller)
# ───────────────────────────────────────────────────────
"""integrations → ledger: the books a partner may read, and closing a month.

TWO HALVES, AND THEY FACE OPPOSITE WAYS. `close_period` and
`create_export_batch` are OURS calling ledger's own services; `collectable`,
`row_total` and `as_record` are a PARTNER reading what those services left
behind. The read is the larger half and its whole difficulty is that our ledger
and a partner's are different shapes — see `as_record`.

⚠ **THIS FILE WRITES NOTHING AND THE DISTINCTION IS THE WHOLE POINT.** Both
functions below call `apps.ledger`'s own service — `close.close_period` and
`exports.create_export_batch` — which is ledger's code writing ledger's tables,
exactly as `B2` §2, the module map and `BR-TEN-013` require. The seam is the
ADDRESS. It is the same discipline `seams/payments.land_inbound_delivery`
already keeps, and the reason it is a seam file rather than an import is that
`apps/integrations/` may not import another app's modules at module scope (G6),
and the module graph has to stay a DAG: integrations is loaded at
`AppConfig.ready()` and ledger must not have to be.

⚠ **NEITHER FUNCTION SWALLOWS A REFUSAL.** Ledger's four export gates —
the month must be closed, the window must not already be covered, the books
must foot, every account must carry its ref — are the point of asking ledger
instead of writing the row. They raise, and the caller reports the refusal by
name (`BR-TEN-060`). A seam that turned an `ExportError` into `None` would
make *"the books do not balance"* indistinguishable from *"there is no
ledger"*, which is `DEF-075` exactly.

⚠ **`None` IS ONLY EVER RETURNED FOR AN ABSENT MODULE.** If `apps.ledger` is
not importable in this deployment these answer `None`, meaning *this module
cannot answer*. The caller then declines to record anything; it never treats
that as *the utility has no books*.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.db.models import Case, Count, F, IntegerField, Prefetch, Q, Sum, When
from django.db.models.functions import Greatest

from core.tenancy import current_tenant_id


def _ledger() -> Any | None:
    """`apps.ledger`, or `None` when this deployment has no ledger at all."""
    try:
        from apps import ledger  # noqa: F401 — imported for its submodules
    except ImportError:  # pragma: no cover — the app is installed in every build
        return None
    return ledger


def close_period(
    *,
    actor: Any,
    period_start: date,
    period_end: date,
    closed_at: datetime,
    reason: str | None = None,
) -> dict[str, Any] | None:
    """Shut a month, through ledger's own `close_period`.

    `closed_at` is an INPUT (`BR-TEN-043`): the moment a period shut is a
    business fact, and a service that read a clock would stamp a different one
    on a retry. `reason` is what `BR-LED-018` demands whenever the close
    checklist is short of complete — WARN + CONFIRM, never a silent close and
    never a hard lockout.

    Raises ledger's own `CloseError` for a month that is already closed. That
    is not swallowed here: the caller has to be able to tell *already closed*
    from *no ledger*.
    """
    if _ledger() is None:
        return None
    from apps.ledger import close as ledger_close

    return ledger_close.close_period(
        actor,
        period_start=period_start,
        period_end=period_end,
        closed_at=closed_at,
        reason=reason,
    )


def create_export_batch(
    *,
    actor: Any,
    period_start: date,
    period_end: date,
    target: str,
    created_at: datetime,
) -> dict[str, Any] | None:
    """Record that a closed month went to the books, through ledger's own service.

    ⚠ **THE IDEMPOTENCY KEY IS LEDGER'S AND IS NOT TOUCHED HERE.**
    `uq_export_batches_period_target` (`BR-LED-004`, `DB-12`) is what makes a
    second handover of one window impossible, and it is signed. This seam adds
    no second key, no pre-check and no "have we done this already" of its own:
    a caller that wants to know asks ledger, and a replay is refused by the
    database with a sentence naming the first batch.

    `created_at` is an INPUT for `BR-TEN-043`'s reason — a retried send must
    stamp one moment, and a fixture must stamp the same one on every tenant.
    """
    if _ledger() is None:
        return None
    from apps.ledger import exports as ledger_exports

    return ledger_exports.create_export_batch(
        actor,
        period_start=period_start,
        period_end=period_end,
        target=target,
        created_at=created_at,
    )



# ═══════════════════════════════════════════════════════════════════════════
# CR-110-BRC04 phase 2 wave 5 · THE READ PATH — our books, in a partner's shape
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **OUR LEDGER AND A PARTNER'S ARE DIFFERENT SHAPES, DELIBERATELY, AND THIS
# BLOCK IS THE WHOLE OF THE TRANSFORM.** `JournalLine` carries a `side` and a
# NON-NEGATIVE amount — its own docstring says why: *"Direction is a column, so
# there is exactly one way to express a credit."* A balanced pair is therefore
# TWO ROWS. Aclarian's `/ledger` payload is ONE row carrying a `debitAccount`
# and a `creditAccount`. Everything below is how the first becomes the second
# without a cent moving, and it is written out here rather than left to be
# inferred, because the specification itself calls this API *PROPOSED* and says
# *"Final debit/credit handling and GL mapping should follow the accounting
# rules agreed with Aclarian."* **No accounting rule is invented here.**


def display_amount(value: Any) -> str:
    """Four stored decimals → two displayed, half-up (hard rule 2, B4).

    ⚠ **THE SAME FOUR LINES AS `seams/billing` AND `seams/payments`, AND THAT
    IS DELIBERATE RATHER THAN LAZY.** Rounding happens at DISPLAY and in ONE
    place per payload; a seam that imported a sibling's copy would make
    integrations' three partner payloads depend on each other for their money
    format, and the day one of them needs a different rounding the other two
    would move with it silently. B4 owns the rule; each seam states it.
    """
    return str(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _models() -> Any:
    """`apps.ledger.models`, imported inside the call — the same discipline the
    two functions above keep, and for the same two reasons: `G6` refuses a
    module-scope import of another app's model module from `apps/integrations/`
    (B2 §2), and the module graph has to stay a DAG."""
    from apps.ledger import models as ledger_models

    return ledger_models


def _model() -> Any:
    """The queryset's own model — `JournalEntry`, and the choice is load-bearing.

    ⚠ **THE PAGED UNIT IS THE ENTRY AND NOT THE LINE, BECAUSE THE TRANSFORM
    BELOW NEEDS THE WHOLE ENTRY IN ITS HAND.** Pairing a debit with a credit
    reads every line of one entry; page on LINES and a page boundary can fall
    between the debit and the credit it belongs to, and the last row of one
    page and the first of the next would each be paired against nothing. That
    is not a rounding error, it is two half-postings — and it would look
    perfectly healthy in a test whose fixture is smaller than a page.
    """
    return _models().JournalEntry


def collectable(*, since: date | None = None, until: date | None = None) -> Any:
    """The queryset a partner's page is cut from. No tenant ARGUMENT — the
    tenant is on the session (hard rule 1), exactly as in `seams/billing` and
    `seams/payments`.

    ⚠ **POSTED ONLY. A DRAFT ENTRY IS NOT IN THE BOOKS**, which is
    `seams/billing`'s draft argument one table along: `BR-LED-003` makes a
    draft freely editable and freely deletable, so a finance system that
    collected one would post an entry that may still move or may never exist.
    Nothing in the payload could tell it apart, because nothing that is not
    posted reaches the payload at all.

    ⚠ **BOUNDED BY `entry_date`, WHICH IS THE BOOK DATE AND NOT `posted_at`.**
    `JournalEntry`'s own docstring keeps the two apart for LE-9's reason: July
    closes on Aug 5, and on Aug 7 a payment dated Jul 30 posts *into August*.
    A partner pulling *their* July is asking for the month the entry is
    BOOKED in, because that is the period their own GL will post it to.

    ⚠ **THE `tenant_id` FILTER IS BELT AND BRACES AND IT IS THE THIRD PLACE
    THIS SURFACE NEEDED IT.** RLS `FORCE` scopes this on PostgreSQL, so it is
    redundant in production. **The suite runs on SQLite, which has no RLS**
    (`config/settings/test.py` hardcodes it), so a partner reading another
    utility's books would pass the entire suite if the tenant were stated only
    once (CLAUDE.md law 7, *structurally incapable of failing*). `seams/
    billing.py` and `seams/payments.py` carry the same paragraph.

    ⚠ **THE ORDER ENDS ON `id` AND THAT IS THE PAGING GUARANTEE, NOT A
    TIEBREAKER FOR TIDINESS.** `entry_date` is a DATE, so a month's entries
    share a few hundred values between them; page over that with no second key
    and PostgreSQL may return one entry on page 1 and again on page 2 while
    another is never returned at all. **A missed journal entry is a missed
    posting**, and nothing on either side would raise. `id` is a uuid7 — it is
    unique, it never repeats, and it sorts by creation — so the sequence is
    total and a page boundary falls in the same place on every call.

    ⚠ **THE PREFETCH IS PART OF THE CONTRACT AND NOT AN OPTIMISATION.** A
    month at the top of this product's ICP is ~200,000 journal lines; at a
    thousand entries a page, reading `line.ledger_account.code` without this
    would be a query per line — hundreds of thousands of round trips, and it
    would look perfectly fast on a demo tenant with a hundred. With it, a page
    costs one query for the entries and one for their lines, whatever the page
    holds.
    """
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return _model().objects.none()
    models = _models()
    lines = (
        models.JournalLine.objects.filter(tenant_id=tenant_id)
        .select_related("ledger_account", "account")
        .order_by("side", "id")
    )
    query = _model().objects.filter(tenant_id=tenant_id, status=models.JE_POSTED)
    if since is not None:
        query = query.filter(entry_date__gte=since)
    if until is not None:
        query = query.filter(entry_date__lte=until)
    return query.order_by("entry_date", "id").prefetch_related(
        Prefetch("lines", queryset=lines)
    )


def row_total(queryset: Any) -> int:
    """How many partner ROWS the whole window will produce — the envelope's
    TOTAL, computed in ONE query rather than by walking the pages.

    ⚠ **A PAGE NUMBER OVER A MOVING TABLE SKIPS ROWS, AND A MISSED JOURNAL
    ENTRY IS A MISSED POSTING.** The window bound and the total order are what
    stop that happening; this is what lets a partner PROVE it did not happen.
    Their nightly job adds up the rows it received and compares — and where the
    two disagree it has a number to report instead of a silence to trust.

    ⚠ **IT IS ONE SCALAR AGGREGATE AND NOT A SUM IN PYTHON, WHICH IS THE
    DIFFERENCE BETWEEN A CONSTANT AND A COST PAID ON EVERY PAGE.** The first
    draft annotated each entry and added the numbers up here, which is one query
    but ships **one row per entry in the WINDOW** — 40,000 of them for a month at
    the top of T5, on all 40 page requests of the walk. Measured on the demo
    tenant it read 0.032s over 168 entries, which extrapolates to about seven
    seconds a page and would have looked perfectly fast right up to the first
    real utility. `SUM(...)` over the annotated subquery returns ONE number.

    ⚠ **IT APPLIES `as_record`'s OWN RULE AND MUST NOT DRIFT FROM IT.** One
    entry yields `max(debits, credits)` rows where one side has a single line
    (the pairing), and `debits + credits` where neither does (the unpaired
    branch). The arithmetic lives here, beside the transform it counts, and
    `test_cr110_wave5_partner_ledger.py` asserts the two agree by walking every
    page of a real window and comparing the count to this number — because a
    total computed a second way is free to be wrong in exactly the direction
    nobody checks.
    """
    per_entry = queryset.annotate(
        _debits=Count("lines", filter=Q(lines__side="debit"), distinct=True),
        _credits=Count("lines", filter=Q(lines__side="credit"), distinct=True),
    ).annotate(
        _rows=Case(
            When(Q(_debits=1) | Q(_credits=1), then=Greatest("_debits", "_credits")),
            default=F("_debits") + F("_credits"),
            output_field=IntegerField(),
        )
    )
    return int(per_entry.aggregate(total=Sum("_rows"))["total"] or 0)


def transaction_type(entry: Any) -> dict[str, str]:
    """`{code, label}` for `journal_entries.type`, READ FROM THE ONE PLACE THAT
    PUBLISHES IT rather than typed out here.

    ⚠ **IF A SEAM TYPES A VOCABULARY, THE REFERENCE ENDPOINT AND THE PAYLOAD
    CAN DISAGREE**, and the disagreement is exactly the failure
    `GET /partner/v1/reference` exists to prevent — the PO asked for it in as
    many words: *"you ahve to extend the defination of codes so that partner
    can resolve all codes at there end otherwise they will ahve an issues"*. So
    this asks `reference.transaction_types()` for the very list it publishes
    under the key `transactionType`, and a code it cannot find is a code the
    reference endpoint does not publish either — which is a defect in one place
    instead of two.

    ⚠ **A RECORDED DIVERGENCE FROM THE SPECIFICATION'S SAMPLE
    (`CR-110-BRC04` phase 2 wave 5).** Aclarian's sample draws
    `{"code":"payment","label":"Customer payment"}`. Ours is
    `{"code":"standard","label":"An ordinary entry"}`, because
    `journal_entries.type` is the ledger's entry-type vocabulary —
    standard · accrual · reversing — and it is the one the reference endpoint
    publishes. **The column that holds their word is `source_type`**
    (`invoice`, `payment`, `opening_balance`, `refund`, `credit_note`), and it
    is NOT published: `JournalEntry`'s own docstring records that B2 §2 ships
    it *"with no FK and no chosen vocabulary"* (the O-4 residue), so emitting
    it as a `code` would mint a vocabulary this product has never agreed on and
    hand it to a partner as though it were settled. What a partner gets instead
    is `description`, which names the source document in words. Put to the PO
    with the collapse question; not decided here.
    """
    from apps.integrations import reference

    published = {one["code"]: one["label"] for one in reference.transaction_types()}
    code = str(getattr(entry, "type", "") or "")
    return {"code": code, "label": published.get(code) or reference.derived_label(code)}


def _account_code(line: Any) -> str | None:
    """A ledger account's `code` — `'4100'`, `'2200-01'` — or `None`.

    PO 2026-09-16, verbatim: *"this is already done using setting and plans and
    rates - bills are generated with gl code only"*. Checked and correct:
    `rating.charges.gl_account_id`, `rating.taxes.liability_gl_account_id` and
    tenancy's three defaults all flow onto `invoice_lines.gl_account_id` and
    from there onto the posting, so `accountString` is simply the code of the
    account this line hit. **Nothing is mapped here and nothing is composed.**

    ⚠ **`None` IS AN ANSWER AND NEVER A GUESS.** A line with no resolvable
    account returns null; a partner meeting a null knows to look, where a
    plausible-looking code they cannot find in their chart is a posting into
    the wrong place that both sides believe went well.
    """
    account = getattr(line, "ledger_account", None)
    code = getattr(account, "code", None)
    return str(code) if code else None


def account_code(line: Any) -> str | None:
    """`_account_code` under a name another file may call. **THE ONE GL
    RESOLUTION ON THE PARTNER SURFACE.**

    ⚠ **IT EXISTS SO THERE IS NOTHING TO COPY (`CR-132-BRC07`).** New World's
    receipt needs a GL account for every distribution, exactly as this seam's
    ledger rows need one for every line. Two resolutions would be two things
    that can disagree, and a disagreement between them presents as a
    municipality's books being short by the difference — found, if at all, at a
    month end by somebody who cannot see either of our code paths.

    So the projection in `apps/integrations/newworld.py` calls THIS, and a GL
    rule changes in one place. It delegates and adds nothing: a wrapper that
    began normalising, padding or defaulting would BE the second answer.
    """
    return _account_code(line)


def _consumer_no(*lines: Any) -> str | None:
    """The ACCOUNT number — `AC-2026-00036` — off the line's `account`
    dimension, taking the first line that carries one.

    ⚠ **`None` IS A REAL ANSWER HERE AND MUST NOT BE FILTERED OUT.** A period
    close, a bank fee, a depreciation run and an opening balance are all real
    journal entries with no customer behind them. A partner reconciling a
    month needs exactly those — they are the difference between the customer
    ledger and the general ledger — so an entry with no account is SERVED with
    `consumerNo: null` rather than dropped. Dropping it would make our books
    and theirs disagree by the amount of every one of them, silently.
    """
    for line in lines:
        account = getattr(line, "account", None)
        number = getattr(account, "account_no", None)
        if number:
            return str(number)
    return None


def _entry_reference(entry: Any) -> str | None:
    """`BR-LED-021`'s `JE-` number, or `None` WITH THE REASON NAMED IN THE
    ENVELOPE — never a number composed here.

    ⚠ **`id` IS NOT OUR UUID, AND THAT IS THIS SURFACE'S RULE RATHER THAN THIS
    SEAM'S PREFERENCE.** `seams/billing.as_record` states it for the whole
    partner surface — *"a partner keyed on our uuid is coupled to our storage
    forever"* — and serves `invoice_no`; `seams/payments` serves `payment_no`.
    The ledger's equivalent is `journal_entries.number`.

    ⚠ **THIS DOCSTRING SAID THE NUMBER IS NEVER STAMPED AND THAT STOPPED BEING
    TRUE ON 2026-09-24 (`DEF-INT-6601`, Finance blueprint `P5.1`).** It read
    *"NULL ON EVERY SOURCE-EVENT ENTRY IN THE PRODUCT TODAY — MEASURED, 168 OF
    168 … `posting.post_draft()` stamps it and `posting.post()` — the path
    every bill, payment, opening balance, refund and credit note takes — does
    not."* **`posting.post()` allocates its own number now**
    (`apps/ledger/posting.py::post`, through `_allocated_number`; `P0.3`, commit
    `b813394a6`), so every entry posted from that morning on carries one and
    this function returns it. The claim was true when it was written and was
    superseded without being moved, which is CLAUDE.md hard-won law 1 in its
    mirror — a comment claiming an ABSENCE.

    ⚠ **WHAT IS STILL NULL IS HISTORY, AND THAT DIFFERENCE IS WHY THE ENVELOPE
    CODE WAS RENAMED RATHER THAN DELETED.** Entries posted BEFORE `P0.3` were
    written with no number and nothing backfills them — **measured on the demo
    tenant, PostgreSQL 16.13, 2026-09-24: 167 posted entries, 0 numbered.** So a
    partner pulling a window that reaches back before the change still meets
    nulls, and the envelope has to say *these entries pre-date our numbering*
    rather than *this product does not number entries*. A gap code naming a
    cause that has since been fixed is this repo's most-filed rot; CLAUDE.md
    hard rule 4 records the identical rename on
    `amendment_history_is_not_a_permanent_record`.

    **A partner-surface lane still does not MINT an identifier**, and that has
    not moved an inch: composing a number here would be a second allocator
    against one series, which is how two entries end up carrying one number and
    a partner's books are the last place that should be discovered. This reads
    the column and does nothing else.
    """
    number = getattr(entry, "number", None)
    return str(number) if number else None


# ═══════════════════════════════════════════════════════════════════════════
# P5.2 · THE TAX AUTHORITY · P5.3 · THE DOCUMENT NUMBER
# ═══════════════════════════════════════════════════════════════════════════
#
# Both are PAGE reads and neither may be done per row. `collectable` already
# carries the paragraph: a month at the top of T5 is ~200,000 journal lines,
# so a resolution done inside `as_record` is a query per line and it looks
# perfectly fast on a demo tenant with a hundred. `seams/billing.PageContext`
# is the shape this follows, for the same reason and with the same words.


class LedgerPageContext:
    """Everything a page of journal entries needs that is not on the row.

    ⚠ **IT EXISTS SO A THOUSAND-ENTRY PAGE IS NOT THOUSANDS OF ROUND TRIPS**,
    which is `seams/billing.PageContext`'s own argument one table along. The
    tax authority behind a line and the document number behind an entry are
    two reads for the WHOLE page here, and two reads PER LINE if `as_record` is
    left to resolve them itself.

    `as_record` still works with no context at all: it builds one for the
    single entry it was handed. One composer, two callers, no second answer.
    """

    __slots__ = ("authorities", "documents")

    def __init__(
        self,
        *,
        authorities: dict[str, dict[str, Any]],
        documents: dict[tuple[str, str], dict[str, str]],
    ) -> None:
        self.authorities = authorities
        self.documents = documents


def _tax_authorities(authority_ids: set[str]) -> dict[str, dict[str, Any]]:
    """`rating.TaxJurisdiction` by id, as the fields a PARTNER may see.

    ⚠ **THE UUID IS NOT ONE OF THEM, AND B14 RULE 31 IS ONLY HALF THE REASON.**
    The rule is about a screen; this is a wire. `seams/billing.as_record`
    states the wire half for the whole partner surface — *"a partner keyed on
    our uuid is coupled to our storage forever"* — so the authority travels as
    the four things a tax office is actually known by: its `name`, the
    `authority` that levies it, its `level`, and the `referenceNo` a utility
    files under. A partner splitting a remittance cheque needs those; it has no
    use for our primary key and every reason not to store it.

    ⚠ **THE FK IS THE REVIEWED CROSS-MODULE ONE AND NOT A NEW REACH.**
    `journal_lines.tax_authority_id → rating.TaxJurisdiction` is in B2 §2's
    interface set and `apps/ledger/models.py` carries it as `r16 #7`. This seam
    imports rating's models inside the call for the reason `_models()` gives —
    integrations loads at `AppConfig.ready()` and rating must not have to.

    ⚠ **AN ID THAT RESOLVES TO NOTHING IS LEFT OUT RATHER THAN FAKED.** A line
    naming an authority this tenant cannot read is a line whose authority we
    cannot state, and `None` on the row says exactly that. Inventing a label
    from the uuid would put a plausible-looking authority on a tax figure, and
    a remittance is the last place to discover it.
    """
    if not authority_ids:
        return {}
    try:
        from apps.rating import models as rating_models
    except Exception:  # pragma: no cover — a deployment with no rating module
        return {}
    tenant_id = current_tenant_id()
    if tenant_id is None:
        return {}
    rows = rating_models.TaxJurisdiction.objects.filter(
        tenant_id=tenant_id, id__in=sorted(authority_ids)
    )
    return {
        str(one.id): {
            "name": one.name or None,
            "authority": one.authority or None,
            "level": one.level or None,
            "referenceNo": one.reference_no or None,
        }
        for one in rows
    }


#: The source kinds whose printed number this seam can resolve, and the SEAM
#: that owns each. ⚠ **INTEGRATIONS ASKS ITS OWN SEAM FILES, WHICH IS WHY
#: `P5.3` WAS BUILDABLE HERE AND NOT IN `apps/ledger`.**
#:
#: ⚠ **AMENDED 2026-09-24 — THE SCREEN HALF IS CLOSED AND THIS COMMENT SAID IT
#: WAS OPEN.** It read *"the Finance SCREEN's Reference column has the identical
#: gap (`reference_is_the_source_id_not_the_document_number`) and cannot close
#: it the same way"*. `P5.8` landed that day: billing publishes
#: `invoice_numbers_for` and `credit_note_numbers_for`, payments publishes
#: `payment_numbers_for`, `apps/ledger/{billing,payments}_seam` resolve them BY
#: NAME, and the retired gap code no longer exists anywhere. **This list and
#: `apps/ledger/billing_seam.BILLING_DOCUMENT_READS` +
#: `payments_seam.PAYMENT_DOCUMENT_SOURCE` must now name the SAME THREE KINDS**
#: — a screen that resolved fewer than the wire would print a uuid on exactly
#: the row the feed can name, with every test green (`DEF-LED-6653`).
_DOCUMENT_SOURCES: dict[str, tuple[str, str]] = {
    "invoice": ("billing", "invoice_no"),
    "credit_note": ("billing", "credit_note_no"),
    "payment": ("payments", "payment_no"),
}


def _document_numbers(wanted: dict[str, set[str]]) -> dict[tuple[str, str], dict[str, str]]:
    """`{(source_type, source_id): {"type": …, "number": …}}` for one page.

    ⚠ **WHAT THIS ANSWERS FOR, MEASURED RATHER THAN CLAIMED** — the demo
    tenant's 167 posted entries, PostgreSQL 16.13, 2026-09-24:

        invoice           80  → `invoices.invoice_no`         RESOLVED
        payment           66  → `payments.payment_no`         RESOLVED
        opening_balance   19  → there is no document          CORRECTLY NULL
        credit_note        1  → `credit_notes.credit_note_no` RESOLVED
        refund             1  → `refunds` HAS NO NUMBER COLUMN

    So **147 of 167 carry a printed number, 19 are not documents at all, and
    exactly one is a real gap** — a refund, whose number arrives with `P3.3`.
    An entry this cannot answer for keeps `documentNo: null`, and the envelope
    does not apologise for the 19: an opening balance HAS no document, and a
    note saying otherwise would be rationale on a wire.

    ⚠ **A MISS IS A NULL AND NEVER THE UUID.** The whole task is *document
    number, not internal id*; falling back to the source id would put the exact
    value `P5.3` exists to remove onto the field named for its replacement, and
    it would read as an answer.
    """
    resolved: dict[tuple[str, str], dict[str, str]] = {}
    for source_type, ids in wanted.items():
        route = _DOCUMENT_SOURCES.get(source_type)
        if route is None or not ids:
            continue
        module, column = route
        try:
            if module == "billing":
                from apps.billing import models as owner_models

                model = (
                    owner_models.Invoice if column == "invoice_no" else owner_models.CreditNote
                )
            else:
                from apps.payments import models as owner_models  # type: ignore[no-redef]

                model = owner_models.Payment
        except Exception:  # pragma: no cover — a deployment without that module
            continue
        tenant_id = current_tenant_id()
        if tenant_id is None:
            continue
        rows = model.objects.filter(tenant_id=tenant_id, id__in=sorted(ids)).values_list(
            "id", column
        )
        for row_id, number in rows:
            if number:
                resolved[(source_type, str(row_id))] = {
                    "type": source_type,
                    "number": str(number),
                }
    return resolved


def page_context(entries: list[Any]) -> LedgerPageContext:
    """The two shared reads for ONE page of journal entries.

    Both are driven off the page's own rows, so a window with no tax lines
    costs no tax query and a window of opening balances costs no document
    query. `_tax_authorities` and `_document_numbers` each return `{}` for an
    empty ask and neither touches the database for one.
    """
    authority_ids: set[str] = set()
    wanted: dict[str, set[str]] = {}
    for entry in entries:
        source_type = getattr(entry, "source_type", None)
        source_id = getattr(entry, "source_id", None)
        if source_type and source_id:
            wanted.setdefault(str(source_type), set()).add(str(source_id))
        for line in entry.lines.all():
            if line.tax_authority_id:
                authority_ids.add(str(line.tax_authority_id))
            line_type = getattr(line, "source_type", None)
            line_id = getattr(line, "source_id", None)
            if line_type and line_id:
                wanted.setdefault(str(line_type), set()).add(str(line_id))
    return LedgerPageContext(
        authorities=_tax_authorities(authority_ids),
        documents=_document_numbers(wanted),
    )


def _source_document(entry: Any, line: Any, context: LedgerPageContext) -> dict[str, str] | None:
    """The printed number behind this row — the LINE's source first, the
    ENTRY's second.

    ⚠ **THE LINE WINS AND THE ORDER IS THE POINT.** `JournalLine` carries its
    own `source_type`/`source_id`, *"distinct from the entry's: one issue
    entry's lines trace to individual `invoice_line` rows"*
    (`apps/ledger/models.py`). Where a line names its own document that is a
    finer answer than the entry's and it is the one a partner can act on;
    where it does not, the entry's applies to every row it produced.
    """
    for source_type, source_id in (
        (getattr(line, "source_type", None), getattr(line, "source_id", None)),
        (getattr(entry, "source_type", None), getattr(entry, "source_id", None)),
    ):
        if not source_type or not source_id:
            continue
        found = context.documents.get((str(source_type), str(source_id)))
        if found is not None:
            return found
    return None


def as_record(entry: Any, context: LedgerPageContext | None = None) -> list[dict[str, Any]]:
    """ONE journal entry, as the ROWS a partner's ledger takes. **Note the
    return type: a LIST, and the plural is the shape problem made visible in
    the signature** — `seams/billing.as_record` and `seams/payments.as_record`
    each return one dict because one bill is one bill, and one balanced entry
    is not one partner row.

    ── WHAT AN ENTRY BECOMES, AND WHY ──────────────────────────────────────
    Aclarian's row names a `debitAccount` and a `creditAccount` and carries one
    `amount`. Our entry is N lines, each a side and an amount. Three shapes
    arrive and two rules cover them:

    **1 · ONE DEBIT, ONE CREDIT — one row, exactly their shape.** 83 of the
    demo tenant's 168 entries. Nothing is lost and nothing is chosen.

    **2 · ONE LINE ON ONE SIDE, N ON THE OTHER — N rows, each pairing one line
    of the many side against the single COMMON line.** 85 of 168, and it is the
    shape a bill takes: one debit to `1200 Accounts receivable` against five
    credits — `4100` electric usage, `4105` electric base, `4110` water usage,
    `4115` water base and `2200-01` tax. **The pairing is arithmetic and not a
    judgment**: each row's `amount` is the many-side line's own amount, so the
    rows sum to the entry's total on both sides and no allocation is invented.
    The mirror — five debits against one credit — is the same rule and is in
    the demo tenant once.

    **3 · MORE THAN ONE LINE ON BOTH SIDES — WE DO NOT PAIR, AND THE ROW SAYS
    SO.** There is no arithmetic that pairs three debits with four credits:
    which debit funds which credit is an ALLOCATION RULE, and the specification
    is explicit that *"Final debit/credit handling and GL mapping should follow
    the accounting rules agreed with Aclarian"*. **Inventing one is the one
    thing this wave was told not to do**, and picking the first line and
    calling it the counter-account — the obvious move — would put a real
    amount against an account that never saw it, on a row that reads as
    settled. So each line becomes its own row with ITS OWN side filled and the
    counter-account `null`: a partner meeting a null knows to look. **No such
    entry exists in the product today** (measured: every one of the 168 has
    exactly one line on one side), which is precisely why the branch is written
    now rather than discovered by a customer.

    ⚠ **IT BALANCES IN BOTH BRANCHES, WHICH IS THE PROPERTY THIS TRANSFORM IS
    GRADED ON.** In the paired branch a row's `amount` is both a debit to
    `debitAccount` and a credit to `creditAccount`, so Σ rows = Σ debits =
    Σ credits. In the unpaired branch each row's amount belongs to ONE side, so
    Σ over rows naming a `debitAccount` = Σ debits and Σ over rows naming a
    `creditAccount` = Σ credits, and the entry's own balance makes them equal.
    `test_cr110_wave5_partner_ledger.py` asserts it on the six-line bill, not
    on a two-line entry — a two-line fixture proves nothing about the case that
    is hard.

    ⚠ **AND THE PARTNER'S OWN TWO SIDES CANNOT PROVE IT, WHICH IS WORTH KNOWING
    BEFORE SOMEBODY WRITES THAT CHECK.** A PAIRED row carries ONE amount that is
    both its debit and its credit, so Σ debits = Σ credits across the paired rows
    **by construction** — hand this function a deliberately lopsided entry and
    the payload still balances perfectly. The check that actually bites compares
    the partner's total against **OUR OWN** debit total, and that is the one the
    test file makes. What guarantees the input is balanced in the first place is
    `ledger/migrations/0002`'s balance trigger, which refuses an unbalanced post
    in the DATABASE — not anything in this file.

    ── THE FIELDS ──────────────────────────────────────────────────────────
    `transactionDate` is `entry_date` — the BOOK date — rendered as the
    specification draws it, midnight UTC. A partner's GL period is the book
    date's; `posted_at` is when the entry became immutable, which is our fact
    and not theirs.

    `accountString` is the code of **the line that gave this row its amount**.
    On a bill that is the revenue or tax account, and on a payment it is the
    receivable — which is what Aclarian's own sample draws, where
    `accountString` and `creditAccount` are the same string. It is always one
    of the two accounts already on the row and never a third thing; where the
    row is unpaired it is that line's own account.

    `description` is the entry's memo — *"Bill BL-2607-000014 issued"*,
    *"Payment PY-260808-0012"* — which names the source DOCUMENT, so a partner
    can tie a ledger row back to the bill or payment it already pulled from
    `/partner/v1/bills` and `/…/payments` without us joining across a module
    boundary on every line of a 200,000-row month.
    """
    lines = list(entry.lines.all())
    models = _models()
    debits = [one for one in lines if one.side == models.SIDE_DEBIT]
    credits = [one for one in lines if one.side == models.SIDE_CREDIT]

    if context is None:
        context = page_context([entry])

    reference_no = _entry_reference(entry)
    shared = {
        "transactionDate": f"{entry.entry_date.isoformat()}T00:00:00Z",
        "transactionType": transaction_type(entry),
        "description": entry.memo or None,
    }

    def _row(ordinal: int, amount: Any, debit: Any, credit: Any, filed: Any) -> dict[str, Any]:
        # `P5.2` — the tax authority, off the line that GAVE THIS ROW ITS
        # AMOUNT, which is the same line `accountString` is taken from. On a
        # bill that is the revenue or tax account, so the tax row names its
        # authority and the four revenue rows name none — which is the split a
        # partner cannot make from this feed at all today. ⚠ **MEASURED: 0 of
        # the demo tenant's 661 journal lines carry an authority**, because
        # every one of them was posted before `P0.3` published
        # `rating.selectors.tax_authority_id_for_tax` for billing to stamp with
        # (2026-09-24). New posts carry it; nothing backfills the old ones.
        authority_id = getattr(filed, "tax_authority_id", None)
        document = _source_document(entry, filed, context)
        return {
            "id": reference_no,
            # `P5.3` — the SOURCE DOCUMENT'S PRINTED NUMBER, which is what a
            # partner holds in its hand. `null` where there is no document (an
            # opening balance, a period close) or where the document carries no
            # number yet; never our uuid, which is the identifier this task
            # exists to stop handing out.
            "documentNo": document["number"] if document else None,
            "documentType": document["type"] if document else None,
            "taxAuthority": context.authorities.get(str(authority_id))
            if authority_id
            else None,
            # One entry can be several rows, so the ROW reference carries its
            # ordinal — a partner keying on a value repeated five times would
            # collapse a bill's five revenue rows into one and post a fifth of
            # it. `None` when the entry carries no number at all; see
            # `_entry_reference`, and the envelope names the reason once.
            "transactionId": f"{reference_no}-{ordinal}" if reference_no else None,
            "consumerNo": _consumer_no(filed, *lines),
            "debitAccount": _account_code(debit) if debit is not None else None,
            "creditAccount": _account_code(credit) if credit is not None else None,
            "amount": display_amount(amount),
            "currency": entry.currency,
            "accountString": _account_code(filed),
            **shared,
        }

    # Branch 2 (and 1, which is its N = 1 case): one side has a single line.
    if len(debits) == 1 and len(credits) >= 1:
        common = debits[0]
        return [
            _row(n, one.amount, common, one, one) for n, one in enumerate(credits, start=1)
        ]
    if len(credits) == 1 and len(debits) >= 1:
        common = credits[0]
        return [
            _row(n, one.amount, one, common, one) for n, one in enumerate(debits, start=1)
        ]

    # Branch 3: many on both sides, or an entry with a side missing entirely
    # (which the balance trigger forbids, and which is therefore a row this
    # code should hand over rather than interpret). One row per line, its own
    # side filled, the counter-account null.
    return [
        _row(
            n,
            one.amount,
            one if one.side == models.SIDE_DEBIT else None,
            one if one.side == models.SIDE_CREDIT else None,
            one,
        )
        for n, one in enumerate(lines, start=1)
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-110-BRC04 phase 2 wave 5 · CR-083 (PO 2026-09-07) · CR-069 §11 (one seam file per neighbouring module)
# generated: 2026-09-07 by the CR-083 integrations sample-data lane; read path 2026-09-16 by the CR-110-BRC04 wave 5 lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H✔(no money math — the amounts are ledger's own and are only FORMATTED here, 4 stored to 2 displayed)
# gates: pytest tests/test_cr110_wave5_partner_ledger.py · pytest tests/test_cr083_integrations_sample_data.py · G6 (no module-scope import of another app)
# exceptions: (1) `as_record` returns a LIST where its two siblings return one dict — one balanced entry is not one partner row, and the plural is the shape problem made visible in the signature · (2) `collectable` hands back a QUERYSET, matching `seams/billing` and `seams/payments` exactly, because the caller pages it; what crosses into JSON is plain dicts · (3) an entry with several lines on BOTH sides is NOT flattened and the counter-account is left null — no such entry exists in the product today and the allocation rule is Aclarian's to agree (`OQ-INT-12393`)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

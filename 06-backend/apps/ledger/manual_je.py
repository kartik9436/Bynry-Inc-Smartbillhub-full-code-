# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-011 (manual JE: draft → post lifecycle, three types, balanced
#           at post — TC-1..TC-7) · US-LED-012 (accrual auto-reverse: day 1 of
#           the next period, linked both ways — TC-1..TC-7)
#           Screens: S57 · S56
# Rules:    BR-LED-003 (drafts freely editable/deletable before post; balanced
#           required AT POST; posted = immutable; reason + audit; System Admin /
#           Billing Clerk per OQ-175) · BR-LED-005 (accrual JEs auto-reverse on
#           day 1 of the next period, linked BOTH ways) · BR-LED-021 (the `JE-`
#           series, allocated per tenant and stamped AT POST) · BR-LED-001
#           (source_type `manual_je` + dimensions on every line) · BR-LED-015
#           (every finance action audits) · BR-TEN-022 (period boundaries from
#           fiscal settings) · BR-TEN-038 (closed-period dating auto-forwards) ·
#           BR-TEN-035 (numbering: allocated per tenant, gaps ok, never reused) ·
#           CLAUDE.md rule 1 · rule 4 · rule 5 · rule 6 · rule 7
# Golden:   LE-4 — Sep 30 accrual DR 1210 500.00 / CR 4100 500.00 → Oct 1 mirror
#           DR 4100 500.00 / CR 1210 500.00, linked both ways, 1210 nets 0.00
# Tests:    06-backend/tests/test_us_led_011_manual_je.py ·
#           06-backend/tests/test_us_led_012_accrual_auto_reverse.py
# Impacts:  apps/ledger/posting.py (the sole writer — save_draft/delete_draft/
#           post_draft/reverse_entry are called from here and nothing else in
#           this file touches journal_entries or journal_lines) ·
#           apps/ledger/close.py (every date passes through resolve_entry_date)
# ───────────────────────────────────────────────────────
"""The manual journal entry, and the accrual that reverses itself.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module authors money entries a human
typed and decides when they enter the books. AI-authored 2026-08-15 under the PO
ruling of 2026-08-09; row owed in 12-governance/09-human-review-ledger.md. Not on
the G7 glob list yet — REPORTED for the daily batch rather than self-added
(B12 r2, *"who watches the watchers"*).

════════════════════════════════════════════════════════════════════════════
THIS FILE WRITES NO JOURNAL ROW. NOT ONE.
════════════════════════════════════════════════════════════════════════════
Every insert, update and delete on `journal_entries` / `journal_lines` goes
through `apps/ledger/posting.py` (CLAUDE.md rule 5), and `ledger/0004`'s
sole-writer trigger is what makes that structural rather than a promise: this
module never opens the write window and could not insert a row if it tried.
Grep it — there is no `objects.create(`, no `.save(`, no `.delete(` on a journal
model anywhere below.

What this module owns is everything AROUND the write: the role gate, the
`JE-` number, the closed-period dating, the audit context, and the day-1
schedule.

════════════════════════════════════════════════════════════════════════════
THE LIFECYCLE, IN THE PO's OWN TERMS (BR-LED-003)
════════════════════════════════════════════════════════════════════════════
    draft  (editable · deletable · WORTHLESS · no JE- number)
      --post (balanced + memo + role)-->  posted (IMMUTABLE, hard rule 4)
                                          + JE- number stamped HERE

*"Worthless"* is the PO's word and it is load-bearing: a draft touches nothing,
sums into no report, and deleting one leaves the books byte-identical. That is
why `delete_draft` exists at all — hard rule 4 has no exception for posted
entries and needs none for drafts, because a draft never entered anything.

════════════════════════════════════════════════════════════════════════════
THE `JE-` NUMBER, AND THE ONE THING THAT IS NOT WIRED
════════════════════════════════════════════════════════════════════════════
BR-LED-021 (PO 2026-08-12, OQ-176 — *"Approve a JE- series"*): the number is
allocated per tenant from the ninth `number_series` under BR-TEN-035 and stamped
**at POST**. `core/numbering.JOURNAL_ENTRY` is that series and `post_manual_je`
allocates it inside the posting transaction, exactly as a bill number is
allocated inside issue.

✔ **THE SERIES IS SEEDED — CR-005 CLOSED THIS ON 2026-08-17, and the paragraph
that used to stand here is kept in outline because the REPORT is what fixed it.**
It read: *"NO TENANT HAS THE SERIES ROW YET, AND THIS MODULE REPORTS THAT RATHER
THAN FAKING A NUMBER"* — `SERIES_DEFAULTS` seeded five series while nine were
known, the journal one was not among them, and this lane could not reach into
`apps/tenancy/**` to fix it, so it named the one-line fix instead:

    SERIES_DEFAULTS[core_numbering.JOURNAL_ENTRY] = "JE-{000000}"

The tenancy lane made it structural rather than one line — `SERIES_DEFAULTS` is
now derived from `core.numbering.SERIES_CATALOG`, so a series can no longer be
KNOWN and unseeded — and `JE-{000000}` is the seeded default for every tenant,
the exact string named above. **A tenant whose series opens at 104 posts
JE-000104** (`tests/test_us_led_011_manual_je.py`).

⚠ **TWO THINGS THIS DOES NOT CLOSE.** (1) An entry posted during the gap is
posted forever unnumbered — hard rule 4 forbids stamping it afterwards, and
nothing here tries. (2) A tenant provisioned BEFORE 2026-08-17 still has no row
until `manage.py seed_demo --tenant <subdomain>` runs, so the refusal path below
is live code, not history: a manual JE **posts with `number = None`** and the
result and the audit row carry `JOURNAL_NUMBER_SERIES_NOT_SEEDED`, which the S56
list surfaces as `posted_entries_without_a_je_number`. Refusing to post at all
was considered and rejected — it would make the whole manual-JE feature dead on
such a host over a seed row, and BR-LED-003's lifecycle does not depend on the
number. Composing a number here was rejected outright: BR-TEN-035 makes numbering
tenant-visible and format-configurable, and a second allocator is how two entries
end up as JE-14.

**A posted entry can never be numbered afterwards** (hard rule 4 — `number` is in
`ledger_journal_entry_immutable()`'s frozen list from `ledger/0007`), so an entry
posted during the gap stays unnumbered forever. That is the cost, stated.

════════════════════════════════════════════════════════════════════════════
BR-LED-005 — WHY THE AUTO-REVERSAL IS A JOB AND NOT A TRIGGER
════════════════════════════════════════════════════════════════════════════
LE-4: *"Sep 30 JE-201 (accrual): DR 1210 Unbilled AR 500.00 / CR 4100 500.00 →
Oct 1 JE-202 auto-posts the mirror, both linked. October's real bill run posts
normally — no double-count."*

The mirror is posted by `apps.ledger.posting.reverse_entry`, which READS the
accrual and swaps the sides. It is never hand-composed: a compensating entry
computed a second time could disagree with what it claims to reverse, which is
the one thing a reversal may never do, and BR-LED-005's *"no double-count"* is a
promise about two entries netting to exactly zero.

It runs as an idempotent SWEEP (`run_accrual_auto_reversals`) rather than a
scheduled per-entry timer, for three reasons that are all about recovery: a
sweep that did not run yesterday catches up today; a replay writes nothing
(`posting_key` is `journal_entry|<accrual id>|auto_reversed`, one string per
accrual, forever); and the CLOSE CHECKLIST can ask the same question the sweep
asks — *"is any accrual's mirror overdue?"* — which is what makes
`close._accruals_item` a real check instead of a tick.

**TC-5's "no suppress path exists" is a property of this design**, not a guard
in it: there is nothing to suppress. The sweep looks at the books, and an
accrual with no mirror gets one the next time it runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db import transaction

from apps.ledger import close, models, posting
from core import errors
from core import numbering as core_numbering
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

#: BR-LED-001 / US-LED-011 §5: *"Source stamp | source_type `manual_je` | on
#: every line"*. One constant so the write and every read of it agree.
SOURCE_MANUAL_JE = "manual_je"
EVENT_POSTED = "posted"

#: US-LED-012's own replay key event. Deliberately NOT `reversed` — that string
#: belongs to US-LED-013's one-click correction, and a shared event would make a
#: human's reversal and the schedule's mirror indistinguishable in the guard.
EVENT_AUTO_REVERSED = "auto_reversed"

ZERO = Decimal("0")


class ManualJournalError(RuntimeError):
    """A manual-JE request the ledger refuses, with the reason a human can act on.

    Distinct from `apps.ledger.posting.PostingError` so a caller can tell *"the
    ledger refused the ACT"* (no memo, wrong role, a posted entry sent to the
    draft path) from *"the books refused the ENTRY"* (unbalanced, foreign
    account, float amount) without matching on prose. Same argument as
    `apps.ledger.journal.JournalActionError`.
    """


JOURNAL_NUMBER_SERIES_NOT_SEEDED = {
    "code": "journal_number_series_is_not_seeded",
    "br_ref": "BR-LED-021 · BR-TEN-035",
    "detail": "BR-LED-021 (PO 2026-08-12, OQ-176 — *\"Approve a JE- series\"*) allocates a `JE-` "
    "number per tenant and stamps it AT POST. `core/numbering.JOURNAL_ENTRY` is the ninth "
    "series and this entry asked for a number, but this tenant has no `journal_entry` row in "
    "`number_series`: provisioning seeds one row per entry in "
    "`apps.tenancy.services.SERIES_DEFAULTS` and that map has five entries, none of them the "
    "journal. The entry POSTS — the lifecycle does not depend on the number and refusing would "
    "kill the whole feature over a seed row — and it posts UNNUMBERED, forever, because "
    "`number` is frozen once posted (hard rule 4, ledger/0007). A number is never composed "
    "here: BR-TEN-035 makes numbering tenant-visible and format-configurable, and a second "
    "allocator is how two entries end up as JE-14.",
    "wanted_reads": ("apps.tenancy.services.SERIES_DEFAULTS[core.numbering.JOURNAL_ENTRY]",),
}

ROLE_GATE_IS_A_READING = {
    "code": "manual_je_role_gate_is_a_reading_not_a_ruling",
    "br_ref": "BR-LED-003 (OQ-175, CLOSED for REVERSAL only)",
    "detail": "US-LED-011 TC-5 wants S57 gated to *Finance/Owner*, and this product has no "
    "Finance and no Owner — the three roles are system_admin / billing_clerk / executive "
    "(BR-IDN-008). The PO ruled *\"System Admin, Billing Clerk\"* on 2026-08-12 (OQ-175) about "
    "REVERSING a posted entry, and EP-LED-05 §8 already flags that carrying those two roles to "
    "the other ledger writes is a READING. It is carried here — an executive reads the books, a "
    "clerk writes them — and marked, because a signature covers only what was shown.",
    "wanted_reads": (),
}


def _tenant_id() -> UUID:
    """CLAUDE.md rule 1 — no tenant table is touched without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


@dataclass(frozen=True)
class ManualLine:
    """One S57 GL row as a human typed it: an account, a side, an amount.

    ⚠ **THE PARAGRAPH BELOW WAS THE RULING UNTIL 2026-09-25 AND IS NOW
    SUPERSEDED — READ IT IN THE PAST TENSE (hard-won law 1).** It said the
    dimensions are absent *"and that is the ruling rather than an omission"*,
    and on 2026-09-25 the PO ruled the opposite, verbatim: *"a — Add the five
    tags, keep them optional"* (`OQ-LED-12629`, option (a) of three). **The five
    tags — service · account · premises · unit · tax authority — ARE to be
    captured on the hand-typed entry, and they stay OPTIONAL.**

    **WHAT IS STILL TRUE, AND IT IS MOST OF IT.** Nothing on this dataclass has
    moved yet: the build is `P1.16`, which the ruling UNBLOCKS and which is a
    separate piece of work. `source_type='manual_je'` + the entry's own
    `source_id` remain unconditional under `BR-LED-001`, and they are still what
    makes an auditor's *"what is this?"* answerable. What changed is the reason
    the five are missing — it was a decision, and it is now an unbuilt one.

    ⚠ **WHAT THE RULING DID NOT DECIDE, so that `P1.16` does not read it as
    licence.** The PO chose (a), OPTIONAL, over (b) refuse-without-a-service and
    over (c) optional-plus-a-stated-absence on each report. **So the catch-all
    row STAYS and no report may grow a "we could not place this" line** — that
    was (c) and it was declined. And `BR-LED-001`'s *"where it applies"* STILL
    has no rule: which of the five APPLY to a hand-typed reclassification is
    unruled, and a lane needing that answer mints a question rather than
    choosing one.

    **SUPERSEDED (PO 2026-09-25, `OQ-LED-12629` option (a) → the five tags are
    added, optional):** *The seven BR-LED-001 dimensions are NOT on this
    dataclass and that is the ruling rather than an omission. US-LED-011 §5 maps
    the modal's fields — Date, Type, Memo, GL line (account, DR/CR, amount) —
    and nothing else; a manual reclass between two GL accounts has no invoice,
    no premises and no service.*
    """

    ledger_account_id: Any
    side: str
    amount: Decimal


@dataclass(frozen=True)
class ManualDraftResult:
    """A saved draft, and what it WOULD post — including the gap if it is wrong."""

    entry_id: str
    created: bool
    entry_date: date
    entry_type: str
    debits: Decimal
    credits: Decimal
    balanced: bool
    gap: Decimal
    line_count: int
    date_note: dict[str, Any] | None = None
    unavailable: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ManualPostResult:
    """A posted manual JE — LE-4's JE-201, with its number if it has one."""

    entry_id: str
    number: str | None
    posting_key: str
    created: bool
    entry_date: date
    debits: Decimal
    credits: Decimal
    line_count: int
    date_note: dict[str, Any] | None = None
    unavailable: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class AutoReversalResult:
    """One accrual's day-1 mirror (US-LED-012), or the reason it did not get one."""

    accrual_entry_id: str
    mirror_entry_id: str | None
    posting_key: str
    created: bool
    due_on: date
    entry_date: date | None
    amount: Decimal
    skipped: str | None = None
    date_note: dict[str, Any] | None = None


def _posting_lines(lines: tuple[ManualLine, ...], source_id: Any) -> tuple[posting.PostingLine, ...]:
    """Manual rows → posting lines, with BR-LED-001's two mandatory dimensions."""
    return tuple(
        posting.PostingLine(
            ledger_account_id=row.ledger_account_id,
            side=row.side,
            amount=row.amount,
            source_type=SOURCE_MANUAL_JE,
            source_id=source_id,
        )
        for row in lines
    )


def _refuse_unless_lines_given(lines: Any) -> tuple[ManualLine, ...]:
    if not lines:
        raise ManualJournalError(
            "a journal entry needs at least one GL line. S57 opens with two empty rows and a "
            "*+ Add line* button; saving nothing saves nothing."
        )
    return tuple(lines)


def _allocate_number(entry_date: date) -> tuple[str | None, dict[str, Any] | None]:
    """BR-LED-021's number, or the named reason there is none.

    Allocated with the tenant's own series through `core.numbering` — inside the
    caller's transaction, which is what BR-TEN-035 requires and what makes two
    clerks posting at once get two different numbers.
    """
    try:
        return core_numbering.next_number(core_numbering.JOURNAL_ENTRY, entry_date), None
    except core_numbering.NumberingError:
        return None, JOURNAL_NUMBER_SERIES_NOT_SEEDED


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-011 — the draft lifecycle
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-003")
def save_manual_je(
    actor: Any,
    *,
    entry_date: date,
    entry_type: str = models.JE_STANDARD,
    memo: str | None = None,
    lines: Any = (),
    currency: str = "USD",
    entry_id: Any = None,
) -> ManualDraftResult:
    """S57's *Save draft* — TC-1, and TC-4's unbalanced draft.

    The draft may be UNBALANCED and is saved anyway (BR-LED-003: *drafts freely
    editable*), with `gap` carrying what S57's *Must balance* footer shows. What
    it may NOT be is unreadable: a float amount, a negative, a third decimal
    (BR-LED-025), an unknown side, a foreign account — all refused by the posting
    service's validator at Save, where a human can still fix them, rather than at
    Post, where the modal has already been closed once.

    **The date is resolved through the close (BR-TEN-038) at SAVE as well as at
    POST**, so a clerk drafting into a closed July sees the forwarded date while
    the modal is still open rather than discovering it after confirming.
    """
    rows = _refuse_unless_lines_given(lines)
    if entry_type not in models.JE_TYPES:
        raise ManualJournalError(
            f"journal entry type {entry_type!r} is not one of {models.JE_TYPES}. S57 offers "
            "Standard / Accrual / Reversing (A1 r2), and the choice is not cosmetic: an ACCRUAL "
            "schedules its own day-1 mirror (BR-LED-005)."
        )
    resolved, note = close.resolve_entry_date(entry_date)
    # The draft's own document id. Minted once at creation and REUSED on every
    # later save, so an edited draft's lines keep pointing at the same document
    # the entry does — a second uuid on the second save would leave the entry
    # tracing to one thing and its lines to another.
    source_id = _draft_source_id()
    if entry_id is not None:
        existing = models.JournalEntry.objects.filter(
            tenant_id=_tenant_id(), pk=entry_id
        ).first()
        source_id = (existing.source_id if existing and existing.source_id else entry_id)
    result = posting.save_draft(
        posting.DraftRequest(
            entry_date=resolved,
            currency=currency,
            lines=_posting_lines(rows, source_id),
            memo=(str(memo).strip() if memo else None),
            entry_type=entry_type,
            source_type=SOURCE_MANUAL_JE,
            source_id=source_id,
        ),
        entry_id=entry_id,
        actor=actor,
    )
    return ManualDraftResult(
        entry_id=result.entry_id,
        created=result.created,
        entry_date=resolved,
        entry_type=entry_type,
        debits=result.debits,
        credits=result.credits,
        balanced=result.balanced,
        gap=abs(result.debits - result.credits),
        line_count=result.line_count,
        date_note=note,
        unavailable=(ROLE_GATE_IS_A_READING,),
    )


def _draft_source_id():
    """A stable id for a draft's own lines to point at.

    BR-LED-001 requires `source_id` on EVERY line and a brand-new draft has no
    entry id yet (the row is created by the same call that writes the lines). A
    fresh uuid7 is minted here and travels onto both the entry and its lines, so
    the pair is self-referencing exactly as an invoice entry's lines point at
    the invoice.
    """
    from core.dbfields import uuid7

    return uuid7()


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-003")
def delete_manual_je(actor: Any, *, entry_id: Any) -> dict[str, Any]:
    """S57/S56's *Delete draft* — TC-6, *"gone without trace in the books"*.

    The audit row remains, which is TC-6's other half: a draft that existed and
    was abandoned is a fact somebody may need, even though the books never moved.
    """
    posting.delete_draft(entry_id, actor=actor)
    return {"entry_id": str(entry_id), "deleted": True, "unavailable": (ROLE_GATE_IS_A_READING,)}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-003")
def post_manual_je(
    actor: Any,
    *,
    entry_id: Any,
    posted_at: datetime,
) -> ManualPostResult:
    """S57's *Post entry ✓* — TC-2, and the three things it refuses.

    BR-LED-003 makes three demands at post and all three are enforced HERE, on
    the server, whatever the modal did: **balanced** (the posting service asserts
    it against the lines that exist, and `ledger/0002`'s deferred trigger asserts
    it again at COMMIT), a **memo** (US-LED-011 TC-4: *"or with an empty memo …
    blocked"*), and the **role** (the gate above).

    The `JE-` number is allocated inside the transaction and stamped by
    `posting.post_draft` — BR-LED-021's *"stamped when the entry POSTS"*.

    `posted_at` is an INPUT (BR-TEN-043): a double-submitted form must stamp one
    moment, not two.
    """
    tenant_id = _tenant_id()
    entry = models.JournalEntry.objects.filter(tenant_id=tenant_id, pk=entry_id).first()
    if entry is None:
        raise ManualJournalError(
            f"journal entry {entry_id!r} is not one of this tenant's entries (US-LED-011 TC-7). "
            "Nothing is posted and nothing is reported about whose it is."
        )
    if entry.status == models.JE_POSTED:
        # A double-submitted Post. The first one is the answer.
        return ManualPostResult(
            entry_id=str(entry.pk),
            number=entry.number,
            posting_key=entry.posting_key or "",
            created=False,
            entry_date=entry.entry_date,
            debits=ZERO,
            credits=ZERO,
            line_count=entry.lines.count(),
            unavailable=(ROLE_GATE_IS_A_READING,),
        )
    if not str(entry.memo or "").strip():
        raise ManualJournalError(
            "posting a journal entry needs a MEMO (BR-LED-003: *balanced required at post; "
            "reason + audit*; US-LED-011 TC-4 blocks an empty one). The entry is immutable the "
            "moment it posts, so the memo is the only place the WHY can ever be written."
        )

    key = posting.posting_key(
        source_type=SOURCE_MANUAL_JE, source_id=entry.pk, event=EVENT_POSTED
    )
    # BR-TEN-038 AT POST, not only at save (DEF-3202). This function's own
    # docstring above claimed the date was resolved *"at SAVE as well as at
    # POST"* and it was resolved only at save — hard-won law 1, and
    # `ManualPostResult.date_note` existed with nothing ever writing it, which is
    # law 2. A draft can sit open for days and the month can close under it; the
    # clerk is never blocked, the entry lands in the earliest OPEN period, and
    # the note says why. The JE number comes from the RESOLVED date because
    # BR-LED-021's series is per period — numbering a September entry into
    # August's series would put a gap in one and a duplicate in the other.
    resolved, date_note = close.resolve_entry_date(entry.entry_date)
    with transaction.atomic():
        number, gap = _allocate_number(resolved)
        result = posting.post_draft(
            entry.pk,
            posted_at=posted_at,
            posting_key=key,
            number=number,
            entry_date=resolved,
            actor=actor,
            audit_context={
                "action": "manual_je_post",
                "memo": entry.memo,
                **({"auto_forwarded": date_note} if date_note else {}),
            },
        )
    reasons = [ROLE_GATE_IS_A_READING]
    if gap is not None:
        reasons.insert(0, gap)
    return ManualPostResult(
        entry_id=result.entry_id,
        number=number,
        posting_key=result.posting_key,
        created=result.created,
        entry_date=resolved,
        debits=result.debits,
        credits=result.credits,
        line_count=result.line_count,
        date_note=date_note,
        unavailable=tuple(reasons),
    )


# ═══════════════════════════════════════════════════════════════════════════
# BR-LED-798 — A BATCH POSTS IN FULL OR NOT AT ALL (`P1.22`)
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class BatchEntryProblem:
    """One entry the pre-check refused, and the reason in a sentence."""

    entry_id: str
    reason: str


@dataclass(frozen=True)
class ManualBatchPostResult:
    """A whole month-end, posted together. `results` is one row per entry."""

    results: tuple[ManualPostResult, ...]
    entry_count: int
    unavailable: tuple[dict[str, Any], ...] = ()


def precheck_manual_je_batch(entry_ids: Any) -> tuple[BatchEntryProblem, ...]:
    """BR-LED-798 (2) — EVERY entry checked BEFORE the first one is attempted.

    ⚠ **THIS FUNCTION IS THE DIFFERENCE BETWEEN THE OPTION THE PO CHOSE AND THE
    ONE THEY DID NOT.** Option (a) and option (c) both leave the books untouched
    on a failure; (c) was chosen for exactly one reason, in the PO's own words:
    *"Priya is told about the missing memo before anything is attempted, so the
    common case never gets this far"*. A batch path that posts, fails and rolls
    back has implemented (a) and would pass every all-or-nothing case. So the
    pre-check is a separate, named function, and it is asserted separately.

    **IT REPORTS EVERY PROBLEM, NOT THE FIRST.** *"refused in ONE answer"* — a
    batch refused once per fault is a person fixing one thing, resubmitting, and
    being refused again.

    **WHAT IS CHECKED**, from `BR-LED-003` and the rule's own list (balance,
    memo, period, account state):

      * the entry EXISTS and is this tenant's — hard rule 1, and a batch takes a
        LIST of ids, which is a wider door than one id in a path;
      * it is a DRAFT. An already-POSTED entry is not a problem: it is the
        idempotent re-submit of a batch whose first attempt landed, and
        `post_manual_je` already answers it with the first result (hard rule 6);
      * it BALANCES. `BR-LED-003` requires it at post and `ledger/0002`'s
        deferred trigger asserts it again at COMMIT, so an unbalanced entry in a
        batch would abort the whole transaction at the very last moment — which
        is the rule working, at the worst possible moment to learn;
      * it has a MEMO. The entry is immutable the moment it posts, so the memo
        is the only place the WHY can ever be written. **This is the PO's own
        worked case: entry 3 of 5, $506.25, no memo.**

    ⚠ **THE PERIOD IS NOT CHECKED HERE AND THAT IS NOT AN OMISSION.**
    `BR-TEN-038` AUTO-FORWARDS a date in a closed period rather than refusing
    it, so there is nothing for a pre-check to refuse — `post_manual_je`
    resolves the date and reports the forward in `date_note`.

    ⚠ **AND ACCOUNT STATE IS CHECKED BY THE POSTING SERVICE, NOT HERE.** A GL
    account switched off BETWEEN this check and the post is the case the rule
    records as **UNSPECIFIED** — *"naming which entry and why in that rarer case
    is a screen question nobody has put"*. The transaction rolls the batch back,
    which is the ruling applied; what the officer is TOLD is not invented here.
    """
    tenant_id = _tenant_id()
    wanted = [str(one) for one in (entry_ids or ())]
    found = {
        str(row.pk): row
        for row in models.JournalEntry.objects.filter(tenant_id=tenant_id, pk__in=wanted)
    }
    # One query for every line in the batch, rather than one per entry.
    sums: dict[str, dict[str, Decimal]] = {}
    for entry_id, side, amount in models.JournalLine.objects.filter(
        tenant_id=tenant_id, journal_entry_id__in=list(found)
    ).values_list("journal_entry_id", "side", "amount"):
        bucket = sums.setdefault(
            str(entry_id), {models.SIDE_DEBIT: ZERO, models.SIDE_CREDIT: ZERO}
        )
        bucket[side] += amount

    problems: list[BatchEntryProblem] = []
    for entry_id in wanted:
        entry = found.get(entry_id)
        if entry is None:
            # US-LED-011 TC-7's posture: nothing is reported about whose it is.
            problems.append(
                BatchEntryProblem(
                    entry_id,
                    "is not one of this tenant's journal entries, so the batch was "
                    "not attempted",
                )
            )
            continue
        if entry.status == models.JE_POSTED:
            continue  # the idempotent re-submit; `post_manual_je` answers it
        bucket = sums.get(entry_id, {models.SIDE_DEBIT: ZERO, models.SIDE_CREDIT: ZERO})
        if not bucket[models.SIDE_DEBIT] and not bucket[models.SIDE_CREDIT]:
            problems.append(BatchEntryProblem(entry_id, "has no GL lines"))
            continue
        if bucket[models.SIDE_DEBIT] != bucket[models.SIDE_CREDIT]:
            problems.append(
                BatchEntryProblem(
                    entry_id,
                    "does not balance: debits "
                    f"{bucket[models.SIDE_DEBIT]} against credits "
                    f"{bucket[models.SIDE_CREDIT]} "
                    "(BR-LED-003 requires balance at post)",
                )
            )
        if not str(entry.memo or "").strip():
            problems.append(
                BatchEntryProblem(
                    entry_id,
                    "has no memo. A posted entry is immutable, so the memo is the only "
                    "place the reason can ever be written (BR-LED-003)",
                )
            )
    return tuple(problems)


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-798")
def post_manual_je_batch(
    actor: Any,
    *,
    entry_ids: Any,
    posted_at: datetime,
) -> ManualBatchPostResult:
    """BR-LED-798 — the whole batch posts inside ONE transaction, or none of it.

    **PO ruling 2026-09-24**, option (c) of three, closing `OQ-LED-12630`,
    verbatim: *"c  All-or-nothing, and the screen checks every entry before it
    starts  Same as (a), but Priya is told about the missing memo before
    anything is attempted, so the common case never gets this far"*.

    **WORKED, AS SHOWN TO THE PO:** five month-end entries totalling
    **$2,142.75** — depreciation $812.00 · prepaid insurance released $415.50 ·
    accrued utilities $506.25 · payroll accrual $268.00 · bank charges $141.00 —
    the third with no memo. **Nothing posts.** The rejected alternative would
    have put **$1,227.50** irreversibly into September, removable only by two
    further reversing entries standing beside it for ever.

    ⚠ **THIS IS A BATCH ENDPOINT AND NOT A LOOP IN THE CLIENT, AND DECIDING
    THAT WAS THE WHOLE REASON `P1.22` WAS BLOCKED ON A QUESTION.**
    `post_manual_je` posts exactly ONE entry and `ManualPostResult` carries one
    `entry_id` and one `number`, so five entries is five calls — and five calls
    from a browser cannot be one transaction. **A screen that simply looped
    would have shipped the REJECTED option by accident**, which is why the
    register row said *"doing nothing is choosing (b)"* and why it is now wrong.

    ⚠ **HARD RULE 4 IS UNTOUCHED.** Nothing posted is ever unwound, because on a
    failure nothing was posted. `BR-LED-003`'s immutability is what makes
    all-or-nothing the SAFER half rather than the tidier one: under the rejected
    option, entries 1 and 2 could only be removed by two further reversing
    entries beside them for ever.

    ⚠ **HARD RULE 6 IS UNTOUCHED.** Each entry keeps its own `posting_key`
    (`journal_entry|<id>|posted`), so retrying the whole batch is idempotent and
    a partially-attempted batch cannot double-post on the retry.

    ⚠ **AND ON POSTGRESQL THE ROLLBACK IS THE DATABASE'S, NOT OURS (hard-won law
    14).** A failed statement aborts the whole transaction, so `atomic()` here
    is the mechanism rather than a courtesy. **The default suite is SQLite,
    which has no aborted-transaction state and therefore cannot prove any of
    this** — `tests/test_br_led_798_batch_posts_in_full_or_not_at_all.py` says
    so in its own docstring and names the settings module to run it under.
    **There is no `except … continue` anywhere in this function and there must
    never be**: a SAVEPOINT that let entry 4 proceed past entry 3 would be
    option (b) reintroduced one layer down.
    """
    wanted = [str(one) for one in (entry_ids or ())]
    if not wanted:
        raise ManualJournalError(
            "a batch needs at least one entry. An empty batch that answered success "
            "would tell a finance officer their month-end had posted."
        )
    problems = precheck_manual_je_batch(wanted)
    if problems:
        raise ManualJournalError(
            "the batch was NOT attempted, and nothing is in the books (BR-LED-798). "
            + "; ".join(f"entry {row.entry_id} {row.reason}" for row in problems)
        )
    results: list[ManualPostResult] = []
    with transaction.atomic():
        for entry_id in wanted:
            results.append(post_manual_je(actor, entry_id=entry_id, posted_at=posted_at))
    return ManualBatchPostResult(
        results=tuple(results),
        entry_count=len(results),
        unavailable=(ROLE_GATE_IS_A_READING,),
    )


# ═══════════════════════════════════════════════════════════════════════════
# US-LED-012 — the accrual auto-reversal (BR-LED-005)
# ═══════════════════════════════════════════════════════════════════════════
def accrual_reversal_due_on(entry_date: date) -> date:
    """*"day 1 of the next period"* (BR-LED-005), per the tenant's fiscal settings.

    Not *"the first of the next calendar month"*: BR-TEN-022 computes the period
    from the tenant's fiscal year and cadence, and a tenant on QUARTERLY close
    accrues into a quarter. `close.period_window` is the one implementation of
    that calendar; deriving it again here would be a second one.

    LE-4 on a monthly tenant: an accrual dated **Sep 30** sits in the September
    period, whose next period starts **Oct 1** — which is the date the workbook
    names.
    """
    window = close.period_window(entry_date)
    return window[1] + timedelta(days=1)


def pending_accrual_reversals(*, as_of: date) -> tuple[models.JournalEntry, ...]:
    """Every posted accrual whose day-1 mirror is due by `as_of` and missing.

    The same question `close._accruals_item` asks, so the checklist and the sweep
    can never disagree about whether October is safe to bill.
    """
    tenant_id = _tenant_id()
    candidates = models.JournalEntry.objects.filter(
        tenant_id=tenant_id,
        type=models.JE_ACCRUAL,
        status=models.JE_POSTED,
        auto_reverse_entry__isnull=True,
        entry_date__lte=as_of,
    ).order_by("entry_date", "created_at")
    return tuple(
        entry for entry in candidates if accrual_reversal_due_on(entry.entry_date) <= as_of
    )


def run_accrual_auto_reversals(
    *,
    as_of: date,
    posted_at: datetime,
    actor: Any = None,
) -> tuple[AutoReversalResult, ...]:
    """BR-LED-005's schedule, as an idempotent sweep. LE-4, end to end.

    For each accrual whose day-1 mirror is due and missing, the mirror is posted
    by `apps.ledger.posting.reverse_entry` with `link_forward=True`, so:

      * the MIRROR carries `reversal_of` → the accrual (r13 #2), and
      * the ACCRUAL carries `auto_reverse_entry` → the mirror,

    which is BR-LED-005's *"linked both ways"* and US-LED-012 TC-3's Links
    column. It is audited as `journal.auto_reversed`, not `journal.reversed`
    (TC-1's own code).

    **NO ACTOR, and that is deliberate.** This is a system job: `actor=None`
    makes `core.audit` stamp the job name rather than a user id (BR-AUD-003),
    because nobody clicked anything — the rule fired. It carries no
    `@require_role` for the same reason; there is no request and no role, and a
    gate on a scheduled sweep would be a gate on the rule itself.

    **`as_of` and `posted_at` are both INPUTS** (BR-TEN-043 / gate G6): a sweep
    that read the clock could not be re-run over yesterday, and a catch-up run is
    the normal case after a host was down.

    **THE MIRROR'S DATE GOES THROUGH THE CLOSE** — US-LED-012 TC-6: if day 1 of
    the next period is itself inside a locked period (the reopened-then-closed
    edge), BR-TEN-038 forwards it and the note rides into the audit row. The
    mirror never lands in a closed month.

    Returns one row per accrual it considered, including the ones it SKIPPED —
    an accrual a human already reversed by hand cannot take a second mirror
    (`uq_journal_entries_reversal`), and reporting that is more useful than
    silently doing nothing.
    """
    if not isinstance(as_of, date) or isinstance(as_of, datetime):
        raise ManualJournalError(
            "as_of must be a date supplied by the caller (BR-TEN-043 — nothing in a money path "
            "reads a clock, gate G6). A sweep that read 'today' could never be re-run over a "
            "day it missed."
        )
    if not isinstance(posted_at, datetime):
        raise ManualJournalError("posted_at must be a datetime supplied by the caller.")

    results: list[AutoReversalResult] = []
    for accrual in pending_accrual_reversals(as_of=as_of):
        due_on = accrual_reversal_due_on(accrual.entry_date)
        key = posting.posting_key(
            source_type="journal_entry", source_id=accrual.pk, event=EVENT_AUTO_REVERSED
        )
        amount = sum(
            (
                line_amount
                for side, line_amount in accrual.lines.values_list("side", "amount")
                if side == models.SIDE_DEBIT
            ),
            ZERO,
        )
        existing_mirror = accrual.reversed_by.first()
        if existing_mirror is not None:
            results.append(
                AutoReversalResult(
                    accrual_entry_id=str(accrual.pk),
                    mirror_entry_id=str(existing_mirror.pk),
                    posting_key=key,
                    created=False,
                    due_on=due_on,
                    entry_date=existing_mirror.entry_date,
                    amount=amount,
                    skipped="already_reversed_by_hand",
                )
            )
            continue
        entry_date, note = close.resolve_entry_date(due_on)
        result = posting.reverse_entry(
            accrual.pk,
            posting_key=key,
            entry_date=entry_date,
            posted_at=posted_at,
            memo=f"Auto-reversal of accrual {accrual.number or accrual.pk} (BR-LED-005)",
            actor=actor,
            audit_context={
                "action": "accrual_auto_reverse",
                "accrual_entry_date": accrual.entry_date.isoformat(),
                "due_on": due_on.isoformat(),
                **({"auto_forwarded": note} if note else {}),
            },
            audit_action=posting.AUDIT_AUTO_REVERSED,
            link_forward=True,
        )
        results.append(
            AutoReversalResult(
                accrual_entry_id=str(accrual.pk),
                mirror_entry_id=result.entry_id,
                posting_key=result.posting_key,
                created=result.created,
                due_on=due_on,
                entry_date=entry_date,
                amount=result.debits,
                date_note=note,
            )
        )
    return tuple(results)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-011@bdd33ae (sha1[:7], newline-joined in order; US-LED-012 ships here too — the authorities this module implements, in order: 04-docs/05-modules/09-ledger/06-epics/EP-LED-04-manual-je.md US-LED-011 §1-§8 + US-LED-012 §1-§8 · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-003/005/015/021/025 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-4 + LE-8 · 04-docs/05-modules/09-ledger/04-flows.md §2 · 12-governance/02-decision-log.md 2026-08-12 "Approve a JE- series" (OQ-176) and "System Admin, Billing Clerk" (OQ-175))
# generated: 2026-08-15 by the ledger close-the-books lane
# checklist: A✔ B✔ C✔ D=deferred(the S57 endpoints are the API half — not built by this lane) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row owed and G7 glob REPORTED)
# gates: see 06-backend/tests/test_us_led_011_manual_je.py and
#         test_us_led_012_accrual_auto_reverse.py — the unbalanced post, the
#         empty memo, the posted-entry edit, the executive role and the
#         double-mirror were each proved RED before they were trusted green
# exceptions: THE `JE-` NUMBER IS ALLOCATED AND NO TENANT CAN ANSWER —
#         `apps.tenancy.services.SERIES_DEFAULTS` has no journal entry and
#         apps/tenancy/** is another lane's in this session, so the one-line seed
#         is REPORTED and every unnumbered post says so by name · BR-LED-021's
#         *"gapless"* clause is NOT implemented: this allocates through
#         BR-TEN-035's monotonic counter, where *"gaps ok, never reused"*, and
#         the two statements are flagged on the rule rather than reconciled here ·
#         BR-LED-021's justification *"exactly as a draft bill does under
#         BR-BIL-063"* is BACKWARDS (a draft BILL takes its number at creation);
#         the RULING is built as given — number at POST — and the contradiction is
#         flagged, not resolved · the role gate is a READING of OQ-175, which
#         ruled on REVERSAL; carried on every result as
#         `manual_je_role_gate_is_a_reading_not_a_ruling` · MANUAL LINES CARRY NO
#         service/premises/account DIMENSIONS: US-LED-011 §5 maps four fields and
#         none of them is a dimension, and a reclass between two GL accounts has
#         no invoice to inherit one from. `source_type`/`source_id` ARE carried,
#         which is what BR-LED-001 requires unconditionally · the S57 modal, its
#         *Must balance* footer and IS-6's confirm are the FRONTEND half and are
#         not built here; `gap` is the figure that footer renders
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

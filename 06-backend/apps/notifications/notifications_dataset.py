# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · **THE TENTH DATASET** — `notifications`, which `R8
#           Bill Delivery` is drawn from and the registry does not hold
#           (`P6.10`, and `DEF-REP-6797` from the other direction: the brief
#           says *nine datasets* four times and its own §05 table lists TEN
#           owners; ten is right).
#           Drawings read as IMAGES (B14 rule 42): p051 (R7 Bill Print File and
#           R8 Bill Delivery in full), p083–p086 (§7.2/§7.2.1/§7.2.2/§7.2.4),
#           p087 (§7.5 read path + §7.6 scale), p090–p092 (§08 architecture).
# Story:    US-REP-009 (the six audit-added reports — *delivery-queue health*
#           and *returned mail* are this exact fact) · US-REP-002 (the S46
#           viewer). R8 Bill Delivery.
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — `current_tenant_id()` on
#           every queryset, RLS FORCE) · hard rule 4 (**this file writes
#           nothing at all**) · hard rule 7 (a money ACTION writes `audit_log`;
#           a READ is not an action) · **hard rule 8 — an address lives on
#           `premises` and every other entity WALKS to it; this dataset
#           declares NO address column and makes NO second copy, and the one
#           address it serves is the envelope the MESSAGE already carries** ·
#           NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
#           BR-BIL-016 (one delivery row per document per CHANNEL) ·
#           BR-BIL-036 (an account with NO email address is normal, not an
#           exception) · BR-NOT-005 (the status lifecycle is forward-only) ·
#           BR-NOT-013 (`delivered` and `bounced` are PROVIDER facts) ·
#           BR-PAY-018 (paper held on a bad address is written, marked held,
#           never dispatched, never lost) · BR-TEN-017 (an issued document is
#           never re-rendered; the envelope is pinned) · BR-REP-024 (never a 0
#           where a figure could not be computed) · BR-TEN-043 (the business
#           date is an argument, never a clock)
# Tests:    06-backend/tests/test_rep_notifications_dataset.py
#           10-scripts/ds_accounts_audit_notifications_cost.py (the PostgreSQL
#           measurement — hard-won law 14: the suite runs on in-memory SQLite)
#           10-scripts/rep_ds_accounts_rls_proof.py (tenant isolation, two tenants)
# Impacts:  apps/reports/datasets.py — **a tenth `Dataset` must be REGISTERED**
#           and `R8`'s seeded `dataset` column moved from `audit_log` to
#           `notifications`. REP-UNBLOCK owns `queries.py`/`datasets.py` this
#           session; this lane BUILDS and REPORTS and registers nothing.
# ───────────────────────────────────────────────────────
"""THE `notifications` DATASET — **one row per OUTBOUND MESSAGE**, paged in SQL.

🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — it is what a utility's *did the bill go out?* answer
is made of. Row in `12-governance/09-human-review-ledger.md`, before the review.

═══════════════════════════════════════════════════════════════════════════════
⚠ WHY THERE IS A TENTH DATASET AT ALL, AND WHY `R8` WAS NOT FORCED ONTO
  `audit_log`
═══════════════════════════════════════════════════════════════════════════════
`reports/migrations/0003_seed_catalogue.py` seeds `R8 bill_delivery` with
`dataset="audit_log"`. **Its drawing's own eyebrow reads `Billing › Delivery ·
notifications · —`** (p051, read as an image), and every one of its seven
columns is a column of `outbound_messages`:

| R8 draws | `outbound_messages` holds |
|---|---|
| ACCOUNT | `account_id` → customers' `account_no` (B14 rule 31: the number, never the id) |
| CUSTOMER | the account's primary contact, through customers' batched read |
| CHANNEL | `channel` |
| ADDRESS | `recipient_address` — the envelope pinned at queue time |
| SENT | `sent_at` |
| STATUS | `status` |
| REASON | `last_error` · `unavailable_reason` · `held_reason` |

and its tiles — `SENT 1,198 · DELIVERED 1,144 (95%) · BOUNCED 38 · RETURNED
POST 16` — are counts of MESSAGES.

**`audit_log` could not have served one of them.** No audit row is written when
a provider bounces an email: a bounce is a provider's answer ABOUT a message,
not an act anybody performed, and `BR-NOT-013` says so in as many words —
*"`delivered` and `bounced` can never be written by anything in this repo"*,
both are provider facts. Forcing R8 onto the trail would have rendered **an
audit register under the title *Bill Delivery*** — real rows, a footing total
and an answer to a question nobody asked.

So the choice put and taken: **build the tenth dataset's QUERY.** Registration
is `apps/reports/datasets.py` and `R8`'s seeded `dataset` column, both of which
belong to REP-UNBLOCK this session; what needs doing is REPORTED with this file
rather than done in it, because a sibling has already found that adding a key to
`VIEWERS` can override a live screen through the dict merge in `api._VIEWERS`.

═══════════════════════════════════════════════════════════════════════════════
⚠ THE GRAIN IS ONE MESSAGE, AND THE ALTERNATIVE DROPS EVERY SECOND CHANNEL
═══════════════════════════════════════════════════════════════════════════════
`BR-BIL-016` and the table's own unique key make one row per (source_type,
source_id, **channel**, copy_no). A bill emailed AND posted is TWO rows, and
that is the point: R8's `SENT` tile counts DELIVERY ATTEMPTS, not bills.

A grain of *one bill* would count that bill once and lose whichever channel
sorted second — and a smaller number of sent letters does not read as wrong, it
reads as a quieter month. That is the same shape as the `payments` lane's
allocation grain dropping every deposit (`DEF-REP-6853`), met here before it
shipped rather than after.

═══════════════════════════════════════════════════════════════════════════════
⚠ THE STATUS BUCKETS ARE DERIVED FROM `models.STATUSES` AND THE FILE REFUSES TO
  IMPORT IF ONE IS UNCOUNTED — THIS IS PHASE 5'S LESSON, BUILT
═══════════════════════════════════════════════════════════════════════════════
Phase 5's own finding: *five of its six defects were code that was correct while
every row was ours, and wrong the first day a utility wrote one.* The delivery
statuses are exactly that shape. `models.STATUSES` has **nine** values today; it
had **five** before `DEF-NOT-5626` split a bounce into hard and soft and added
`complained` and `unsubscribed` on 2026-09-17, and `models.py` says in its own
comment that *three hand-maintained copies of this tuple is how a new status
becomes invisible on the one screen that exists to show it.*

A tile written as `status="bounced"` counts **zero** on this deployment —
because `bounced` is LEGACY and nothing in this repo has ever written it — while
38 hard and soft bounces sit uncounted. It does not error and it does not look
wrong.

So `_BUCKETS` below is a partition of `models.STATUSES`, and
`_assert_every_status_is_bucketed()` runs at IMPORT and raises naming any value
it does not cover. **A tenth status cannot be added to this platform without
this module going red and naming it.** That is a guard proved RED first (see the
test), and it is the one shape law 7 says has no other cure.

⚠ **TWO FACTS ARE ORTHOGONAL TO STATUS AND BOTH MATTER TO THIS REPORT, WHICH IS
WHY THEY ARE COLUMNS AND NOT BUCKETS.** `models.py` says why in each case:

* **`returned_at` — RETURNED POST.** *"NOT a status either — a returned letter
  was genuinely SENT, and rewriting its status would destroy the fact that it
  left the building (BR-NOT-005 forward-only)."* So the RETURNED POST tile is
  `returned_at IS NOT NULL`, and those rows are ALSO in the sent count. They
  are not double-counted into the failure buckets.
* **`held` — BR-PAY-018.** A paper letter to a bad address is *"written, marked
  held, never dispatched, never lost"*. **A held row has never been sent and
  must not enter the SENT denominator**, or the delivered percentage is struck
  against letters that are still in the building. `held` is counted and
  published separately, which is also the dispatcher's own
  `held_marker_not_implemented` problem finally having a report.

═══════════════════════════════════════════════════════════════════════════════
HARD RULE 8 — AND WHY SERVING `recipient_address` IS OBEYING IT, NOT BENDING IT
═══════════════════════════════════════════════════════════════════════════════
R8's drawn warning, verbatim from the image: *"The address column walks to
`premises` — an address is stored in one place and every other entity derives
it. Nothing here holds its own copy."*

**This dataset declares no address column and composes no address.** What it
serves is `outbound_messages.recipient_address` — *"the address as it stood when
the row was written"* — and that value ALREADY CAME FROM `premises`: for a
postal row it is written by `customers.selectors.delivery_recipients_for_account`
through metering's `envelope_addresses`, which is the walk `DEF-PAY-6342` was
filed to make real after six weeks in which the docstring claimed it and the
code could not do it.

⚠ **AND FOR A DELIVERY REPORT THE PINNED VALUE IS THE ONLY CORRECT ONE.**
`BR-TEN-017` pins the envelope because an issued document is never re-rendered.
Walking to `premises` AT READ TIME would show where the letter WOULD go now —
so a letter returned *No such address*, whose address has since been corrected,
would render against the CORRECTED address and read as a live fault at a good
address. The report is about what happened; the address that happened is the one
on the envelope.

⚠ **AN EMAIL ADDRESS AND A PHONE NUMBER ARE NOT ADDRESSES IN HARD RULE 8's
SENSE AT ALL**, and two of R8's three drawn rows are email. Rule 8 governs where
a PROPERTY is; `m.ruiz@…` is a contact point on a customer.

═══════════════════════════════════════════════════════════════════════════════
IT PAGES AND SORTS IN SQL, AND THE EXPORT IS A SEPARATE FUNCTION
═══════════════════════════════════════════════════════════════════════════════
Brief §7.5 (p087). `per` cuts the page with `[offset:offset+limit]` on a
QuerySet — one `LIMIT/OFFSET` — and `sort` is `order_by(*order_terms(...))`.
**Nothing is sorted or sliced in Python anywhere in this file.**

⚠ **`notifications_dataset_stream()` TAKES NO `page` AND NO `per`.** An export
cannot inherit a screen's fifty rows because there is no argument to pass them
through. `NFR-5` forbids a ceiling and there is none.

**`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET, NEVER OVER THE
PAGE**, so R8's four tiles foot to the report whether a page is cut or not.

═══════════════════════════════════════════════════════════════════════════════
ADDITIVITY (§7.2.2, read as an image on p085)
═══════════════════════════════════════════════════════════════════════════════
* `sent`, `delivered`, `bounced`, `returned`, `failed`, `held`, `queued` — all
  **FULLY ADDITIVE.** Each is a count of events that happened once, at one
  moment, so they sum freely in every direction including across time. September
  plus October really is the two months' post.
* `delivered_pct` — **NON-ADDITIVE.** §7.2.2's own row: *"must be recomputed
  from its components, never averaged."* Two months' delivery rates do not
  average to the two-month rate unless the volumes match. It is recomputed here
  on every call and is `None` — never `0` — when nothing was dispatched, because
  a rate over no letters is not a number (BR-REP-024).

**This dataset carries no money column at all**, so hard rule 2 has nothing to
bite on here and no money basis is declared. That is why R8's eyebrow ends in an
em-dash rather than a date basis, and `BASIS` says so rather than borrowing one.

═══════════════════════════════════════════════════════════════════════════════
WHAT IT WILL NOT DO
═══════════════════════════════════════════════════════════════════════════════
**It writes nothing.** No INSERT, UPDATE, DELETE or `save()` below, and nothing
re-queues, releases or resends — those are `delivery_ops`' and they stay there.

**It never falls back to zero.** BR-REP-024: a rate over no dispatched messages
is `None` beside a named reason, not `0%`.

**It states no clock.** `start`/`end` are arguments (BR-TEN-043).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q

from apps.notifications import customers_seam, models
from core.pagination import order_terms
from core.tenancy import current_tenant_id

#: BR-REP-001 — and the honest answer is that this report has NO money basis.
#: R8's eyebrow ends `notifications · —`, an em-dash, because there is no money
#: on this grain to date. `sent_at` is the report's time axis and it is a fact
#: about the message, not a money basis; borrowing `posting` or `clearing` here
#: would attach a money vocabulary to a report that has no money in it.
BASIS = "none"

#: The time axis. `sent_at` is NULL until the dispatcher moves the row, so a
#: window on it excludes queued and held rows BY CONSTRUCTION — which is
#: correct (they have not been sent) and is also invisible, so both counts are
#: published in `totals` rather than left for a clerk to wonder about.
TIME_COLUMN = "sent_at"


# ═══════════════════════════════════════════════════════════════════════════
#  THE BUCKETS — A PARTITION OF `models.STATUSES`, CHECKED AT IMPORT
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **PHASE 5's LESSON, BUILT RATHER THAN REMEMBERED.** Every one of these
# tuples is derived from the module's own constants; none spells a status
# literal. `_assert_every_status_is_bucketed()` below raises at IMPORT naming
# any value of `models.STATUSES` that no bucket covers, so a tenth status
# cannot arrive on this platform and be silently uncounted on the one report
# that exists to count it.

#: Never left the building. `queued` is the only one — `held` is orthogonal to
#: status (a flag, not a sixth state) and is counted from its own column.
NOT_YET_DISPATCHED: tuple[str, ...] = (models.STATUS_QUEUED,)

#: The provider said it arrived.
DELIVERED_STATUSES: tuple[str, ...] = (models.STATUS_DELIVERED,)

#: The provider said it did not, because of the ADDRESS. All three spellings:
#: `bounced` is LEGACY and deliberately still lawful (`DEF-NOT-5626` — nothing
#: in this repo has ever written it and no row was rewritten to one of the two
#: below, so a row reading `bounced` states *the provider bounced this and we do
#: not know which kind*). Counting only `bounced` would report 0 on this
#: deployment; counting only the two new ones would silently drop any legacy or
#: imported row.
BOUNCED_STATUSES: tuple[str, ...] = (
    models.STATUS_BOUNCED,
    models.STATUS_BOUNCED_HARD,
    models.STATUS_BOUNCED_SOFT,
)

#: We could not send it — our side, or the provider refused outright.
FAILED_STATUSES: tuple[str, ...] = (models.STATUS_FAILED,)

#: The consumer marked it as spam. It LEFT the building and it suppresses, but
#: nothing is wrong with the address, which is why it is its own word and its
#: own count rather than folded into bounces.
COMPLAINED_STATUSES: tuple[str, ...] = (models.STATUS_COMPLAINED,)

#: The consumer used the unsubscribe link. ⚠ **THE ONE OUTCOME OF THE SIX THAT
#: IS NOT A FAILURE OF ANY KIND** — `models.py` says so — so it is counted, it
#: is in the dispatched denominator, and it is NEVER added to `bounced`. A
#: delivery report that files a person's choice under failures invites somebody
#: to re-subscribe them.
UNSUBSCRIBED_STATUSES: tuple[str, ...] = (models.STATUS_UNSUBSCRIBED,)

#: Left the building, nothing further known yet.
SENT_STATUSES: tuple[str, ...] = (models.STATUS_SENT,)

#: Everything that LEFT THE BUILDING — R8's `SENT` tile and the denominator of
#: `delivered_pct`. Held and queued rows are deliberately outside it.
DISPATCHED_STATUSES: tuple[str, ...] = (
    SENT_STATUSES
    + DELIVERED_STATUSES
    + BOUNCED_STATUSES
    + FAILED_STATUSES
    + COMPLAINED_STATUSES
    + UNSUBSCRIBED_STATUSES
)

_BUCKETS: dict[str, tuple[str, ...]] = {
    "queued": NOT_YET_DISPATCHED,
    "sent_only": SENT_STATUSES,
    "delivered": DELIVERED_STATUSES,
    "bounced": BOUNCED_STATUSES,
    "failed": FAILED_STATUSES,
    "complained": COMPLAINED_STATUSES,
    "unsubscribed": UNSUBSCRIBED_STATUSES,
}


def _assert_every_status_is_bucketed() -> None:
    """Refuse at IMPORT if `models.STATUSES` holds a value no bucket covers.

    ⚠ **THIS IS THE GUARD, AND IT IS DELIBERATELY AT IMPORT RATHER THAN IN A
    TEST.** A test can be skipped, deselected or simply not run by the lane that
    adds the tenth status; an import-time refusal cannot. Django loads this
    module the moment anything asks for the report, so the failure arrives at
    the first person to touch it and it NAMES the value.

    It also refuses a value counted TWICE, which is the mirror defect: a status
    in both `bounced` and `failed` makes the tiles add to more than the sent
    count and the report stops footing.
    """
    covered: list[str] = []
    for bucket in _BUCKETS.values():
        covered.extend(bucket)
    duplicated = sorted({value for value in covered if covered.count(value) > 1})
    if duplicated:
        raise RuntimeError(
            "apps.notifications.notifications_dataset: these delivery statuses are counted in "
            f"more than one bucket, so R8's tiles cannot foot: {', '.join(duplicated)}"
        )
    uncounted = sorted(set(models.STATUSES) - set(covered))
    if uncounted:
        raise RuntimeError(
            "apps.notifications.notifications_dataset: these delivery statuses are in "
            f"models.STATUSES and in no bucket here, so R8 Bill Delivery would not count them: "
            f"{', '.join(uncounted)}. Add each to the bucket it belongs in — do NOT widen an "
            "existing tuple without deciding which tile it lands on."
        )


_assert_every_status_is_bucketed()


#: What a caller may order by. Five, because five are what R8's drawing puts a
#: column on. ⚠ **EVERY TUPLE ENDS IN A UNIQUE COLUMN** — without a total order
#: two equal rows swap between pages and a clerk sees one letter twice and
#: another never. `order_terms` refuses to add a tiebreak silently.
DELIVERY_SORTS: tuple[str, ...] = ("sent_on", "account_no", "channel", "status", "queued_on")
DELIVERY_DEFAULT_SORT = "sent_on"
DELIVERY_DEFAULT_DIRECTION = "desc"
DELIVERY_SORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "sent_on": ("sent_at", "id"),
    # ⚠ Sorted by the ACCOUNT ID and LABELLED with the number. The number lives
    # in customers and a cross-module ORDER BY would be a join across a module
    # boundary; the ID is stable, unique and in this table. A caller wanting a
    # number order sorts the exported file.
    "account_no": ("account_id", "sent_at", "id"),
    "channel": ("channel", "sent_at", "id"),
    "status": ("status", "sent_at", "id"),
    "queued_on": ("created_at", "id"),
}

#: The filters this query HONOURS — R8's drawn three plus the two a delivery
#: investigation always needs next.
DELIVERY_FILTERS: tuple[str, ...] = ("from", "to", "channel", "status", "source_type", "account")


# ── BR-REP-024: named gaps, never a silent zero and never a plausible number ──

GAP_PROVIDER_OUTCOMES_NEED_AN_ADAPTER = {
    "code": "delivered_and_bounced_are_provider_facts_and_no_adapter_is_wired",
    "br_ref": "BR-NOT-013 · DEF-NOT-5626 · US-NOT-002",
    "detail": (
        "R8's DELIVERED and BOUNCED tiles count what an email provider reported. BR-NOT-013 "
        "states that `delivered` and `bounced` can never be written by anything in this repo — "
        "both are provider facts — and no provider adapter is wired on this deployment. So on a "
        "tenant with no adapter those two tiles are STRUCTURALLY zero: the figures are real "
        "counts of real rows and the rows do not exist yet. The count is published as measured "
        "with this reason beside it, so a 0% delivery rate reads as `nothing has reported back` "
        "rather than as `nothing arrived`."
    ),
    "wanted_reads": ("apps.notifications.provider_seam (the adapter, when one is configured)",),
}

GAP_HELD_HAS_NOT_BEEN_SENT = {
    "code": "a_held_paper_row_is_written_and_never_dispatched",
    "br_ref": "BR-PAY-018 · BR-NOT-005",
    "detail": (
        "Some rows in this window carry held=True: paper to an account flagged bad-address, "
        "written, marked held, never dispatched, never lost. They are NOT in the sent count and "
        "NOT in the delivered denominator — striking a delivery rate against letters still in "
        "the building would flatter it. They are counted separately so the absence is stated "
        "rather than invisible."
    ),
    "wanted_reads": (),
}

GAP_ADDRESS_IS_THE_PINNED_ENVELOPE = {
    "code": "the_address_served_is_the_one_the_message_carried",
    "br_ref": "CLAUDE.md hard rule 8 · BR-TEN-017 · DEF-PAY-6342",
    "detail": (
        "This dataset declares no address column and composes no address. It serves "
        "outbound_messages.recipient_address — the envelope as it stood when the row was "
        "written, which for a postal row was walked from premises at queue time. Walking to "
        "premises at READ time would show where the letter would go NOW, so a letter returned "
        "'No such address' whose address has since been corrected would render against the "
        "corrected address and read as a live fault at a good address."
    ),
    "wanted_reads": (),
}


@dataclass(frozen=True)
class DeliveryFactRow:
    """One outbound message — one document, on one channel (BR-BIL-016).

    ⚠ **`account_no` IS THE NUMBER, NEVER THE ID (B14 rule 31)**, and it is
    `None` for a message addressed to nobody's account: `account_id` is
    NULLABLE by design because scheduled-report and bookkeeper rows go to staff
    and belong to no customer.

    ⚠ **`reason` IS ONE OF THREE DIFFERENT FACTS AND THEY ARE NOT MERGED.**
    `last_error` is what the provider or our dispatcher said went wrong;
    `unavailable_reason` is `BR-BIL-036`'s *there was no address to send to*,
    which is NORMAL and not an exception; `held_reason` is why a written letter
    is still in the building. Collapsing them into one string is the error
    `BR-BIL-036` exists to prevent, so the row carries which kind it is.

    ⚠ **`sent_on` IS `None` UNTIL THE DISPATCHER MOVES THE ROW**, and that
    absence is the fact — never a queue date rendered as a send date.
    """

    message_id: str
    account_id: str | None
    account_no: str | None
    customer_name: str | None
    channel: str
    source_type: str
    address: str | None
    address_absent_reason: str | None
    queued_on: datetime
    sent_on: datetime | None
    status: str
    held: bool
    held_reason: str | None
    returned_on: datetime | None
    reason: str | None
    reason_kind: str | None


def _tenant_id() -> Any:
    return current_tenant_id()


def _base(
    *,
    start: date | None,
    end: date | None,
    channel: str | None,
    status: str | None,
    source_type: str | None,
    account_id: Any,
) -> Any:
    """The filtered set, every criterion a `WHERE` — hard rule 1 first.

    ⚠ **THE TENANT FILTER IS THE FIRST CLAUSE AND IS NOT OPTIONAL.** RLS FORCE
    is on and would refuse a cross-tenant row anyway, but a queryset that relies
    on the database to be the only guard is wrong the day somebody runs it as an
    owner.

    ⚠ **THE WINDOW IS ON `sent_at`, WHICH IS NULL UNTIL DISPATCH.** So a window
    EXCLUDES queued and held rows by construction. That is correct — they have
    not been sent — and it is invisible, which is why `queued` and `held` are
    counted over the same window's QUEUE date and published beside the tiles.

    ⚠ **AND AN UNWINDOWED READ THEREFORE SERVES MORE ROWS THAN IT COUNTS AS
    SENT.** With no `start` and no `end` there is no `sent_at` predicate, so
    queued and held messages ARE in the row list while `totals["sent"]` still
    counts only what left the building. `total` above `sent` is the correct
    answer and not a discrepancy: the difference is exactly
    `queued + held`, which is published. R8's own parameter bar always carries
    From and To, so the windowed shape is the one a clerk meets.
    """
    rows = models.OutboundMessage.objects.filter(tenant_id=_tenant_id())
    if start is not None:
        rows = rows.filter(sent_at__date__gte=start)
    if end is not None:
        rows = rows.filter(sent_at__date__lte=end)
    if channel:
        rows = rows.filter(channel=str(channel))
    if status:
        rows = rows.filter(status=str(status))
    if source_type:
        rows = rows.filter(source_type=str(source_type))
    if account_id is not None:
        rows = rows.filter(account_id=account_id)
    return rows


def _pending(*, start: date | None, end: date | None, channel: str | None) -> Any:
    """The rows in this window that have NOT been sent, by their QUEUE date.

    ⚠ **A SEPARATE QUERYSET BECAUSE THEY ARE A SEPARATE QUESTION.** A held
    letter has no `sent_at`, so it can never appear in the window above, and a
    report that simply omitted it would be a check reporting zero over a scope
    it silently excludes — the shape hard-won law 7's fifth clause is about, and
    `G32`'s `0 unresolved` over 21 live refusals.
    """
    rows = models.OutboundMessage.objects.filter(
        tenant_id=_tenant_id(), sent_at__isnull=True
    )
    if start is not None:
        rows = rows.filter(created_at__date__gte=start)
    if end is not None:
        rows = rows.filter(created_at__date__lte=end)
    if channel:
        rows = rows.filter(channel=str(channel))
    return rows


def _reason_of(row: Any) -> tuple[str | None, str | None]:
    """R8's REASON column — WHICH of three different facts, kept apart.

    The order is the order a clerk needs: a row that was HELD never reached a
    provider, so its held reason is the whole story; a row with no address was
    never sendable; only then does the dispatcher's or provider's error apply.
    """
    if row.held and row.held_reason:
        return row.held_reason, "held"
    if row.unavailable_reason:
        return row.unavailable_reason, "no_address"
    if row.last_error:
        return row.last_error, "error"
    return None, None


def _shape(
    row: Any, numbers: dict[str, str | None], names: dict[str, str | None]
) -> DeliveryFactRow:
    """One stored message, in the dataset's declared column names."""
    account_id = str(row.account_id) if row.account_id else None
    reason, reason_kind = _reason_of(row)
    return DeliveryFactRow(
        message_id=str(row.id),
        account_id=account_id,
        # ⚠ The account NUMBER, never the id — B14 rule 31. `None` is an
        # account that exists and has never been numbered, and a message with
        # no account at all (a staff report) is `None` too; a renderer draws
        # both as an absence and NEVER the id.
        account_no=numbers.get(account_id or ""),
        customer_name=names.get(account_id or ""),
        channel=row.channel,
        source_type=row.source_type,
        # GAP_ADDRESS_IS_THE_PINNED_ENVELOPE — the envelope this message
        # carried, never a premises walked at read time.
        address=row.recipient_address,
        address_absent_reason=row.unavailable_reason,
        queued_on=row.created_at,
        sent_on=row.sent_at,
        status=row.status,
        held=bool(row.held),
        held_reason=row.held_reason,
        returned_on=row.returned_at,
        reason=reason,
        reason_kind=reason_kind,
    )


def _shape_all(materialised: list[Any]) -> list[DeliveryFactRow]:
    """Two bounded batched label reads, then the rows. Never one query per row."""
    account_ids = [row.account_id for row in materialised if row.account_id]
    numbers = customers_seam.account_numbers(account_ids)
    names_fn = customers_seam._resolve("customers", "primary_contact_names_for")
    names = (
        {str(key): value for key, value in names_fn(account_ids).items()}
        if names_fn is not None and account_ids
        else {}
    )
    return [_shape(row, numbers, names) for row in materialised]


def _bucket_counts(rows: Any) -> dict[str, Any]:
    """Every tile, in ONE aggregate call over the same snapshot of the same rows.

    ⚠ **ONE ROUND TRIP, NOT SEVEN.** Two aggregates could see two different
    minutes if the dispatcher moved a row between them, and *"sent and delivered
    were read a millisecond apart"* is not a defect anybody would ever diagnose
    from a report that does not foot.
    """
    return rows.aggregate(
        message_count=Count("id"),
        dispatched_count=Count("id", filter=Q(status__in=DISPATCHED_STATUSES, held=False)),
        delivered_count=Count("id", filter=Q(status__in=DELIVERED_STATUSES)),
        bounced_count=Count("id", filter=Q(status__in=BOUNCED_STATUSES)),
        failed_count=Count("id", filter=Q(status__in=FAILED_STATUSES)),
        complained_count=Count("id", filter=Q(status__in=COMPLAINED_STATUSES)),
        unsubscribed_count=Count("id", filter=Q(status__in=UNSUBSCRIBED_STATUSES)),
        # Orthogonal to status, and in the sent count: a returned letter was
        # genuinely sent (BR-NOT-005 forward-only).
        returned_count=Count("id", filter=Q(returned_at__isnull=False)),
    )


def notifications_dataset(
    *,
    start: date | None = None,
    end: date | None = None,
    channel: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
    account_id: Any = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = DELIVERY_DEFAULT_DIRECTION,
) -> dict[str, Any]:
    """THE dataset query — R8 Bill Delivery. One row per message, paged in SQL.

    `per=None` is the whole filtered set. `per` is an integer page size; the
    CALLER clamps it (`core.pagination.clamp_page_size`) and this function does
    not invent one (`NFR-5`).

    ⚠ **FOR AN EXPORT, CALL `notifications_dataset_stream()`** — it takes no
    `page` and no `per`.

    **`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET AND NEVER OVER THE
    PAGE**, so R8's four tiles foot to the report whether a page is cut or not.
    """
    rows = _base(
        start=start,
        end=end,
        channel=channel,
        status=status,
        source_type=source_type,
        account_id=account_id,
    )
    aggregated = _bucket_counts(rows)

    pending = _pending(start=start, end=end, channel=channel)
    pending_counts = pending.aggregate(
        queued_count=Count("id", filter=Q(held=False)),
        held_count=Count("id", filter=Q(held=True)),
    )

    dispatched = int(aggregated["dispatched_count"])
    delivered = int(aggregated["delivered_count"])
    # NON-ADDITIVE (§7.2.2): recomputed from its components on every call,
    # never averaged and never stored. `None` — not `0` — when nothing was
    # dispatched, because a rate over no letters is not a number (BR-REP-024).
    delivered_pct = (
        (Decimal(delivered) / Decimal(dispatched)) * Decimal(100) if dispatched else None
    )

    problems: list[dict[str, Any]] = [dict(GAP_ADDRESS_IS_THE_PINNED_ENVELOPE)]
    if delivered == 0 and dispatched:
        problems.append(dict(GAP_PROVIDER_OUTCOMES_NEED_AN_ADAPTER))
    if int(pending_counts["held_count"]):
        problems.append(dict(GAP_HELD_HAS_NOT_BEEN_SENT))

    total_rows = int(aggregated["message_count"])
    ordered = rows.order_by(
        *order_terms(sort, direction, columns=DELIVERY_SORT_COLUMNS, default=DELIVERY_DEFAULT_SORT)
    )

    served_page = max(1, int(page or 1))
    if per is None:
        window = ordered
        pages = 1
    else:
        size = max(1, int(per))
        pages = max(1, -(-total_rows // size))
        served_page = min(served_page, pages)
        offset = (served_page - 1) * size
        window = ordered[offset : offset + size]

    return {
        "basis": BASIS,
        "grain": "one outbound message",
        "rows": tuple(_shape_all(list(window))),
        "totals": {
            # Fully additive (§7.2.2) — each is a count of events that happened
            # once, at one moment.
            "sent": dispatched,
            "delivered": delivered,
            "bounced": int(aggregated["bounced_count"]),
            "returned": int(aggregated["returned_count"]),
            "failed": int(aggregated["failed_count"]),
            "complained": int(aggregated["complained_count"]),
            # ⚠ NEVER folded into `bounced`: a person exercising a choice is not
            # a failure of any kind.
            "unsubscribed": int(aggregated["unsubscribed_count"]),
            # Never dispatched — outside `sent` and outside the rate.
            "queued": int(pending_counts["queued_count"]),
            "held": int(pending_counts["held_count"]),
            # Non-additive — recomputed, never averaged.
            "delivered_pct": delivered_pct,
        },
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": total_rows,
        "problems": tuple(problems),
    }


#: How many rows one round trip of the export fetches. A BUFFER, not a cap
#: (`NFR-5`): the loop runs until the cursor is exhausted.
STREAM_CHUNK = 2_000


def notifications_dataset_stream(
    *,
    start: date | None = None,
    end: date | None = None,
    channel: str | None = None,
    status: str | None = None,
    source_type: str | None = None,
    account_id: Any = None,
    sort: str | None = None,
    direction: str = DELIVERY_DEFAULT_DIRECTION,
) -> Iterator[DeliveryFactRow]:
    """EVERY row of the filtered set, streamed — **no `page`, no `per`.**

    ⚠ **THE ABSENCE OF THOSE TWO PARAMETERS IS THE WHOLE DESIGN.** An export
    cannot inherit a screen's fifty rows because there is no argument through
    which to pass them; a flag would have had that bug, a missing parameter
    cannot.

    ⚠ **`NFR-5` — NO CAP ANYWHERE ON THIS PATH.** `STREAM_CHUNK` is a fetch
    buffer rather than a ceiling.
    """
    ordered = _base(
        start=start,
        end=end,
        channel=channel,
        status=status,
        source_type=source_type,
        account_id=account_id,
    ).order_by(
        *order_terms(sort, direction, columns=DELIVERY_SORT_COLUMNS, default=DELIVERY_DEFAULT_SORT)
    )
    buffer: list[Any] = []
    for row in ordered.iterator(chunk_size=STREAM_CHUNK):
        buffer.append(row)
        if len(buffer) >= STREAM_CHUNK:
            yield from _shape_all(buffer)
            buffer = []
    if buffer:
        yield from _shape_all(buffer)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 · P6.10, THE TENTH DATASET (05-prototype/09 Reports Build Brief.pdf p051 read as an IMAGE per B14 rule 42; §7.2/§7.2.2 p083–p086; §7.5/§7.6 p087; §08 p090–p092)
# screens: S46 (the viewer) — R8 Bill Delivery
# generated: 2026-09-27 by lane DS-ACCOUNTS
# checklist: A✔ B✔ C✔ D=deferred(registration is lane REP-UNBLOCK's this session — `apps/reports/datasets.py` and `queries.py`; this lane adds NO endpoint and says so rather than claiming one) E✔(the S46 viewer renders every dataset and needs nothing new — the frontend half is owed nothing by this file) F✔ G✔ H=deferred(HUMAN-REVIEW-PENDING — the row is in 12-governance/09-human-review-ledger.md, dated 2026-09-27, written BEFORE the review)
# gates: RED PROVED FIRST, THROUGH pytest. `_assert_every_status_is_bucketed()` is exercised DIRECTLY in both directions — a tenth status no bucket covers raises naming it, and a status counted twice raises naming it — rather than trusted because it is there. Two further mutations, two reds: `BOUNCED_STATUSES` cut to the legacy spelling alone (the fixture writes all three, so the tile is off by two) · held rows folded into the dispatched count (the delivery rate struck against letters still in the building). Restored and re-run GREEN: 51 passed. Isolation on real PostgreSQL 16: `rep_ds_accounts_rls_proof.py` — 419 own rows beside the neighbour's 0.
# exceptions: (1) this is a TENTH dataset and the registry holds nine — `apps/reports/datasets.py` needs a `NOTIFICATIONS` entry and `R8`'s seeded `dataset` column needs moving from `audit_log`; REP-UNBLOCK owns that file this session, so it is REPORTED and not done here · (2) `_assert_every_status_is_bucketed()` refuses at IMPORT rather than in a test — a test can be deselected by the lane that adds the tenth status · (3) `held` and `queued` rows are outside the SENT denominator and are counted over the QUEUE date, because `sent_at` is NULL on them · (4) the address served is the message's pinned envelope, not a premises walked at read time — hard rule 8 is satisfied at QUEUE time and BR-TEN-017 forbids re-resolving it · (5) this file writes nothing
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

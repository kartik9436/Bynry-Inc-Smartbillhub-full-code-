# ── Trace ──────────────────────────────────────────────
# Change:   CR-138-BRC07 · P4.25 — "One read for refunds AND credits".
#           Blueprint `05-prototype/06 Payments Page Blueprint.pdf` p23 and
#           screen 6·1; its outcome line: *"One list, two number series —
#           refunds' own and Credit memo #"*.
#           Screens: 6·1 Refunds (the Kind column and filter are P4.26, HELD)
# Rules:    B1 / B2 §2 (cross-module reads are service functions; payments may
#           not query `credit_notes`) · BR-BIL-074 (a credit note's amount is
#           stored NEGATIVE, by check constraint) · BR-PAY-037 (both approval
#           acts recorded distinctly) · B14 rule 31 (no database id is ever the
#           visible value of a field) · rule 32 (a stated absence) · NFR-3
#           (server pagination) · NFR-5 (no hard caps) · CLAUDE.md hard rule 1
#           (tenant scoping) · hard rule 2 (money is Decimal, never float)
# Tests:    06-backend/tests/test_cr138_p4_25_refunds_and_credits.py
# Impacts:  apps/payments/billing_seam.credit_notes_page / credit_notes_count
#           (the seam this stands on) · apps/billing/selectors.credit_note_page
#           / credit_note_count (billing's published half) ·
#           apps/payments/refunds_api.py (the route)
# ───────────────────────────────────────────────────────
"""**EVERYTHING GIVEN BACK, IN ONE LIST, WITHOUT FLATTENING TWO LIFECYCLES.**

A utility gives money back two ways and they are not the same thing:

  * a **REFUND** is payments' own row. It is **raised, approved, issued,
    cleared** — four acts by two people over days or weeks, and a cheque
    leaves the building at the third.
  * a **CREDIT NOTE** is billing's row. It is raised, numbered, posted and
    issued **in one act** (`corrections.execute_credit_only` sets `issued_at`
    in the same `create`), and then it freezes — `billing/0002`'s trigger makes
    the row immutable. **It has no state column at all**, and that is not an
    omission somebody will get round to.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE TWO LIFECYCLES ARE NOT FLATTENED, AND THE SHAPE IS HOW IT IS KEPT.  ║
╚══════════════════════════════════════════════════════════════════════════╝
`P4.26` (wave 2) states the requirement in terms: *"The columns must not
flatten the two lifecycles: a refund is raised, approved, issued, cleared; a
credit note has no state column at all."* A response that carried a `status`
member on both kinds would have to put SOMETHING in a credit note's — and every
candidate is a lie. `"issued"` invents a state machine the row is not in.
`null` reads on screen as *we do not know*, when the truth is *there is nothing
to know*. `"n/a"` is the same lie with worse manners.

**So a credit-note row has NO `status` KEY.** Not null — absent. A screen
reading `row.status` on a credit note gets `undefined`, which is the only
honest answer, and `lifecycles` on the envelope is what tells it to render a
stated absence (B14 rule 32) rather than an empty cell.

═══════════════════════════════════════════════════════════════════════════════
`amount_returned` IS A MAGNITUDE, AND SAYING SO IS THE POINT
═══════════════════════════════════════════════════════════════════════════════
`refunds.amount` is POSITIVE and `credit_notes.amount` is NEGATIVE by CHECK
constraint (`BR-BIL-074`, `<= 0`, ruled after `DEF-085` found two writers with
opposite conventions and a signed Σ reading **$272.30 on a run where the
customer owed $222.30**). One column carrying both would be that defect again,
one table over.

So the shared column is `amount_returned`: **the magnitude given back,
positive for both kinds**, taken with a single `abs()` in ONE place with its
reason written here — which is what `release.py` already does and records. The
**signed** figure is untouched and travels on `source.amount`, exactly as its
owning module publishes it. Nothing recomputes and nothing rounds: both arrive
as decimal STRINGS off a `NUMERIC(18,6)` column and leave as decimal strings
(hard rule 2 — no float touches this path).

═══════════════════════════════════════════════════════════════════════════════
⚠ ONE NUMBER SERIES EXISTS AND THE OTHER DOES NOT — REPORTED, NOT INVENTED
═══════════════════════════════════════════════════════════════════════════════
The task says *"two number series — refunds' own and Credit memo #, already one
of the thirty configured"*. **Only one of those two is true**, and it was
checked rather than assumed:

  * **`Credit memo #` IS real.** `core.numbering.CREDIT_MEMO` is seeded in every
    tenant and `corrections._allocate_credit_note_no` has written
    `credit_notes.credit_note_no` since CR-059 CS-37 (2026-09-02). Historic rows
    carry NULL and are deliberately not back-filled, because the row freezes at
    issue.
  * **REFUNDS HAD NO SERIES AND STILL HAVE NO NUMBER COLUMN.** There is no
    `REFUND` constant in `core/numbering.py`'s forty and no `refund_no` on
    `payments.models.Refund`. The only human token a refund carries today is
    `reference` — **the CHEQUE number, which is the BANK's and not ours** — and
    it is null on every ACH refund and on every refund before it is issued.
    ⚠ **RULED 2026-09-23 (`OQ-PAY-12605`): the series is `RFD-{YY}-{0000}` and
    day one is `RFD-26-0001`. The column and the catalogue row are OWED.**

**NOTHING WAS INVENTED HERE.** Minting a series is a numbering-catalogue ruling
with a migration behind it — the shape `OQ-426`/`OQ-427` took to the PO — and
the prime directive forbids an implementer choosing one. So it was ASKED, as
`OQ-PAY-12605`.

⚠ **AND IT WAS ANSWERED THE SAME DAY. `OQ-PAY-12605` IS CLOSED — PO, verbatim,
*"(a) Its own series, RFD-26-0001"*.** A refund gets `RFD-{YY}-{0000}` as a
**seeded default a tenant edits on Settings → Numbering**, like the thirty that
already exist; what is ruled is what it STARTS as. The PO declined reusing the
Payment series for a reason worth keeping: it would put two directions of money
in one counter, and a report grouping by prefix could not tell a refund from a
payment. ⚠ **NOTHING IS BACKFILLED** — refunds already issued carry no number,
and inventing one would be a reference no document ever carried.

⚠ **THE BUILD IS OWED AND IS NOT THIS LANE'S** — one catalogue row and one
nullable column, neither of which exists yet. **So what this file does is
unchanged and is now the HISTORIC path rather than the only one:** `number` is
served from `reference` when there is one, and when there is not,
`number_absence` says WHICH of the two reasons it is, so a screen prints a
sentence instead of a dash. **A dash reads as *this record has no reference*;
the truth is either *this refund is not a cheque* or *nobody has set up
numbering*** — `DEF-127`'s shape, and `S89`/`S90` took this exact decision for
the same reason. **The day `refunds.refund_no` lands, `_refund_number` serves it
first and falls back to the cheque number**, which is one line here and is
written down so the lane that adds the column does not have to find it.

═══════════════════════════════════════════════════════════════════════════════
HOW A UNION IS PAGED **IN SQL** WHEN THE TWO HALVES ARE IN TWO MODULES (NFR-3)
═══════════════════════════════════════════════════════════════════════════════
A `UNION` in one statement is not available: `credit_notes` is billing's table
and payments may not name it (B1, B2 §2). A database view would be the same
breach with a different spelling.

What IS available, and is what this does: **ask each side, in ITS OWN database
query, for the first `offset + limit` rows in the SAME order; merge the two
ordered sequences; take the window.** Both halves are `LIMIT`/`OFFSET` in SQL —
neither side ever builds a row this function will not look at, and neither ever
materialises its whole table. That is the property `NFR-3` is about.

⚠ **THE HONEST COST, STATED RATHER THAN HIDDEN (law 1):** the work grows with
`offset`, not with the table. Page 1 of 50 reads 100 rows; page 40 reads 4,000.
It is bounded, it is two indexed reads, and it is the standard shape for a
federated page. **What it is NOT is unbounded**, which is the thing the rule
forbids: there is no `limit` here any row can be beyond, so `NFR-5` holds too.
A keyset page would remove even that cost and needs a cursor both modules agree
on; it is worth doing the day a tenant pages deep, and it is not worth guessing
at today.

**THE ORDER IS `created_at` DESC, AND IT IS THE SAME KEY ON BOTH SIDES.** It is
the only instant both rows are guaranteed to have: `issued_at` is nullable on a
credit note and `approved_at`/`cleared_at` are null for most of a refund's
life, and **a page taken over an order that is null for some rows shows the
same row twice and hides another** (`notice_history_page`'s recorded lesson).
Ties break on `id` — uuid7, so the tiebreak is itself creation order.

This module WRITES NOTHING. No clock, no money arithmetic beyond a sign, no
audit row — it is a read (hard rule 7 is about money ACTIONS).
"""

from __future__ import annotations

from typing import Any

from apps.payments import billing_seam, models, selectors
from core import errors
from core import tenancy as core_tenancy


def _tenant_id() -> Any:
    """The tenant in context, or a refusal — the same helper every payments
    module carries (`refunds._tenant_id`, `notices._tenant_id`), rather than
    reaching into a sibling's private name. hard rule 1: a query with
    `app.tenant_id` unset matches ZERO ROWS AND REPORTS SUCCESS, so the absence
    is raised here and never read as *this tenant has nothing*."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


#: The two kinds, as the `kind` discriminator spells them. One vocabulary: the
#: filter, the row and the `lifecycles` descriptor all use these strings, so a
#: screen cannot be shown a word it cannot filter by.
KIND_REFUND = "refund"
KIND_CREDIT_NOTE = "credit_note"
KINDS: tuple[str, ...] = (KIND_REFUND, KIND_CREDIT_NOTE)

#: Why a row has no number a person can quote. Two DIFFERENT facts, kept apart
#: for `DEF-127`'s reason: one is a property of this refund and the other is a
#: gap in the tenant's settings, and a clerk sent to fix the second when it is
#: the first has been sent to fix nothing.
NUMBER_ABSENT_NO_SERIES = "refunds_have_no_number_series"
NUMBER_ABSENT_NOT_A_CHEQUE = "refund_is_not_a_cheque"
NUMBER_ABSENT_HISTORIC_NOTE = "credit_note_predates_numbering"

#: What each kind's lifecycle IS — carried on every response rather than known
#: by the screen, so the Kind column (P4.26) renders a STATED ABSENCE for a
#: credit note's state instead of an empty cell (B14 rule 32).
LIFECYCLES: dict[str, dict[str, Any]] = {
    KIND_REFUND: {
        "has_state": True,
        "states": list(models.REFUND_STATUSES),
        "detail": "a refund is raised, approved, issued and cleared — four acts, and "
        "BR-PAY-037 keeps the first two recorded distinctly.",
    },
    KIND_CREDIT_NOTE: {
        "has_state": False,
        "states": [],
        "detail": "a credit note has no state column at all. It is raised, numbered, posted "
        "and issued in one act, and the row then freezes (billing/0002). There is nothing to "
        "know rather than nothing known.",
    },
}


def _refund_page(*, upto: int) -> list[dict[str, Any]]:
    """The tenant's refunds, newest first, `LIMIT upto` — in SQL.

    ⚠ **IT DOES NOT CALL `selectors.refund_queue`.** That read is the APPROVAL
    QUEUE and is unpaginated *deliberately* — its own words: *"a page of an
    approval queue is a queue that lies about what is pending."* Building this
    list on it would either page the queue (breaking that) or build every
    refund the tenant has ever had (breaking `NFR-3`). Two questions, two reads,
    one **row shape**: `selectors.refund_row` is called for every row here, so a
    refund cannot look like one thing in the queue and another in this list.

    Ordered `-created_at, -id` rather than the queue's `-requested_at`:
    `requested_at` is NULLABLE on the model, and a page over a nullable sort key
    is the instability `notice_history_page` records.
    """
    if upto <= 0:
        return []
    rows = models.Refund.objects.filter(tenant_id=_tenant_id()).order_by("-created_at", "-id")[
        :upto
    ]
    out: list[dict[str, Any]] = []
    for row in rows:
        out.append({"_at": row.created_at, "_id": str(row.pk), "_row": selectors.refund_row(row)})
    return out


def _refund_number(row: dict[str, Any]) -> tuple[str | None, str | None]:
    """The number a person quotes for a refund, or WHY there is none.

    See the module docstring: refunds have no series. `reference` is the cheque
    number the clerk typed — the bank's, not ours.

    ⚠ **THIS SENTENCE SAID `refunds.request_refund` REQUIRED IT FOR CHEQUES
    UNTIL 2026-09-23, AND IT IS NOW `issue_refund` THAT DOES (`DEF-PAY-6331`).**
    The requirement did not move method — it is still cheques only — it moved
    ACT, to the one that writes the cheque. **Which makes the branch below the
    ORDINARY case rather than an edge one:** every cheque refund between raise
    and issue now has no number, where before it had a guess.
    """
    reference = (row.get("reference") or "").strip()
    if reference:
        return reference, None
    if (row.get("method") or "") == models.REFUND_METHOD_CHECK:
        # A cheque with no reference means the number has not been written yet:
        # the row is still `requested`/`approved` and nothing has left the
        # building. That is a real, temporary state, not the missing series.
        return None, NUMBER_ABSENT_NO_SERIES
    return None, NUMBER_ABSENT_NOT_A_CHEQUE


def _row_for_refund(entry: dict[str, Any]) -> dict[str, Any]:
    """One refund as a union row — **with** its `status`, because it has one."""
    row = entry["_row"]
    number, absence = _refund_number(row)
    return {
        "kind": KIND_REFUND,
        "id": row["id"],
        "account_id": row["account_id"],
        # A MAGNITUDE — see the module docstring. The signed figure is untouched
        # on `source.amount`, which for a refund is already positive.
        "amount_returned": _magnitude(row["amount"]),
        "currency": row["currency"],
        "reason": row.get("reason"),
        "occurred_at": _iso(entry["_at"]),
        "number": number,
        "number_absence": absence,
        # ⚠ PRESENT ON THIS KIND ONLY. A credit-note row below has no such key.
        "status": row["status"],
        "source": row,
    }


def _row_for_credit_note(entry: dict[str, Any]) -> dict[str, Any]:
    """One credit note as a union row — **without** a `status` key, deliberately.

    Read the module docstring before adding one. Every value a `status` could
    hold here is false, and `lifecycles` on the envelope is what a screen uses
    to draw the stated absence.
    """
    row = entry["_row"]
    number = row.get("credit_note_no")
    return {
        "kind": KIND_CREDIT_NOTE,
        "id": row["id"],
        "account_id": row["account_id"],
        # `credit_notes.amount` is NEGATIVE by CHECK constraint (BR-BIL-074).
        # The single `abs()` this module performs, in one place, with its reason
        # in the docstring — never a reader compensating per row (DEF-085).
        "amount_returned": _magnitude(row["amount"]),
        "currency": row["currency"],
        "reason": row.get("reason"),
        "occurred_at": row.get("created_at"),
        "number": number,
        "number_absence": None if number else NUMBER_ABSENT_HISTORIC_NOTE,
        "source": row,
    }


def _magnitude(amount: Any) -> str:
    """`abs()` of a decimal STRING, without going through a float.

    The sign is a leading `-` or nothing at all — `_decimal_str` on both sides
    emits a plain decimal string off `NUMERIC(18,6)`. Stripping the character is
    exact; `abs(Decimal(...))` would be too, and `abs(float(...))` is the money
    defect hard rule 2 exists to prevent. Neither side is re-parsed, so no
    rounding site is added.
    """
    text = str(amount)
    return text[1:] if text.startswith("-") else text


def _iso(moment: Any) -> str | None:
    return None if moment is None else moment.isoformat()


def page(*, offset: int = 0, limit: int, kind: str | None = None) -> dict[str, Any]:
    """ONE PAGE of everything this utility has given back.

    `kind` narrows to one source and is REFUSED rather than ignored when it is
    not one of the two — an unknown filter answering an empty list is
    indistinguishable from a real empty list, which is `refund_queue`'s own
    recorded trap and `write_off_queue`'s before it.

    ⚠ **WHEN ONE SOURCE CANNOT BE ASKED, THE LIST SAYS SO ON EVERY PAGE.** The
    seam returns a problem rather than raising, so a tenant whose billing module
    publishes no credit-note read still gets their refunds — with
    `credit_notes_read_unavailable` on the envelope and a `count` that says it
    counts refunds only. **A short list with no number attached to what it left
    out is `G32`'s defect**: a true zero over a scope it silently excluded.
    """
    if kind is not None and kind not in KINDS:
        raise errors.ValidationError(
            errors.VAL_UNKNOWN_LOOKUP,
            message_key="payments.refundsAndCredits.kind_unknown",
            params={"kind": kind, "supported": list(KINDS)},
        )
    start = max(int(offset), 0)
    size = max(int(limit), 0)
    upto = start + size

    problems: list[dict[str, Any]] = []
    entries: list[tuple[Any, str, dict[str, Any]]] = []
    count = 0

    if kind in (None, KIND_REFUND):
        count += models.Refund.objects.filter(tenant_id=_tenant_id()).count()
        for entry in _refund_page(upto=upto):
            entries.append((entry["_at"], entry["_id"], _row_for_refund(entry)))

    if kind in (None, KIND_CREDIT_NOTE):
        note_count, count_problems = billing_seam.credit_notes_count()
        count += note_count
        problems.extend(count_problems)
        rows, page_problems = billing_seam.credit_notes_page(offset=0, limit=upto)
        for code in page_problems:
            if code not in problems:
                problems.append(code)
        for row in rows:
            # `created_at` crosses the seam as an ISO STRING, and ISO-8601 with a
            # fixed offset sorts correctly as text. It is parsed back rather than
            # compared as text anyway, because the refund side holds real
            # datetimes and comparing a str with a datetime raises.
            entries.append(
                (_parse(row.get("created_at")), row["id"], _row_for_credit_note({"_row": row}))
            )

    # THE MERGE. Both sequences arrive newest-first from their own SQL; this
    # interleaves them and takes the window. Sorting `upto` rows is what a
    # federated page costs and it is bounded by the page, never by the table.
    entries.sort(key=lambda entry: (_sort_key(entry[0]), entry[1]), reverse=True)
    window = entries[start : start + size] if size > 0 else []

    return {
        "rows": [row for _, _, row in window],
        "count": count,
        "offset": start,
        "limit": size,
        "kind": kind,
        "kinds": list(KINDS),
        "lifecycles": {name: dict(body) for name, body in LIFECYCLES.items()},
        "problems": problems,
    }


def _parse(value: Any) -> Any:
    """An ISO instant back to a `datetime`, or None — never an exception.

    A row whose `created_at` cannot be read sorts LAST rather than crashing the
    page: the column is `auto_now_add` and cannot be null, so this is defensive
    against a future seam change, and a list that refuses to render because one
    row is odd is worse than one that puts it at the bottom and shows the rest.
    """
    if value in (None, ""):
        return None
    from datetime import datetime

    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return None


def _sort_key(moment: Any) -> tuple[int, str]:
    """Order instants with `None` LAST under `reverse=True`, without comparing types.

    `sorted` on a mixed list of `datetime` and `None` raises, and mixing naive
    and aware datetimes raises too — both are real possibilities across a seam.
    So the key is a pair: a presence flag, then the ISO text, which for a fixed
    offset sorts identically to the instant.
    """
    if moment is None:
        return (0, "")
    return (1, moment.isoformat())


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-138-BRC07 §3 P4.25 · 05-prototype/06 Payments Page Blueprint.pdf
#         p23 + screen 6·1 · apps/payments/billing_seam.py · apps/billing/
#         models.CreditNote · apps/payments/models.Refund · B1 · B2 §2 ·
#         BR-BIL-074 · BR-PAY-037 · B14 rules 31/32 · NFR-3 · NFR-5
# generated: 2026-09-23 by the CR-138 lane P4-READS
# checklist: A✔ B=deferred(P4.26 owns screen 6·1's Kind column and is HELD to
#            wave 2) C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — see the test file's own header.
# exceptions:
#   (1) THE TWO LIFECYCLES ARE NOT FLATTENED AND A CREDIT-NOTE ROW HAS NO
#       `status` KEY AT ALL. P4.26 requires it in terms; every value a
#       synthesised status could hold is false. `lifecycles` on the envelope is
#       how a screen knows to draw a stated absence (B14 rule 32).
#   (2) ⚠ **REFUNDS HAD NO NUMBER SERIES AND ONE WAS NOT INVENTED — IT WAS
#       ASKED, AND RULED THE SAME DAY.** The task line says "two number series";
#       only `Credit memo #` existed. `OQ-PAY-12605` is CLOSED on option (a):
#       `RFD-{YY}-{0000}`, day one `RFD-26-0001`, a seeded default a tenant
#       edits. **The catalogue row and the `refund_no` column are OWED and are
#       not this lane's.** Until they land this serves `reference` (the cheque
#       number, the bank's) with `number_absence` naming which of two reasons
#       applies; `_refund_number` is the one place that changes.
#   (3) THE PAGE IS FEDERATED, NOT A SINGLE `UNION`: payments may not name
#       `credit_notes` (B1/B2 §2). Each side pages in its OWN SQL and the
#       window is taken after the merge; the cost grows with `offset` and never
#       with the table, and there is no cap any row can be beyond.
#   (4) `amount_returned` IS A MAGNITUDE, positive for both kinds, because
#       `credit_notes.amount` is negative by CHECK constraint (BR-BIL-074) and
#       one column carrying both signs is `DEF-085` again. The signed figure is
#       untouched on `source.amount`, and the `abs()` is a string operation so
#       no float touches the money path.
#   (5) THIS READ DOES NOT NET INTO ANY BALANCE, for the reason CS-38 rejects by
#       name: a second source of truth for what an account owes, in a second
#       module.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-014 (Send statement) — `CR-094-BRC01` wave M, releasing the
#           ✉ quick action `ACC-Q07` that has refused since the rail was drawn.
#           Screens: S21 Account detail (the ✉ glyph) · S59 (the same figures,
#           as a report)
# Rules:    BR-CUS-040 (statement ≠ bill: a range ledger plus the "nothing is
#           due" disclaimer; CONFIRMED, PO closure batch 2026-08-08) ·
#           A19 §1 statement row + A19 rule 1 (BOTH the printed statement and
#           the statement email must say nothing is due) · BR-LED-010 (the
#           range ledger itself) · BR-REP-002 (read models over the books,
#           never a parallel query) · BR-NOT-005 (a document is WRITTEN to the
#           outbound queue; only the dispatcher sends) · BR-NOT-013 (nothing
#           dispatches this release) · BR-NOT-024 / BR-BIL-036 (print is the
#           floor on a customer document) · BR-TEN-017 (utility identity is
#           stamped AT RENDER) · BR-TEN-043 (the caller names the date; no
#           clock is read here) · CLAUDE.md hard rule 1 (tenant scoping) ·
#           rule 2 (money stored 4dp, DISPLAYED 2 — nothing here rounds) ·
#           rule 4 (financial immutability — this writes no money row) ·
#           rule 6 (idempotency) · rule 7 (the queue write's audit row)
# Tests:    06-backend/tests/test_cr094_m_send_statement.py
# Impacts:  apps/ledger/reporting.account_ledger (the figures, resolved BY NAME
#           — billing never imports the ledger) · apps/notifications/services.
#           queue_document (the only writer of `outbound_messages`, resolved BY
#           NAME) · apps/customers/selectors (the name and the address, through
#           the reads customers already publishes) · apps/billing/statement_api
# ───────────────────────────────────────────────────────
"""THE ACCOUNT STATEMENT — built from figures that already existed, and QUEUED.

══════════════════════════════════════════════════════════════════════════
WHAT THIS WAVE ACTUALLY FOUND, BECAUSE IT CHANGES HOW THIS FILE READS
══════════════════════════════════════════════════════════════════════════
The brief said *"nothing renders a statement"*. That was this session's own
sentence and the measurement (12-governance/02-decision-log.md, 2026-09-13)
came back the other way round: **all three parts already existed and not one
of them was joined to the next.**

  * **The wording** — `email_statement` has been seeded and live in
    `apps/notifications/seed_templates.py` the whole time, already carrying
    A19 rule 1's disclaimer verbatim: *"It is not a bill, and nothing is due
    from this statement."*
  * **The figures** — `apps.ledger.reporting.account_ledger` has returned an
    opening balance, dated rows and period totals since **2026-08-11**
    (`dea0d6f0b`, dated with `git log -S`). Put A19 §1's definition of a
    statement beside its return value — *"a running ledger over a date range —
    date / description / reference / charges / payments / balance"* — and they
    are the same list in the same order.
  * **The queue** — `notifications.services.queue_document` has been the one
    writer of `outbound_messages` since the beginning.

So this file is **WIRING and not building** (hard-won law 2), and the reason
no check ever caught the gap is that each of the three parts is correct,
tested and live *on its own*. Nothing here computes a figure; if it did, it
would be a second derivation of money the books already state (BR-REP-002),
and the first time the two disagreed a clerk would have to decide which screen
was lying.

⚠ **THE REFUSAL THIS REPLACES NAMED A REASON THAT HAD BEEN FALSE FOR A
MONTH.** `accountRailReadiness.ts` held *"the account-ledger derived view a
statement would read does not exist"* — written four days AFTER
`account_ledger` landed. That is hard-won law 1: a comment claiming a gap,
which nothing re-checks, outliving the gap. Its OTHER half was right and is
kept: `GET /reports/customer-statement` (CR-060 C16) is **not** this document
and must never be pointed at this glyph — see `WHY THE CUSTOMER STATEMENT IS A
DIFFERENT DOCUMENT` below.

══════════════════════════════════════════════════════════════════════════
IT MINTS NO MONEY, AND THAT IS THE WHOLE POSTURE
══════════════════════════════════════════════════════════════════════════
A statement is a SUMMARY of what is already recorded. Every figure on it is
the ledger's own, reached through `account_ledger` and passed through
untouched. Specifically:

  * **Nothing here rounds.** CLAUDE.md rule 2 stores money to 4 decimals and
    DISPLAYS 2, and the display rounding happens in ONE place —
    `rendering.format_money`, on the far side of the queue row's JSON column.
    That is why every amount below travels as a **`Decimal` and never as a
    string**: `rendering.encode_context` tags Decimals on the way in and
    restores them on the way out, and a string here would print `123.4500` on
    a customer's statement (the same reasoning `receipts.py` writes out).
  * **No B4/B5 figure is touched.** Those are ❄️ FROZEN and a statement has no
    arithmetic of its own to freeze — it restates. If a statement ever needed
    a new money rule, that would be a question to mint, not a value to choose.
  * **No money row is written** (hard rule 4). The only write is the queue row,
    and `queue_document` writes its own hard-rule-7 audit row for it, naming
    the actor this file hands down. A second audit row here would be two
    statements of one event.

══════════════════════════════════════════════════════════════════════════
"SEND" MEANS **QUEUE**, AND THE SCREEN SAYS SO
══════════════════════════════════════════════════════════════════════════
`BR-NOT-005` and `BR-NOT-013`: a document is WRITTEN to `outbound_messages`
and only the dispatcher sends. **No vendor is connected on email, text or post
and none is this release** (PO, 15 August 2026), and the code that would hand
a message to one does not exist. So nothing in this module, its API or its
screen uses the word *sent*. A statement that told a clerk it had been sent
would be false on every account in the product.

══════════════════════════════════════════════════════════════════════════
TWO CHANNELS, AND THE PRINT ONE HAS NO WORDING YET
══════════════════════════════════════════════════════════════════════════
`account` is one of the six source kinds carrying `BR-NOT-024`'s PRINT FLOOR
(*"don't switch of print for any document it is awayls on"*, PO 2026-08-29),
so asking for email alone still produces a print row — correctly, because a
statement is a customer document and A19 rule 1 legislates for the printed one
by name.

⚠ **AND THE PRINTED STATEMENT HAS NO BODY ON ANY DEPLOYMENT.** The class is
declared in `catalogs.py` with its ten tokens and
`mandatory_content=("nothing is due",)`, and `seed_templates.py` **excludes**
it, on the ground that *"Bills and statements are BILLING's registry (B2 r10
#4) and are seeded by `apps.billing.services.seed_bill_templates`"* — a name
that resolves to `templates_service.seed_platform_default`, which seeds the
BILL LAYOUT and plants no statement body at all. That is `DEF-123`'s shape one
document to the left, and it is **reported on every result rather than
papered over** (`STATEMENT_PRINT_WORDING_ABSENT`). It is not invented here:
authoring the printed statement's wording is a document-registry act with an
owner named in two places, and this wave does not quietly become that owner.
Filed as `DEF-BIL-5133`.

══════════════════════════════════════════════════════════════════════════
WHY THE CUSTOMER STATEMENT (CR-060 C16) IS A DIFFERENT DOCUMENT
══════════════════════════════════════════════════════════════════════════
`GET /reports/customer-statement?customer={id}` already exists and was read
end to end before any of this was designed, because the standing instruction
is not to build a second copy of something. **It is not this and it is not
close.** It is *one customer, their accounts, each balance, and a total across
them* — keyed on a CUSTOMER where ✉ is on an ACCOUNT, over **no date range at
all**, with no ledger lines, no disclaimer and no queue write. Set it against
the ten tokens the `statement` class declares and it supplies a per-account
closing balance and **none** of `period_start`, `period_end`,
`opening_balance`, `ledger_date`, `description`, `reference`, `charges`,
`payments`, `running_balance`.

Pointing ✉ at it would ship a button that produces the wrong document, which
is worse than one that refuses. That report is left exactly as it is.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

from core import errors

# ── The three owners this file reaches, each BY NAME (B1) ─────────────────
#: The books. `account_ledger` is a published READ and billing never imports
#: the ledger — the same posture `posting_seam.py` takes for the write half.
LEDGER_MODULE = "ledger"
LEDGER_KIND = "reporting"
LEDGER_READ = "account_ledger"

#: The queue's owner. `queue_document` is the ONLY write path into
#: `outbound_messages` (B1) and this file never touches that ORM.
QUEUE_MODULE = "notifications"
QUEUE_WRITE = "queue_document"

#: Customers' own published reads — the name on the greeting and the address
#: the statement is *for*. `delivery_recipients_for_account` is deliberately
#: the SAME read `notifications` uses to put an address on the queue row, so
#: the name in "Hi Maria," and the name on the envelope are one fact.
CUSTOMERS_MODULE = "customers"
RECIPIENT_READ = "delivery_recipients_for_account"
ACCOUNT_READ = "account_detail"

#: `notifications.template_service.published_versions` — used ONLY to tell a
#: clerk that the printed statement has no wording. It decides nothing.
TEMPLATE_MODULE = "notifications"
TEMPLATE_KIND = "template_service"
TEMPLATE_VERSIONS = "published_versions"

#: A19 §1's two template classes for this one document. `frozen_documents.py`
#: already maps BOTH onto the single kind `statement`, because *"the printed
#: statement and the statement email are one document"*.
PRINT_TEMPLATE_CODE = "statement"
EMAIL_TEMPLATE_CODE = "email_statement"

CHANNEL_PRINT = "pdf_print"
CHANNEL_EMAIL = "email"

#: `outbound_messages.source_type`. **`account`, and the choice is load-bearing
#: twice over.** It is what the statement is ABOUT — there is no single row for
#: "this account between these two dates" — and it is one of the six kinds
#: carrying `BR-NOT-024`'s print floor, so filing a statement under a kind with
#: no floor would quietly drop the paper copy A19 rule 1 names.
SOURCE_TYPE = "account"

#: The namespace the deterministic `source_id` is minted in. UUID5 rather than
#: a random id **because the id IS the idempotency** (hard rule 6): the queue's
#: key is `(tenant, source_type, source_id, channel, copy_no)`, so the same
#: account over the same period must produce the same id or a double-clicked
#: button queues two statements. `runbook_ports.runbook_source_id` and
#: `payments/notices.plan_notice_source_id` mint theirs exactly this way.
STATEMENT_NAMESPACE = uuid.UUID("7c2e4b90-3f51-5a62-8d14-2b6e9c0a7f31")

# ── Problem / outcome codes. CODES, never prose ───────────────────────────
# The dispatch home and the account screen group on these, and a screen cannot
# group on a sentence (the reason `receipts.py` gives for the same choice).
STATEMENT_QUEUED = "statement_queued"
STATEMENT_EMAIL_QUEUED = "statement_email_queued"
STATEMENT_LEDGER_UNAVAILABLE = "statement_ledger_unavailable"
STATEMENT_LEDGER_UNREADABLE = "statement_ledger_unreadable"
STATEMENT_QUEUE_UNAVAILABLE = "statement_queue_unavailable"
STATEMENT_QUEUE_REFUSED = "statement_queue_refused"
STATEMENT_PRINT_WORDING_ABSENT = "statement_print_wording_absent"
STATEMENT_RECIPIENT_NAME_UNREADABLE = "statement_recipient_name_unreadable"
STATEMENT_SERVICE_ADDRESS_UNREADABLE = "statement_service_address_unreadable"


def statement_source_id(*, account_id: Any, start: date, end: date) -> uuid.UUID:
    """The stable `source_id` for one account's statement over one period.

    Same account, same two dates, same id, always — which is what makes hard
    rule 6 work here. The period is IN the id on purpose: two different periods
    are two different documents and must not collide, while the SAME period
    asked for twice is one document and must.
    """
    return uuid.uuid5(STATEMENT_NAMESPACE, f"statement|{account_id}|{start}|{end}")


def _resolve(module: str, attribute: str, kind: str = "services") -> Any:
    """The owning module's published attribute, or None.

    getattr at CALL time — the idiom `posting_seam.py`, `delivery_seam.py`,
    `customers_seam.py` and `gather.py` all use, so no import statement binds
    billing to another module's internals (B1), the boundary is greppable from
    both sides by name, and nothing here needs re-wiring when an owner moves a
    function.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    return getattr(target, attribute, None)


@dataclass(frozen=True)
class StatementFigures:
    """The books' answer for one account over one period, or why there is none.

    `readable is False` means the question could not be PUT — the ledger
    publishes no read, or this tenant has designated no AR account. It is NOT
    the same as an account with no movements, which is `readable=True` with an
    empty `rows` and an opening balance that carries forward. **Collapsing the
    two would print a statement footing 0.00 over books nobody could read**,
    which is `DEF-127` exactly, one document along.
    """

    account_id: str
    readable: bool = False
    period_start: date | None = None
    period_end: date | None = None
    opening_balance: Decimal | None = None
    closing_balance: Decimal | None = None
    charges: Decimal | None = None
    payments: Decimal | None = None
    currency: str | None = None
    rows: tuple[dict[str, Any], ...] = ()
    problems: tuple[dict[str, Any], ...] = ()


def statement_figures(account_id: Any, *, start: date, end: date) -> StatementFigures:
    """The range ledger for one account — the LEDGER's figures, untouched.

    `BR-LED-010` and `BR-REP-002`. Every number below is `account_ledger`'s
    own; this function copies and never computes. The running balance in
    particular is the server's per row (US-LED-009 §7's `r_n = r_{n-1} +
    charge_n - payment_n`), for the same reason `AccountLedgerReportPage`
    refuses to accumulate one in the browser.

    ⚠ **AN INVERTED RANGE IS THE LEDGER'S OWN REFUSAL AND IS LET THROUGH.**
    `account_ledger` raises rather than answering an empty-but-plausible report
    (US-LED-009 TC-6), and catching that here to return a friendlier shape
    would be a second statement of the same rule — and the weaker one.
    """
    account_key = str(account_id)
    read = _resolve(LEDGER_MODULE, LEDGER_READ, LEDGER_KIND)
    if read is None:  # pragma: no cover - the ledger publishes this today
        return StatementFigures(
            account_id=account_key,
            problems=(
                {
                    "code": STATEMENT_LEDGER_UNAVAILABLE,
                    "br_ref": "BR-LED-010 · BR-REP-002",
                    "detail": "the account's ledger could not be read at all, so no "
                    "statement was produced. Nothing was estimated: a statement is a "
                    "restatement of the books, and a summary assembled without them "
                    "would be a new set of figures wearing the books' name.",
                },
            ),
        )

    answer = read(account_id, start=start, end=end)
    if not isinstance(answer, dict):  # pragma: no cover - defensive
        return StatementFigures(
            account_id=account_key,
            problems=(
                {
                    "code": STATEMENT_LEDGER_UNREADABLE,
                    "br_ref": "BR-LED-010",
                    "detail": "the books answered something this statement could not "
                    "read, so nothing was produced. An unreadable answer is not the "
                    "same fact as an account with no activity, and neither is guessed.",
                },
            ),
        )

    # ⚠ `unavailable` is the LEDGER's own list of what it could not do — no AR
    # designation, no premises dimension, the Reference column carrying a uuid.
    # It travels VERBATIM rather than being re-worded here: the owner's
    # sentence is the one a clerk can act on, and a paraphrase is a second
    # statement of the gap that will drift (hard-won law 1).
    ledger_gaps = tuple(dict(gap) for gap in (answer.get("unavailable") or ()))
    no_ar = any(
        gap.get("code") == "no_account_carries_the_accounts_receivable_designation"
        for gap in ledger_gaps
    )
    totals = dict(answer.get("totals") or {})
    period = dict(answer.get("period") or {})

    if no_ar:
        # The books cannot be asked at all. `account_ledger` answers zeros in
        # this case so that S59 can draw a shaped report; a STATEMENT must not
        # carry them to a customer — DEF-127's exact lesson.
        return StatementFigures(
            account_id=account_key,
            readable=False,
            period_start=period.get("start") or start,
            period_end=period.get("end") or end,
            problems=ledger_gaps,
        )

    return StatementFigures(
        account_id=account_key,
        readable=True,
        period_start=period.get("start") or start,
        period_end=period.get("end") or end,
        opening_balance=answer.get("opening_balance"),
        closing_balance=totals.get("closing_balance"),
        charges=totals.get("charges"),
        payments=totals.get("payments"),
        currency=answer.get("currency"),
        rows=tuple(
            {
                "date": getattr(row, "entry_date", None),
                "type": getattr(row, "type", None),
                "reference": getattr(row, "reference", None),
                "description": getattr(row, "description", None),
                "charge": getattr(row, "charge", None),
                "payment": getattr(row, "payment", None),
                "running_balance": getattr(row, "running_balance", None),
            }
            for row in (answer.get("rows") or ())
        ),
        problems=ledger_gaps,
    )


def _greeting_name(name: str | None) -> str | None:
    """`{first_name}` from notifications' shared greeting rule (DEF-NOT-10542)."""
    greet = _resolve("notifications", "greeting_name", "customer_context")
    return greet(name) if callable(greet) else None


def _recipient_name(account_id: Any) -> str | None:
    """Who the statement greets — through customers' OWN published read.

    `delivery_recipients_for_account` is the read `notifications` already calls
    to put an ADDRESS on the queue row. Reading the same one for the greeting
    is deliberate and is `receipts.py`'s precedent: the name in *"Hi Maria,"*
    and the name on the envelope are then one fact, and a statement addressed
    to one person and greeting another is a defect no gate in this repo can
    see.

    An account with no contact returns `None` with NO problem row. That is an
    ordinary account and not a fault — the statement greets nobody by name and
    the renderer prints its named absence, exactly as it does for every other
    missing value (OQ-117's closure: a document with a NAMED absence still goes
    out, because the customer needs the rest of it).
    """
    read = _resolve(CUSTOMERS_MODULE, RECIPIENT_READ, "selectors")
    if read is None:  # pragma: no cover - customers publishes this today
        return None
    answered = dict(read(account_id, channels=(CHANNEL_EMAIL, CHANNEL_PRINT)) or {})
    for entry in answered.values():
        name = ((entry or {}).get("snapshot") or {}).get("name")
        if name:
            return str(name)
    return None


def _account_facts(account_id: Any) -> tuple[str | None, str | None, tuple[dict[str, Any], ...]]:
    """`(account_no, service_address, problems)` — the header band's two names.

    ⚠ **THE SERVICE ADDRESS IS WALKED TO, NEVER STORED** (hard rule 8 /
    `BR-MET-1161`): an address lives on `premises` and nowhere else, and every
    other entity derives it. `account_detail`'s `premise_locality` is the
    customers module's own walk — through the UNIT when there is one and
    through `accounts.premises_id` for an owner's account that names none — so
    this reads the answer rather than repeating the walk. A second walk here
    would be a second statement of `BR-CUS-1010`'s precedence and the one that
    drifts.

    The three locality columns are COMPOSED into one line here because a
    statement's `{service_address}` token is a sentence a person reads, not a
    mailing address a machine sorts. `mailing_address_for_account` exists for
    the machine case and deliberately composes nothing.
    """
    read = _resolve(CUSTOMERS_MODULE, ACCOUNT_READ, "selectors")
    if read is None:  # pragma: no cover - customers publishes this today
        return (
            None,
            None,
            (
                {
                    "code": STATEMENT_SERVICE_ADDRESS_UNREADABLE,
                    "br_ref": "BR-MET-1161",
                    "detail": "the account's own details could not be read, so the statement "
                    "names neither the account nor the address it is for. Both print as a "
                    "named absence rather than as a blank.",
                },
            ),
        )
    detail = read(account_id)
    if not isinstance(detail, dict):  # pragma: no cover - defensive
        return None, None, ()
    locality = detail.get("premise_locality") or {}
    parts = [
        str(locality.get(part))
        for part in ("city", "state", "postal_code")
        if locality.get(part) not in (None, "")
    ]
    # "Austin, TX 78704" — comma after the city only, which is how the account
    # header next door already writes it.
    line: str | None = None
    if parts:
        line = parts[0] if len(parts) == 1 else f"{parts[0]}, {' '.join(parts[1:])}"
    return detail.get("account_no"), line, ()


def statement_render_context(
    account_id: Any, *, start: date, end: date
) -> tuple[dict[str, Any], StatementFigures, tuple[dict[str, Any], ...]]:
    """Every token the two statement bodies can name, and what it is worth.

    Returns `(context, figures, problems)`. The context goes straight to
    `queue_document(render_context=...)`, which stamps it on the queue row so
    the dispatch-time render has the figures `BR-NOT-012` says live there.

    ⚠ **MONEY TRAVELS AS `Decimal`, NEVER AS A STRING.** `rendering.
    encode_context` tags Decimals on the way in and restores them on the way
    out, and `format_money` — the ONE display-rounding path, 2 dp beside the
    tenant's `CHAR(3)` (CLAUDE.md rule 2) — runs on the far side of that JSON
    column. A string here would print `123.4500` on a customer's statement.

    ⚠ **THE UTILITY'S OWN VALUES ARE NOT HERE, AND THEIR ABSENCE IS
    DELIBERATE.** `utility_name`, `utility_address`, `support_phone`,
    `support_email` and `utility_website` are stamped AT RENDER by
    `rendering._identity_context` (`BR-TEN-017`), which is why the seeded
    email body can already say *"Call {support_phone}"* without this file
    knowing the number. Putting them in here would be a second source for the
    masthead and the one that goes stale when a tenant edits Settings.

    ⚠ **NOTHING WRITES AND NO TRANSACTION IS WIDENED** (hard rule 4). This is
    three published reads and a dict.
    """
    # ⚠ **THE ACCOUNT IS RESOLVED FIRST, AND IT IS THE ONLY THING HERE THAT
    # RAISES.** `customers.selectors.account_detail` answers
    # `deny_as_not_found` for an id this tenant does not hold — 404-never-403,
    # because from outside a tenant an id that exists elsewhere and one that
    # does not are the same fact (HR-1 / G4). That refusal is let THROUGH
    # rather than turned into a problem row: a statement for somebody else's
    # account is not a document with a gap in it, it is not a document. Doing
    # it before the ledger read also means a foreign id costs one query.
    account_no, service_address, address_problems = _account_facts(account_id)
    figures = statement_figures(account_id, start=start, end=end)
    name = _recipient_name(account_id)

    context: dict[str, Any] = {
        # ── the period, which is the one thing a statement IS over ──────────
        "period_start": figures.period_start,
        "period_end": figures.period_end,
        # ── the books' own figures, copied and never computed ───────────────
        "opening_balance": figures.opening_balance,
        "closing_balance": figures.closing_balance,
        "charges": figures.charges,
        "payments": figures.payments,
        # ⚠ **THE RUNNING-LEDGER BAND IS DELIBERATELY *NOT* HERE, AND THE
        # REASON IS A TRAP WORTH WRITING DOWN.** `rendering.encode_context` is
        # **TOP-LEVEL ONLY**: it tags a `Decimal`, a `datetime` or a `date`
        # sitting directly under a key, and anything nested inside a list or a
        # dict falls through its `else` branch untouched. A `rows` array of
        # dated Decimals therefore reaches Django's JSONField as raw Python and
        # dies at `json.dumps` with *"Object of type date is not JSON
        # serializable"* — which is what it did the first time this was written,
        # and which is a queue write failing at the moment a clerk clicks.
        #
        # Pre-formatting them into strings to get around that would be worse: it
        # moves money's display rounding OUT of `format_money`, which CLAUDE.md
        # rule 2 keeps in exactly one place, and puts it in a billing module
        # where a second rounding rule could quietly grow.
        #
        # **And nothing would read them.** The only statement body that exists
        # is `email_statement`, which names six tokens and not one row token;
        # the band belongs to the PRINTED statement, which has no wording on any
        # deployment (`DEF-BIL-5133`). Stamping a payload no renderer reads is
        # hard-won law 2 in reverse — built, unwired, and invisible. The row
        # COUNT travels on the API result instead, so a clerk can see how much
        # activity the period held, and the rows themselves are on `figures` for
        # any caller that wants them.
        #
        # When the printed statement gains a body, it gains a row band with it,
        # and whoever writes it owns the codec question above.
        # ── who it is for ──────────────────────────────────────────────────
        "account_no": account_no,
        "customer_name": name,
        # The seeded body's greeting, by the ONE shared rule
        # (`notifications.customer_context.greeting_name`, DEF-NOT-10542), so
        # `Miller, Sarah` greets `Sarah` as on every other letter.
        "first_name": _greeting_name(name),
        "service_address": service_address,
        # ⚠ **`bill_no`, `cycle` and `bill_date` ARE IN THIS CLASS'S PALETTE
        # AND ARE DELIBERATELY ABSENT FROM THIS CONTEXT.** `catalogs.py` builds
        # the statement's tokens from `_BILL_META` minus `due_date`, which
        # carries three bill-shaped names along with it. **A statement is not a
        # bill** (BR-CUS-040) and has no bill number, no cycle and no bill
        # date; supplying one would be inventing a fact, and BR-CUS-040 —
        # *statement != bill*, CONFIRMED in the PO closure batch of 2026-08-08 —
        # is what decides it, so this is an application of signed law rather
        # than a judgment call. **No question is minted for it** (CLAUDE.md law
        # 13: a judgment recorded with its reasoning is the deliverable, a
        # question is the failure to make one). What IS reported is the
        # consequence: `catalogs.py` derives this class's palette from
        # `_BILL_META`, so the Templates screen will count three merge fields
        # for this class that no statement can ever fill. Narrowing the palette
        # is an edit to an A19-derived token set and belongs to whoever owns
        # A19, not to this wave — see the decision log, 2026-09-13.
    }
    return context, figures, address_problems + figures.problems


def _print_wording_problem() -> tuple[dict[str, Any], ...]:
    """Is there a published body for the PRINTED statement? Usually not.

    ⚠ **THIS DECIDES NOTHING AND REFUSES NOTHING.** It asks the template
    registry a question and reports the answer, because a print row is queued
    either way: `account` carries `BR-NOT-024`'s floor and A19 rule 1 names the
    printed statement explicitly. What it prevents is the silent version —
    a clerk told their statement is queued on paper, over a class that has no
    wording on any deployment. See the module docstring and `DEF-BIL-5133`.
    """
    read = _resolve(TEMPLATE_MODULE, TEMPLATE_VERSIONS, TEMPLATE_KIND)
    if read is None:  # pragma: no cover - notifications publishes this today
        return ()
    try:
        published = read(code=PRINT_TEMPLATE_CODE)
    except Exception:  # pragma: no cover - a reporting read never breaks a queue
        return ()
    if published:
        return ()
    return (
        {
            "code": STATEMENT_PRINT_WORDING_ABSENT,
            "br_ref": "BR-CUS-040 · A19 rule 1 · DEF-BIL-5133",
            # Reaches a clerk, so it names neither a rule id nor a module
            # (G28 / CLAUDE.md's DEF-1931).
            "detail": "the paper statement has no wording set up yet, so only the email "
            "copy has words in it. The paper copy is still queued and still counted; "
            "nobody has written what it should say.",
        },
    )


def queue_statement(
    *,
    account_id: Any,
    start: date,
    end: date,
    actor: Any = None,
    copy_no: int = 0,
) -> dict[str, Any]:
    """**QUEUE** one account's statement for a period. It does not send it.

    `BR-NOT-005`: the document is WRITTEN to `outbound_messages` and only the
    dispatcher sends. **Nothing dispatches this release** (`BR-NOT-013`, PO 15
    August 2026) — no vendor is connected on email, text or post — so every
    word this returns, and every word the screen draws from it, is *queued*.

    **Both channels, one document.** `frozen_documents.py` already maps the
    printed statement and the statement email onto the single kind `statement`,
    because *"the printed statement and the statement email are one
    document"* — `channel` is its own column. The two rows cannot collide:
    channel is part of the idempotency key.

    ⚠ **A REPLAY QUEUES NOTHING.** Same account, same period → same
    `source_id` → `queue_document` finds its own rows and returns
    `created=False` (hard rule 6). `copy_no` is the one deliberate door, and it
    is the caller's: a HUMAN asking for a second copy passes `copy_no=1`, which
    is a genuinely different key and a genuinely new message.

    ⚠ **AN UNREADABLE LEDGER QUEUES NOTHING AT ALL.** A statement whose figures
    could not be read is not a statement — it is a letter with a customer's
    name on it and no numbers, and it would be immutable the moment it was
    written. The problems come back instead, in the ledger's own words.
    """
    context, figures, problems = statement_render_context(account_id, start=start, end=end)

    if not figures.readable:
        return {
            "queued": [],
            "account_id": str(account_id),
            "period": {"start": start, "end": end},
            "problems": list(problems),
        }

    write = _resolve(QUEUE_MODULE, QUEUE_WRITE)
    refusal = _resolve(QUEUE_MODULE, "QueueWriteRefused")
    if write is None:  # pragma: no cover - notifications publishes this today
        return {
            "queued": [],
            "account_id": str(account_id),
            "period": {"start": start, "end": end},
            "problems": [
                *problems,
                {
                    "code": STATEMENT_QUEUE_UNAVAILABLE,
                    "br_ref": "BR-NOT-005",
                    "detail": "the outbound queue could not be reached, so this statement "
                    "was not queued. Nothing was produced and nothing was lost — ask "
                    "again once the platform is answering.",
                },
            ],
        }

    source_id = statement_source_id(account_id=account_id, start=start, end=end)
    queued: list[dict[str, Any]] = []
    extra: list[dict[str, Any]] = [*problems, *_print_wording_problem()]

    for channel, template_code, code in (
        (CHANNEL_PRINT, PRINT_TEMPLATE_CODE, STATEMENT_QUEUED),
        (CHANNEL_EMAIL, EMAIL_TEMPLATE_CODE, STATEMENT_EMAIL_QUEUED),
    ):
        pin = _resolve(QUEUE_MODULE, "TemplatePin")
        try:
            answer = write(
                source_type=SOURCE_TYPE,
                source_id=source_id,
                channels=(channel,),
                template=pin(code=template_code) if pin is not None else None,
                account_id=account_id,
                render_context=dict(context),
                copy_no=copy_no,
                actor=actor,
                job="billing.send_statement",
            )
        except Exception as broken:  # noqa: BLE001 - reported, never raised at a clerk
            if refusal is not None and isinstance(broken, refusal):
                extra.append(
                    {
                        "code": STATEMENT_QUEUE_REFUSED,
                        "br_ref": "BR-NOT-005",
                        "detail": f"the {channel} copy of this statement was refused by "
                        f"the outbound queue: {broken}",
                    }
                )
                continue
            raise
        # ⚠ **ONLY THE ROW FOR *THIS* CHANNEL, AND THE FILTER IS LOAD-BEARING**
        # — `receipts.py::_queue_one` does exactly this and for exactly this
        # reason. `account` carries `BR-NOT-024`'s PRINT FLOOR, so the email
        # call comes back having also touched the print row this loop queued on
        # its previous pass. Recording every message the call returns would
        # list `pdf_print` twice — once `created`, once not — and a clerk would
        # be told three copies were queued when two were. The floor is still
        # honoured and still reported; it is simply not double-counted.
        mine = next(
            (
                message
                for message in getattr(answer, "messages", ()) or ()
                if getattr(message, "channel", None) == channel
            ),
            None,
        )
        if mine is not None:
            queued.append(
                {
                    "code": code,
                    "channel": channel,
                    "message_id": str(getattr(mine, "id", "")) or None,
                    "created": bool(getattr(mine, "created", False)),
                }
            )
        for trouble in getattr(answer, "problems", ()) or ():
            extra.append(dict(trouble) if isinstance(trouble, dict) else {"detail": str(trouble)})

    return {
        "queued": queued,
        "account_id": str(account_id),
        "period": {"start": figures.period_start, "end": figures.period_end},
        "currency": figures.currency,
        # The three figures a clerk checks the statement by before they trust
        # it, so the confirmation can state what was queued rather than only
        # that something was. Decimals — the wire layer formats them.
        "opening_balance": figures.opening_balance,
        "closing_balance": figures.closing_balance,
        "row_count": len(figures.rows),
        "problems": extra,
    }


def parse_period(raw_start: Any, raw_end: Any) -> tuple[date, date]:
    """The two dates, or a 422 that says WHICH one is wrong.

    ⚠ **THERE IS NO DEFAULT AND NO CLOCK.** `BR-TEN-043` and gate `G6`: the
    business date is the CALLER's and nothing in a service module reads a wall
    clock. A default period invented here would also be a product decision
    taken in the quietest possible place — a statement covering the wrong three
    months is wrong in a way nobody notices. The SCREEN offers a starting range
    and the clerk can see it and change it.
    """
    parsed: list[date] = []
    for field, raw in (("from", raw_start), ("to", raw_end)):
        text = str(raw or "").strip()
        if text == "":
            raise errors.ValidationError(
                errors.VAL_REQUIRED,
                message_key="billing.statement.periodRequired",
                field_errors=[{"field": field, "code": errors.VAL_REQUIRED}],
            )
        try:
            parsed.append(date.fromisoformat(text))
        except ValueError:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="billing.statement.periodFormat",
                field_errors=[{"field": field, "code": errors.VAL_FORMAT}],
            ) from None
    return parsed[0], parsed[1]

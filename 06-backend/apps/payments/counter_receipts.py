# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 lane H — the PO ruling of 2026-09-15: *"payemnt should
#           show in payments, in ledge and in fiannce books"*, and on the two
#           ends of its life *"when it is approved you can attached it to
#           account - if it is refuse then it is application fees non
#           refundable - it stya in books"*.
# Story:    US-LED-001 (source-event posting contracts)   Screens: capture step
#           5 · the finance books · `GET /counter-receipts`
# Rules:    CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (4 dp stored,
#           2 displayed, CHAR(3), never float) · hard rule 4 (no UPDATE on a
#           money row — the release columns are the named exception, migration
#           0027) · hard rule 5 (ONLY the ledger posting service writes journal
#           lines) · hard rule 6 (a double submit posts once) · hard rule 7
#           (every money act writes `audit_log`) · hard-won law 14 (a failed
#           statement poisons the whole PostgreSQL transaction — SAVEPOINT) ·
#           BR-CUS-090 (the counter accepts what is handed over) · BR-PAY-1140
# Tests:    06-backend/tests/test_cr094_counter_receipt_posts.py
# Impacts:  apps/payments/counter_receipt_models.py (the row this writes) ·
#           apps/payments/ledger_seam.py (`post_counter_receipt_collected` /
#           `post_counter_receipt_released`) · apps/customers/payments_seam.py
#           (customers' only door) · apps/payments/api.py (the finance read)
# ───────────────────────────────────────────────────────
"""payments — the counter takings service. **The ONLY writer of
`counter_receipts`.**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — ledger posting and money rounding are
CLAUDE.md 🔒 sensitive paths. AI-authored 2026-09-15 under the PO ruling of
2026-08-09; row in `12-governance/09-human-review-ledger.md`.

────────────────────────────────────────────────────────────────────────────
WHAT CHANGED, IN ONE SENTENCE
────────────────────────────────────────────────────────────────────────────
Until today the counter took $25.00 and posted **nothing**: the money sat on
the service-request row and appeared in payments, in the ledger and on every
finance screen as an absence. The blueprint said so in red on p079 — *"This
takes money and posts nothing"* — and the PO has reversed that half of the
sentence. The other half stands and is honoured here: **no invoice and no
customer account.** A balanced pair needs neither.

────────────────────────────────────────────────────────────────────────────
THE THREE MOMENTS
────────────────────────────────────────────────────────────────────────────
    collection    DR the tender's clearing account, else 1010 Undeposited funds
                  CR 2400 Customer credit balances
    approval      DR 2400  CR the charge code's OWN revenue account
    refusal       DR 2400  CR the charge code's OWN revenue account
    ask for more  NOTHING — no entry made, none reversed

**Ask for more is not a decision about the money.** The request stays open and
the $25.00 stays where collection put it. It is written down because a reader of
only the other two clauses would reasonably wonder whether the third door needed
a posting of its own, and would then invent one.

⚠ **THE REVENUE ACCOUNT IS NEVER PICKED HERE.** It is `rating.charges.
gl_account_id` — the tenant's own mapping, edited on Settings → the charge code,
validated against the ledger when it is WRITTEN — read through
`apps.rating.selectors.gl_account_id_for_charge` / `charge_by_code`, which is
the identical read billing asks at issue (`issue._gl_account_for`, the `fee`
branch). One home for the mapping.

**WHEN THE MAPPING IS ABSENT, THE RELEASE DOES NOT POST AND THE OUTCOME IS NOT
BLOCKED.** A clerk must always be able to refuse an application; a chart gap is
not a reason to trap somebody at a counter. So the liability STAYS in 2400,
`release_error` says whose configuration to fix, and the money is visible on the
trial balance rather than silently written off. That is `payment_import_rows.
commit_error`'s rule — *"a row that skipped silently would be money nobody
chased"* — and it is the opposite of guessing an account.

⚠ **THAT BRANCH WAS THE DEMO'S ORDINARY CASE UNTIL 2026-09-16 AND IS NOT ANY
MORE (`DEF-RAT-5424`).** The paragraph here read *"AS OF 2026-09-15 THE FIXTURE
CODE `CC-REQFEE` HAS NO `charges` ROW IN ANY TENANT — Brazos Bend holds 28 codes
and that is not one of them … REPORTED rather than fixed: seeding a code and
pointing it at an account is the tenant's act and CR-066's table is the PO's,
not a lane's."* The measurement was right; the conclusion was overtaken by the
PO asking for the code — *"can you add this in seeder data"* — so
`apps.rating.sample_data.seed_sample_request_fee_charge_code` creates it at
`$25.00` on the SAMPLE-data button and `ledger.chart.CHARGE_CODE_ACCOUNTS`
starts it at **`4600` Connection & new-service fees**. `lookup_defaults.json` is
untouched, so CR-066's approved platform table is still the PO's.

**The branch itself has not moved and is not softened.** A tenant's OWN code
with no mapping, and the two other fixture codes (`CC-EXPEDITE`,
`CC-METERTEST`), take it exactly as written: nothing is guessed, nothing posts,
the money stays visible in `2400`, and the clerk is not blocked. ⚠ Those two
read *"which still have no row anywhere"* until 2026-09-23 (`DEF-CUS-6416`):
the service-request fee line is now PRICED from the catalogue, so the sample
loader creates both beside `CC-REQFEE` — `$45.00` and `$60.00` — and still
gives them NO account, which is why this branch is still the one they take.

────────────────────────────────────────────────────────────────────────────
IDEMPOTENCY — TWO GUARDS, AND THEY CATCH DIFFERENT FACTS
────────────────────────────────────────────────────────────────────────────
  `uq_counter_receipts_source`     this REQUEST has been collected before
  `posting_key` in the ledger      this EVENT has been posted before

The first is the drawing's own rule, p079: *"The same receipt number again
answers with what is already recorded; a DIFFERENT one on a request that has
already been collected is refused and names the receipt it already holds."* The
second is hard rule 6 in the ledger, keyed `counter_receipt|<id>|collected` and
`counter_receipt|<id>|released`, so a replay returns the FIRST entry and writes
nothing.

They are asserted separately in the tests, because `DEF-058` is what happens
when one guard silently stands in for another.

────────────────────────────────────────────────────────────────────────────
HARD-WON LAW 14 — WHY THE SAVEPOINT IS NOT A TIDINESS CHOICE
────────────────────────────────────────────────────────────────────────────
`_release` catches the ledger's refusal and carries on so the terminal outcome
is never blocked. On PostgreSQL a failed statement **aborts the whole
transaction**: every later query raises `InFailedSqlTransaction` and the work is
lost at COMMIT anyway. The suite runs on in-memory SQLite, which has no aborted
state, so the version without a SAVEPOINT passes everything and loses the
refusal in production. The nested `transaction.atomic()` below is the only
option, and this paragraph is here so the next lane does not simplify it away.
It is proved against a real PostgreSQL in
`tests/test_cr094_counter_receipt_posts.py`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from importlib import import_module
from typing import Any
from uuid import UUID

from django.db import DatabaseError, transaction
from django.utils.dateparse import parse_date

from apps.payments import counter_receipt_models as cr_models
from apps.payments import counters, ledger_seam, settings_seam
from apps.payments.exceptions import PaymentRuleError
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.money_fields import AMOUNT_QUANTUM

ZERO = Decimal("0")

#: The audit actions. Codes, never prose — the trail is grouped on them
#: (BR-AUD-003), and all three are MONEY ACTS under hard rule 7.
AUDIT_COLLECTED = "counter_receipt.collected"
AUDIT_RELEASED = "counter_receipt.released"
AUDIT_ATTACHED = "counter_receipt.attached"
AUDIT_ENTITY = "counter_receipt"

#: `apps.rating.selectors` — the ONE home of a charge code's GL mapping
#: (BR-BIL-010). Named as constants so the contract is greppable from both
#: sides of the boundary, exactly as `ledger_seam.GL_DESIGNATION_READ` is.
RATING_MODULE = "rating"
CHARGE_GL_READ = "gl_account_id_for_charge"
CHARGE_BY_CODE_READ = "charge_by_code"


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`.

    Refuses rather than defaulting, exactly as `services._tenant_id` does: a
    counter receipt written with no tenant context would be blocked by RLS on
    PostgreSQL and would land in another tenant's books on SQLite.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """A neighbour's published callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _money(value: Any, *, what: str) -> Decimal:
    """A `Decimal`, quantised to hard rule 2's four places. **Never a float.**

    A float is refused rather than coerced, for `post_payment_cleared`'s reason:
    a coercion hides the place where money became binary, and the refusal names
    it.
    """
    if isinstance(value, float):
        raise PaymentRuleError(
            f"{what} arrived as a float ({value!r}). Money is NUMERIC(18,6) written to four "
            "decimal places and never a float (CLAUDE.md hard rule 2). Refused rather than "
            "converted — a conversion would hide the place where money became binary.",
            br_ref="BR-PAY-002",
        )
    amount = value if isinstance(value, Decimal) else Decimal(str(value))
    return amount.quantize(AMOUNT_QUANTUM)


def _method_row(method_code: str | None) -> Any:
    """This tenant's ACTIVE `tenancy.PaymentMethod` for a code, or None.

    The capture screen speaks the service request's vocabulary — `cash`, `card`,
    `cheque` (`ServiceRequest.FEE_METHODS`) — and this module speaks the tenant's
    payment-method vocabulary, where the cheque is spelled `check` (BR-PAY-026's
    six seeds). `FEE_METHOD_TO_TENDER` below is the whole of the translation and
    it lives here rather than in customers, because which codes a tenant has is
    payments' fact.

    ⚠ **AN UNKNOWN CODE IS NOT REFUSED HERE, AND THAT IS DELIBERATE.** A method
    that resolves to nothing means the collection debits `undeposited_funds`,
    which is the documented behaviour of an unmapped tender since OQ-143 and is
    stated rather than silent. Refusing would stop a clerk taking money at a
    counter over a lookup row — the exact thing BR-CUS-090 forbids.
    """
    if not method_code:
        return None
    tender_code = FEE_METHOD_TO_TENDER.get(str(method_code).strip().lower(), method_code)
    lookup = _resolve("tenancy", "PaymentMethod", "models")
    if lookup is None:  # pragma: no cover - defensive
        return None
    return lookup.objects.filter(tenant_id=_tenant_id(), code=tender_code, active=True).first()


#: The one translation between the two vocabularies. `cheque` is the word on the
#: capture screen (British spelling, `ServiceRequest.FEE_METHOD_CHEQUE`) and
#: `check` is the tenant's seeded method code (BR-PAY-026).
FEE_METHOD_TO_TENDER = {"cash": "cash", "card": "card", "cheque": "check", "check": "check"}


def is_live_tender(method_code: str | None) -> bool:
    """Whether `method_code` is one of THIS tenant's active payment methods.

    **DEF-CUS-6376.** The request's fee modal now offers the tenant's served
    list — `GET /payments` `methods[]`, the one Record a payment offers — so a
    service request may be paid by `money_order`, `ach` or any method the
    tenant has added. Customers used to check a hand-typed `cash · card ·
    cheque`; it asks here instead, because which codes a tenant has is
    payments' fact (BR-PAY-026). The request's own `cheque` translates through
    `FEE_METHOD_TO_TENDER` exactly as `_method_row` does.
    """
    return _method_row(method_code) is not None


def till_refusal(actor: Any, method_code: str | None) -> str | None:
    """**The till rule at the counter-receipt door** — the sentence, or None.

    PO ruling 2026-09-23 §3.4, verbatim: *"(a) Refuse it. \"Start your counter
    first.\" One press, then take the money. It is the only option where every
    cash dollar belongs to somebody"* — and `OQ-PAY-12601`, closed the same
    day: *"back office or counter - if person is punching the payemnt in system
    - it is same process, they ahve to open the counter"*. A service request's
    application fee is keyed by a person, so it is inside both (`DEF-CUS-6374`).

    ⚠ **ONE IMPLEMENTATION, A SECOND CALL SITE.** The rule is
    `counters.assert_till_open_for_tender`; this only translates the request's
    spelling (`cheque` → `check`) and turns its refusal into a sentence, so
    customers never imports a payments exception. It is called at the ENDPOINT
    and not inside `record_counter_receipt`, for `P2.23`'s reason: the sample
    data seeds a counter collection for a utility that has no clerks, and a
    guard in the service would stop every fixture seeding.

    ⚠ **IT STILL DOES NOT NAME THE TILL — `record_counter_receipt` DOES, AND
    SINCE 2026-09-24 THE CLOSE COUNT SEES IT (`OQ-PAY-12621`, `DEF-PAY-6375`).**
    This function is the SENTENCE and nothing else; the till is resolved and
    written where the row is written.

    ⛔ **SUPERSEDED — what this paragraph used to say.** *"Under A2 a request
    fee is not a payment row, so it joins no deposit batch and the till's Close
    count does not see it. `DEF-PAY-6375` carries that to the PO."* The first
    half is still true and is A2's design: a fee joins **no deposit batch**,
    because a batch is a bundle of payment rows. The second half was the
    defect: the cash was in the drawer, the Close count did not expect it, and
    since the ruling of 2026-09-23 the over that created POSTED — one fee
    booked twice. PO, 2026-09-24, verbatim: *"p1 a"*. `running_split` now reads
    `counter_receipts` beside `payments`.
    """
    code = str(method_code or "").strip().lower()
    tender = FEE_METHOD_TO_TENDER.get(code, code)
    try:
        counters.assert_till_open_for_tender(actor, tender)
    except PaymentRuleError as refusal:
        return str(refusal)
    return None


def _posting_instant(row: cr_models.CounterReceipt) -> datetime:
    """The receipt's posting DAY as the instant a `Payment` stores.

    BR-TEN-081: midnight in the utility's own zone — `.replace(tzinfo=…)` on a
    wall-clock value, the same reading `payments.api._moment` gives a bare
    date. A receipt with no `posted_on` (taken before the column existed)
    keeps `taken_at`, which is what this function used to write for everyone.
    """
    if row.posted_on is None:
        return row.taken_at
    return datetime(row.posted_on.year, row.posted_on.month, row.posted_on.day).replace(
        tzinfo=settings_seam.tenant_timezone()
    )


def _text(value: Any, limit: int = 200) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] or None


def _date(value: Any) -> date | None:
    """The date on the face of a cheque, from a `date` or an ISO string.

    Parsed HERE rather than left to Django's field coercion, so a typo comes
    back as a sentence naming the field instead of as a 500 three frames down.
    Anything unparseable is refused rather than dropped: a cheque dated
    `12/05/26` silently becoming NULL is how a post-dated cheque gets banked
    early.
    """
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = parse_date(str(value).strip())
    if parsed is None:
        raise PaymentRuleError(
            f"the cheque date {value!r} is not a date. Send it as YYYY-MM-DD — an unparseable "
            "date dropped to NULL would let a post-dated cheque be banked early.",
            br_ref="BR-PAY-1140",
        )
    return parsed


def receipt_for_source(source_type: str, source_id: Any) -> cr_models.CounterReceipt | None:
    """The one receipt taken against this source, or None. Tenant-scoped."""
    return cr_models.CounterReceipt.objects.filter(
        tenant_id=_tenant_id(), source_type=source_type, source_id=source_id
    ).first()


def receipt_dict(row: cr_models.CounterReceipt | None) -> dict[str, Any] | None:
    """The published shape — what a screen, a seam and a sibling lane read.

    Money is a STRING at four places: hard rule 2 stores four and DISPLAYS two,
    and the display rounding belongs to `MoneyCell`, never to a serialiser. A
    JSON number would be a float by the time it reached the browser.

    **B14 rule 31 — no database id is ever the visible value of a field**, which
    is why `source_ref` (`SR-26-0048`) and `receipt_no` (`RCP-26-4471`) are here
    beside the uuids: a screen renders those two and never `source_id`.
    """
    if row is None:
        return None
    return {
        "id": str(row.id),
        "source_type": row.source_type,
        "source_id": str(row.source_id),
        "source_ref": row.source_ref,
        "receipt_no": row.receipt_no,
        "amount": str(row.amount),
        "currency": row.currency,
        "method": getattr(row.method, "code", None),
        "method_name": getattr(row.method, "name", None),
        "card_last4": row.card_last4,
        "card_brand": row.card_brand,
        "card_auth_code": row.card_auth_code,
        "cheque_no": row.cheque_no,
        "drawer_bank": row.drawer_bank,
        "cheque_date": row.cheque_date.isoformat() if row.cheque_date else None,
        "taken_at": row.taken_at.isoformat() if row.taken_at else None,
        # DEF-CUS-6376 — Record a payment's three facts, as that form names them.
        "posted_on": row.posted_on.isoformat() if row.posted_on else None,
        "confirmation": row.confirmation,
        "memo": row.memo,
        "state": row.state,
        "collection_entry_id": str(row.collection_entry_id) if row.collection_entry_id else None,
        "released_at": row.released_at.isoformat() if row.released_at else None,
        "earned_amount": str(row.earned_amount) if row.earned_amount is not None else None,
        "held_remaining": str(_held_remaining(row)),
        "revenue_postings": row.revenue_postings or [],
        "release_entry_id": str(row.release_entry_id) if row.release_entry_id else None,
        "release_error": row.release_error,
        "payment_id": str(row.payment_id) if row.payment_id else None,
    }


def list_queryset(*, state: str | None = None, taken_on: date | None = None) -> Any:
    """The finance read behind `GET /counter-receipts`. Tenant-scoped, ordered.

    `NFR-3` — the PAGE is taken in the database and this returns a queryset
    rather than a list, so no caller can accidentally pull every row of a
    40,000-account utility into memory. `NFR-5` — no cap is applied here and
    none may be.

    An unknown `state` is IGNORED rather than refused: a filter control that
    404s on a typo is worse than one that shows everything, and the three
    lawful values ride out on the response so a screen never has to guess them.

    ⚠ **`taken_on` IS THE DRAWER'S DAY, AND IT IS WHY THIS READ EXISTS AT ALL.**
    Until it was added the only questions this endpoint could answer were
    *everything ever taken* and *everything still held*, and a clerk balancing a
    till at 5pm needs neither. **The money is in `1010` and in `2400` and it is
    NOT in a deposit batch** — `BR-PAY-025` groups a batch by day AND method and
    writes membership onto a `payments` row, and a counter receipt is
    deliberately not one of those, because there is no account yet. So a clerk
    reconciling against batches alone finds the counter cash missing every day.
    This filter is the figure that closes that, and `list_totals` splits it by
    tender for the same reason.

    The day is matched on `taken_at__date`, which Django evaluates in the
    ACTIVE timezone — the same one `timezone.localdate()` answers in, so this
    filter and every other local-day read in the product agree with each other
    by construction rather than by coincidence.

    ⚠ **WHICH DAY THAT IS, STATED RATHER THAN IMPLIED (law 1 — a comment
    claiming a guarantee is not the guarantee).** `settings.TIME_ZONE` is
    **`UTC`** and per-tenant regional display is applied above this layer, so
    unless a caller has activated the tenant's zone this groups by the **UTC**
    day. For a utility whose counter shuts at 5pm that is the same day either
    way. **It is NOT the same day for money taken after 7pm Central**, which is
    00:00 UTC the next morning and would be reported on the following day's
    takings — the one case where a drawer and this figure could disagree. No
    counter in the product takes money that late today and nothing here guesses
    a zone; it is written down because the next reader deserves to know the
    edge exists rather than discover it from a clerk.
    """
    rows = cr_models.CounterReceipt.objects.filter(tenant_id=_tenant_id()).select_related("method")
    if state in cr_models.RECEIPT_STATES:
        rows = rows.filter(state=state)
    if taken_on is not None:
        rows = rows.filter(taken_at__date=taken_on)
    return rows.order_by("-taken_at", "-id")


def list_totals(queryset: Any) -> dict[str, Any]:
    """`taken` and `held` for the CURRENT filter, with the currency beside them.

    `held` is the figure the screen exists for: what `2400 Customer credit
    balances` is still carrying, summed as `amount − earned_amount` over the
    rows in view. It should agree with that account on the trial balance, and a
    finance clerk who finds it does not has exactly one place to look.

    ⚠ **IT STATES NO MONEY FIGURE WHEN THE ROWS COULD NOT HONESTLY BE SUMMED**
    — `DEF-099`'s rule, applied here: a currency-less total is half of hard rule
    2, and a filter that matched nothing has no currency to report. The strings
    are at four places; DISPLAY rounds to two and that is `MoneyCell`'s job.

    ⚠ **`by_method` IS WHAT A DRAWER IS ACTUALLY COUNTED AGAINST, AND A LUMP
    `taken` CANNOT BE.** A clerk counts notes and coin; a cheque and a card slip
    are not in the drawer. So `$25.00` cash plus `$30.00` by cheque reports
    `taken` `55.0000` **and** a cash line of `25.0000`, which is the only one of
    the three a till can be balanced against. The grouping is `day × method`
    deliberately: it is the vocabulary `BR-PAY-025`'s deposit batch already
    uses, so the two figures a finance clerk holds side by side are grouped the
    same way rather than nearly the same way. It is ordered by tender code so
    the line order is stable between two readings of the same day.
    """
    rows = list(queryset)
    if not rows:
        return {"taken": None, "held": None, "currency": None, "count": 0, "by_method": []}
    currencies = {row.currency for row in rows}
    taken = sum((_money(row.amount, what="amount") for row in rows), ZERO).quantize(AMOUNT_QUANTUM)
    held = sum((_held_remaining(row) for row in rows), ZERO).quantize(AMOUNT_QUANTUM)
    if len(currencies) != 1:  # pragma: no cover - BR-TEN-042 locks one currency per tenant
        return {
            "taken": None,
            "held": None,
            "currency": None,
            "count": len(rows),
            "by_method": [],
        }
    return {
        "taken": str(taken),
        "held": str(held),
        "currency": currencies.pop(),
        "count": len(rows),
        "by_method": _by_method(rows),
    }


def _by_method(rows: list[cr_models.CounterReceipt]) -> list[dict[str, Any]]:
    """The takings split by tender — one line per method, four decimals.

    A row whose method could not be resolved is grouped under `None` rather
    than dropped: money with an unreadable tender is money that still has to be
    accounted for, and silently leaving it out would make `by_method` disagree
    with `taken` — the one thing a reconciliation figure may never do.
    """
    grouped: dict[Any, dict[str, Any]] = {}
    for row in rows:
        code = getattr(row.method, "code", None)
        bucket = grouped.setdefault(
            code,
            {
                "method": code,
                "method_name": getattr(row.method, "name", None),
                "currency": row.currency,
                "_taken": ZERO,
                "_held": ZERO,
                "count": 0,
            },
        )
        bucket["_taken"] += _money(row.amount, what="amount")
        bucket["_held"] += _held_remaining(row)
        bucket["count"] += 1
    lines = []
    for code in sorted(grouped, key=lambda value: (value is None, value or "")):
        bucket = grouped[code]
        lines.append(
            {
                "method": bucket["method"],
                "method_name": bucket["method_name"],
                "taken": str(bucket["_taken"].quantize(AMOUNT_QUANTUM)),
                "held": str(bucket["_held"].quantize(AMOUNT_QUANTUM)),
                "currency": bucket["currency"],
                "count": bucket["count"],
            }
        )
    return lines


def _held_remaining(row: cr_models.CounterReceipt) -> Decimal:
    """What `2400 Customer credit balances` still holds for this receipt.

    Zero while nothing has been released and `amount − earned_amount` after —
    so a $30.00 tender against a $25.00 application fee reads **$5.0000** and a
    person can see there is money to give back. The decision-log row of
    2026-09-15 works that figure; it is not clamped and it is not silently
    earned.
    """
    if row.state == cr_models.RECEIPT_HELD:
        return _money(row.amount, what="amount")
    earned = row.earned_amount if row.earned_amount is not None else ZERO
    return (_money(row.amount, what="amount") - _money(earned, what="earned_amount")).quantize(
        AMOUNT_QUANTUM
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 · COLLECTION — the money is taken, and it reaches the books the same minute
# ═══════════════════════════════════════════════════════════════════════════
def record_counter_receipt(
    *,
    source_type: str,
    source_id: Any,
    source_ref: str | None,
    receipt_no: str,
    amount: Any,
    currency: str,
    method_code: str | None,
    taken_at: datetime,
    taken_by_id: Any = None,
    card: dict[str, Any] | None = None,
    cheque: dict[str, Any] | None = None,
    actor: Any = None,
    posted_on: date | None = None,
    confirmation: str | None = None,
    memo: str | None = None,
) -> dict[str, Any]:
    """Record what the counter took, and post it. **The collection leg.**

    **Worked, and it is the ruling's own figure:** Sarah Miller hands over
    `amount=Decimal("25.00")`, `method_code="cash"`, `receipt_no="RCP-26-4471"`
    on 12 May → one `counter_receipts` row in state `held`, and one balanced
    journal entry **DR `1010 Undeposited funds` $25.0000 · CR `2400 Customer
    credit balances` $25.0000**.

    ⚠ **IDEMPOTENT, AND IN THE DRAWING'S OWN TWO SHAPES (p079).** The same
    receipt number again RETURNS what is already recorded and posts nothing. A
    DIFFERENT number against a source already collected is REFUSED and names the
    receipt it already holds — because two receipts against one application is a
    fact no rule describes, and summing them would move money on a guess.

    ⚠ **THE POSTING IS INSIDE THIS TRANSACTION**, exactly as `record_payment`'s
    is. The alternative — post afterwards, outside — produces the one state
    nothing can repair: a money row with no entry in the books and no code path
    left that would ever write one.

    ⚠ **`posted_on` IS THE DAY THE BOOKS SAY — DEF-CUS-6376.** Record a
    payment's posting date: the business day the money counts for, typed by
    the clerk (BR-PAY-033) and read as the TENANT's day (BR-TEN-081). It is the
    collection entry's `entry_date`. Until it existed the entry was dated
    `taken_at.date()` — the date of a UTC instant — so $70.00 taken at 19:30 in
    Chicago was booked to TOMORROW. A caller that names none keeps that old
    behaviour exactly; the one production caller always names one.
    `confirmation` and `memo` are Record a payment's reference and memo, kept
    here until `attach_to_account` can put them on a payment (A2).

    A MONEY ACTION, so it writes `audit_log` (hard rule 7).
    """
    if source_type not in cr_models.SOURCE_TYPES:
        raise PaymentRuleError(
            f"{source_type!r} is not a counter surface this module knows "
            f"({', '.join(cr_models.SOURCE_TYPES)}). A receipt that cannot say what it belongs "
            "to is a receipt nobody can reconcile.",
            br_ref="BR-PAY-1140",
        )
    taken = _money(amount, what="the amount taken")
    if taken < ZERO:
        raise PaymentRuleError(
            f"a counter receipt of {taken} is negative. Money handed back is a REFUND and has "
            "its own table and its own approval (BR-PAY-018); it is never a receipt with a "
            "minus sign.",
            br_ref="BR-PAY-1140",
        )
    slip = _text(receipt_no, 120)
    if not slip:
        raise PaymentRuleError(
            "a counter receipt needs the number on the slip the clerk has just written "
            "(BR-CUS-090 names it: the request stores the quote, the cash, the method and ONE "
            "receipt number). Cash with no receipt is cash nobody can reconcile.",
            br_ref="BR-CUS-090",
        )
    card = card or {}
    cheque = cheque or {}

    with transaction.atomic():
        existing = (
            cr_models.CounterReceipt.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), source_type=source_type, source_id=source_id)
            .first()
        )
        if existing is not None:
            if existing.receipt_no == slip:
                # p079: the same receipt number again answers with what is
                # already recorded. No second row, no second entry, no second
                # audit row — the replay is the CORRECT outcome of a resumed
                # submit, not an error anyone should have to catch.
                return receipt_dict(existing)
            raise PaymentRuleError(
                f"this request has already been collected against receipt {existing.receipt_no!r} "
                f"for {existing.amount} {existing.currency}; {slip!r} is a different number. "
                "Two receipts against one application is a fact no rule describes, so it is "
                "refused by name rather than summed (blueprint p079).",
                br_ref="BR-CUS-090",
            )

        method = _method_row(method_code)
        # ── WHICH TILL IS HOLDING THIS CASH (OQ-PAY-12621, 2026-09-24) ──────
        # ⚠ **RESOLVED, NEVER REFUSED HERE.** `till_refusal` is the rule and it
        # is called at the ENDPOINT, for `P2.23`'s reason: the sample fixture
        # seeds a counter collection for a utility with no clerks, and a guard
        # in this service would stop every fixture seeding. So this reads the
        # actor's open till and writes it when there is one; **a null means the
        # receipt joins no drawer**, which is the honest answer and not a zero.
        # Without it the cash is in the drawer, the Close screen does not expect
        # it, and the over it creates POSTS — the one fee booked twice that
        # `DEF-PAY-6375` measured.
        #
        # ⚠ **ONLY A HAND TENDER JOINS A TILL, WHICH IS EXACTLY WHAT
        # `assert_till_open_for_tender` DOES FOR A PAYMENT ROW.** A card fee
        # taken at a window is not countable money — you cannot count a card
        # total in a drawer (p056 ③) — and `payments.counter_session_id` is
        # left null for `card`, `ach`, `wire` and `lockbox` for that reason.
        # Attaching a card receipt to a till would make a receipt and a payment
        # of the same tender disagree about which till they belong to, on the
        # same screen. The tender spelling is translated first (`cheque` →
        # `check`), the same one-line translation `till_refusal` does.
        tender = FEE_METHOD_TO_TENDER.get(
            str(method_code or "").strip().lower(), str(method_code or "").strip().lower()
        )
        till = (
            counters.open_counter_for(actor)
            if actor is not None and tender in counters.HAND_TENDERS
            else None
        )
        row = cr_models.CounterReceipt.objects.create(
            counter_session_id=till.pk if till is not None else None,
            tenant_id=_tenant_id(),
            source_type=source_type,
            source_id=source_id,
            source_ref=_text(source_ref, 60),
            receipt_no=slip,
            amount=taken,
            currency=(currency or "USD")[:3].upper(),
            method=method,
            card_last4=_text(card.get("last4"), 4),
            card_brand=_text(card.get("brand"), 40),
            card_auth_code=_text(card.get("auth_code"), 40),
            cheque_no=_text(cheque.get("number"), 60),
            drawer_bank=_text(cheque.get("bank"), 120),
            cheque_date=_date(cheque.get("date")),
            taken_at=taken_at,
            taken_by_id=taken_by_id,
            posted_on=posted_on,
            confirmation=_text(confirmation, 120),
            memo=_text(memo, 500),
            state=cr_models.RECEIPT_HELD,
        )
        # Hard rule 5: payments posts NOTHING itself. It hands a fully-specified
        # request to the sole writer of journal lines.
        posting = ledger_seam.post_counter_receipt_collected(
            receipt=row,
            clearing_account_id=ledger_seam.tender_clearing_account_id(row),
            # DEF-CUS-6376 — the clerk's posting day, never a UTC date.
            entry_date=posted_on if posted_on is not None else taken_at.date(),
            posted_at=taken_at,
            actor=actor,
        )
        row.collection_entry_id = UUID(str(posting.entry_id))
        row.save(update_fields=["collection_entry_id", "updated_at"])
        core_audit.write_row(
            action=AUDIT_COLLECTED,
            entity_type=AUDIT_ENTITY,
            entity_id=row.id,
            actor_user_id=taken_by_id,
            after={
                "source_type": source_type,
                "source_ref": row.source_ref,
                "receipt_no": row.receipt_no,
                "amount": str(row.amount),
                "currency": row.currency,
                "method": getattr(method, "code", None),
                "posted_on": row.posted_on.isoformat() if row.posted_on else None,
                "confirmation": row.confirmation,
                "memo": row.memo,
                "journal_entry_id": str(posting.entry_id),
                "debits": str(posting.debits),
                "credits": str(posting.credits),
            },
        )
    return receipt_dict(row)


# ═══════════════════════════════════════════════════════════════════════════
# 2 · RELEASE — a TERMINAL outcome earns the fee. Ask for more does not.
# ═══════════════════════════════════════════════════════════════════════════
def release_counter_receipt(
    *,
    source_type: str,
    source_id: Any,
    outcome: str,
    fee_lines: Any,
    released_at: datetime,
    released_by_id: Any = None,
    actor: Any = None,
) -> dict[str, Any] | None:
    """Turn the held liability into revenue. **Approval and refusal, identically.**

    `outcome` is `approved` or `refused` and decides only the STATE the row
    lands in — `applied` or `earned`. The posting is the same pair either way,
    which is the ruling read plainly: approval APPLIES the credit to the
    application fee and refusal EARNS it because the fee is non-refundable, and
    in double entry those are one act.

    `fee_lines` is the quote, as the source module knows it — an iterable of
    `{"charge_code", "charge_code_id", "amount"}` for every UNWAIVED line, in
    line order. Payments resolves each code to the tenant's own revenue account
    and never picks one.

    **Worked, the drawn case:** one line `CC-REQFEE` $25.00, receipt $25.00,
    refused → **DR `2400` $25.0000 · CR the code's revenue account $25.0000**,
    state `earned`, `held_remaining` $0.0000.

    **Worked, over-collection:** one line `CC-REQFEE` $25.00, receipt $30.00 →
    **$25.0000 released** and **$5.0000 stays a liability in `2400`**. `4xxx` is
    money EARNED and `2400` is money HELD; $5.00 above an application fee is not
    an application fee, and earning it would be the mirror of the defect p085
    warns about.

    **Worked, part payment:** lines totalling $130.00, receipt $25.00, refused →
    **$25.0000 released**; the $105.00 was never collected and posts nowhere.

    ⚠ **A SECOND CALL POSTS NOTHING.** The row is already out of `held`, so this
    returns it unchanged — which is what makes a refuse-then-reopen-then-refuse
    safe, and what makes the ledger's own replay guard the second of two
    independent checks rather than the only one.

    ⚠ **IT NEVER BLOCKS THE OUTCOME.** Every refusal from the books is caught,
    recorded on `release_error` and returned; the caller's state change stands.
    A clerk who cannot refuse an application because a charge code is unmapped
    is a clerk stuck at a counter with a person in front of them.
    """
    # ⊕ `CR-191-BRC10` (PO 2026-10-23) — `paid_online`: a portal application
    # fee paid by card at submission is earned AT ONCE, because it is not
    # refunded (*"That is application fee it is not refunded"*). It lands in
    # `earned`, the state a refused counter fee lands in, through the SAME pair
    # — so a later approval or refusal finds the row out of `held` and posts
    # nothing (the second-call guard below).
    state = {
        "approved": cr_models.RECEIPT_APPLIED,
        "refused": cr_models.RECEIPT_EARNED,
        "paid_online": cr_models.RECEIPT_EARNED,
    }.get(str(outcome))
    if state is None:
        raise PaymentRuleError(
            f"{outcome!r} is not a terminal outcome. The liability is released by APPROVAL, "
            "by REFUSAL and by a portal fee PAID ONLINE, and by nothing else — ask-for-more "
            "leaves the request open and the money exactly where collection put it, posting "
            "nothing (PO rulings 2026-09-15, 2026-10-23).",
            br_ref="BR-PAY-1140",
        )

    with transaction.atomic():
        row = (
            cr_models.CounterReceipt.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), source_type=source_type, source_id=source_id)
            .first()
        )
        if row is None:
            # No money was taken at the counter. Nothing to release, and this is
            # the ordinary case for an application that pays nothing.
            return None
        if row.state != cr_models.RECEIPT_HELD:
            return receipt_dict(row)

        targets, error = _revenue_targets(row, fee_lines)
        if error is not None:
            row.state = state
            row.released_at = released_at
            row.released_by_id = released_by_id
            row.earned_amount = ZERO.quantize(AMOUNT_QUANTUM)
            row.release_error = error
            row.save(
                update_fields=[
                    "state",
                    "released_at",
                    "released_by",
                    "earned_amount",
                    "release_error",
                    "updated_at",
                ]
            )
            core_audit.write_row(
                action=AUDIT_RELEASED,
                entity_type=AUDIT_ENTITY,
                entity_id=row.id,
                actor_user_id=released_by_id,
                before={"state": cr_models.RECEIPT_HELD},
                after={
                    "state": state,
                    "earned": "0.0000",
                    "held_remaining": str(row.amount),
                    "release_error": error,
                },
            )
            return receipt_dict(row)

        earned = sum((target["amount"] for target in targets), ZERO).quantize(AMOUNT_QUANTUM)
        posting = None
        posted_error = None
        if earned > ZERO:
            # ⚠ HARD-WON LAW 14. A SAVEPOINT, not a bare try/except: on
            # PostgreSQL a failed statement aborts the WHOLE transaction, so a
            # caught refusal without this nested atomic() would take the
            # caller's state change down with it at COMMIT — and the suite runs
            # on SQLite, which has no aborted state, so that version passes
            # everything and loses money in production. Do not simplify.
            try:
                with transaction.atomic():
                    posting = ledger_seam.post_counter_receipt_released(
                        receipt=row,
                        targets=targets,
                        entry_date=released_at.date(),
                        posted_at=released_at,
                        actor=actor,
                    )
            except (PaymentRuleError, DatabaseError) as refusal:
                posted_error = str(refusal)

        row.state = state
        row.released_at = released_at
        row.released_by_id = released_by_id
        row.earned_amount = ZERO.quantize(AMOUNT_QUANTUM) if posted_error else earned
        row.release_error = posted_error
        if posting is not None:
            row.release_entry_id = UUID(str(posting.entry_id))
            row.revenue_postings = [
                {
                    "ledger_account_id": str(target["ledger_account_id"]),
                    "charge_code": target["charge_code"],
                    "amount": str(target["amount"]),
                }
                for target in targets
            ]
        row.save(
            update_fields=[
                "state",
                "released_at",
                "released_by",
                "earned_amount",
                "revenue_postings",
                "release_entry_id",
                "release_error",
                "updated_at",
            ]
        )
        core_audit.write_row(
            action=AUDIT_RELEASED,
            entity_type=AUDIT_ENTITY,
            entity_id=row.id,
            actor_user_id=released_by_id,
            before={"state": cr_models.RECEIPT_HELD},
            after={
                "state": state,
                "earned": str(row.earned_amount),
                "held_remaining": str(_held_remaining(row)),
                "journal_entry_id": str(posting.entry_id) if posting else None,
                "release_error": posted_error,
            },
        )
    return receipt_dict(row)


def _revenue_targets(
    row: cr_models.CounterReceipt, fee_lines: Any
) -> tuple[list[dict[str, Any]], str | None]:
    """Split what was collected across the quote's lines, each at its OWN account.

    ⚠ **CAPPED AT THE QUOTE (decision log, 2026-09-15).** The lines are walked
    in order and each takes what it is owed until the cash runs out; anything
    left over when every line is satisfied is NOT released. `4xxx` is money
    earned and `2400` is money held — over-collection is held.

    ⚠ **ONE CREDIT LINE PER DISTINCT ACCOUNT, NOT PER FEE LINE.** Two lines
    pointing at `4600` make one $X credit, because a journal entry says where
    money went and not how many rows a quote had.

    Answers `(targets, None)` or `([], "<the sentence a person can act on>")`.
    A partial answer is never returned: if any unwaived line with money against
    it has no account, NOTHING posts, because posting half a release would leave
    a liability nobody could tell apart from a rounding difference.
    """
    collected = _money(row.amount, what="amount")
    lines = [
        line
        for line in (fee_lines or [])
        if _money(line.get("amount", ZERO), what="a fee line") > ZERO
    ]
    if not lines:
        return [], (
            f"receipt {row.receipt_no} of {row.amount} {row.currency} has no fee line to earn "
            "against — the quote is empty or every line was waived, so there is nothing for the "
            "money to be the fee FOR. The liability stays in customer credit balances until "
            "somebody says what it was for."
        )

    by_account: dict[str, dict[str, Any]] = {}
    remaining = collected
    for line in lines:
        if remaining <= ZERO:
            break
        owed = _money(line.get("amount", ZERO), what="a fee line")
        part = owed if owed <= remaining else remaining
        account_id = _revenue_account_id(line)
        if account_id is None:
            return [], (
                f"charge code {line.get('charge_code') or '(none)'!r} has no GL account on this "
                "tenant's charge-code catalogue, so there is no revenue account to earn "
                f"{part} {row.currency} into. Nothing is guessed and nothing is posted: the "
                "money stays in customer credit balances and is visible there. The fix is "
                "Settings → the charge code → GL account (BR-BIL-010)."
            )
        key = str(account_id)
        bucket = by_account.setdefault(
            key,
            {
                "ledger_account_id": account_id,
                "charge_code": line.get("charge_code"),
                "amount": ZERO,
            },
        )
        bucket["amount"] = (bucket["amount"] + part).quantize(AMOUNT_QUANTUM)
        remaining = (remaining - part).quantize(AMOUNT_QUANTUM)
    return list(by_account.values()), None


def _revenue_account_id(line: dict[str, Any]) -> Any:
    """`rating.charges.gl_account_id` for this line's code, or None.

    Two doors into the SAME column, because a service-request fee line carries
    the code as text and its `charge_code_id` only when the clerk picked from
    the catalogue:

      * `charge_code_id` → `rating.selectors.gl_account_id_for_charge`, the read
        billing already asks at issue;
      * else the code string → `rating.selectors.charge_by_code`, whose row
        carries `gl_account_id`.

    `None` is a REFUSAL the caller honours, never a value to substitute for —
    rating's own docstring says so, and a caller that turned it into a stamped
    account would post one code's revenue into another's bucket permanently.
    """
    charge_id = line.get("charge_code_id")
    if charge_id:
        read = _resolve(RATING_MODULE, CHARGE_GL_READ)
        if read is not None:
            found = read(charge_id)
            if found:
                return found
    code = _text(line.get("charge_code"), 60)
    if not code:
        return None
    by_code = _resolve(RATING_MODULE, CHARGE_BY_CODE_READ)
    if by_code is None:  # pragma: no cover - defensive
        return None
    row = by_code(code)
    return (row or {}).get("gl_account_id")


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE ATTACH — and it has no production caller today (DEF-PAY-5394)
# ═══════════════════════════════════════════════════════════════════════════
def attach_to_account(
    *,
    source_type: str,
    source_id: Any,
    account_id: Any,
    actor: Any = None,
    attached_at: datetime,
) -> dict[str, Any] | None:
    """Put the receipt on the account, as a `Payment`. The ruling's other half.

    PO: *"when it is approved you can attached it to account"*. The MONEY half
    of that sentence is `release_counter_receipt` above and is complete without
    an account; this is the RECORD-KEEPING half — the customer's new account
    showing the $25.00 they paid at the counter in its payment history.

    ⚠ **NOTHING CALLS THIS IN PRODUCTION AND `DEF-PAY-5394` SAYS SO.** Approval
    raises WORK; it opens no account, and `customers.Account` carries no link
    back to a service request, so at the moment of approval there is nothing to
    attach to. It is written now, with a test, because the alternative is that
    the account-opening lane discovers the requirement as a surprise — but it is
    reported as unwired rather than counted as built (hard-won law 2).

    ⚠ **THE PURPOSE IS `prepay`, AND IT IS ONE OF THE FOUR BR-PAY-012 ALREADY
    SIGNS — NOT A FIFTH.** Adding `fee` would be inventing a value on a signed
    rule, and `prepay` is what this money IS: the chart's own external-mapping
    note calls the matching account *"2340 Advance Customer Payment … money paid
    in advance by somebody who is becoming a customer"*, which is this case word
    for word.

    ⚠ **NO ALLOCATION AND NO SECOND LEDGER ENTRY.** The books are already right:
    the holding account was debited at collection and the revenue credited at
    release. Going through `record_payment` here would post the pair a second
    time. So this is a RECORD, not a re-posting — and the three tender columns
    copy across by name, `confirmation` taking `cheque_no` while `drawer_bank`
    and `cheque_date` take themselves.
    """
    with transaction.atomic():
        row = (
            cr_models.CounterReceipt.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), source_type=source_type, source_id=source_id)
            .first()
        )
        if row is None:
            return None
        if row.payment_id:
            return receipt_dict(row)
        if row.state != cr_models.RECEIPT_APPLIED:
            raise PaymentRuleError(
                f"receipt {row.receipt_no} is {row.state!r}. Only an APPROVED application's "
                "receipt attaches to an account: a refused one is earned and there is no "
                "account, and a held one has not been decided yet.",
                br_ref="BR-PAY-1140",
            )
        payments_models = import_module("apps.payments.models")
        payment = payments_models.Payment.objects.create(
            tenant_id=_tenant_id(),
            account_id=account_id,
            type=payments_models.PAYMENT_TYPE_PAYMENT,
            method=row.method,
            amount=row.amount,
            currency=row.currency,
            status=payments_models.PAYMENT_CLEARED,
            purpose=payments_models.PURPOSE_PREPAY,
            # DEF-CUS-6376 — the clerk's own reference first, then what the
            # capture step's tender detail held, then the slip.
            confirmation=(
                row.confirmation or row.cheque_no or row.card_auth_code or row.receipt_no
            ),
            # The slip number stays at the front: it is how this payment is
            # found again from the paper, and the clerk's memo follows it.
            memo=(
                f"Counter receipt {row.receipt_no} · {row.memo}"
                if row.memo
                else f"Counter receipt {row.receipt_no}"
            ),
            cheque_date=row.cheque_date,
            drawer_bank=row.drawer_bank,
            # BR-TEN-081 — the posting DAY as midnight in the utility's own
            # zone, exactly as `POST /accounts/{id}/payments` reads a bare date.
            posted_at=_posting_instant(row),
            cleared_at=row.taken_at,
            # ── CR-132-BRC07 · WHERE THIS MONEY CAME FROM ──────────────────
            # A COUNTER RECEIPT IS `entry` AND IT IS HARDCODED, unlike the
            # other three creation sites, because this one is not reachable
            # any other way: somebody stood at a counter and handed money to a
            # cashier, which is the definition of the word. There is no
            # caller-supplied source here to read.
            #
            # ⚠ It is therefore NEVER in the New World feed, which selects
            # `webhook` — counter money reaches a City's books through its
            # cashier system, which is the assumption the online-only ruling
            # of 2026-09-22 rests on and names.
            #
            # WRITE-ONCE (hard rule 4), OBSERVED, never derived.
            origin="entry",
            origin_is_derived=False,
        )
        row.payment_id = payment.id
        row.attached_at = attached_at
        row.save(update_fields=["payment_id", "attached_at", "updated_at"])
        core_audit.write_row(
            action=AUDIT_ATTACHED,
            entity_type=AUDIT_ENTITY,
            entity_id=row.id,
            actor_user_id=getattr(actor, "id", None),
            after={
                "account_id": str(account_id),
                "payment_id": str(payment.id),
                "amount": str(row.amount),
                "currency": row.currency,
            },
        )
    return receipt_dict(row)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-094-BRC01 lane H (the PO ruling of 2026-09-15 · blueprint `04
#         Accounts` p079 and p085 read as IMAGES at scale 2 · `apps/ledger/
#         chart.py` · hard rules 1, 2, 4, 5, 6, 7 · hard-won law 14)
# generated: 2026-09-15 by the CR-094-BRC01 counter-fee lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no page mounts `GET /counter-receipts` yet)
#         F✔ G✔ H=pending(🔒 HUMAN-REVIEW-PENDING)
# gates: ruff✔ black✔ · pytest tests/test_cr094_counter_receipt_posts.py, and
#         the transaction-sensitive cases re-run against a real PostgreSQL
#         (hard-won law 14)
# exceptions: `attach_to_account` has a test and no production caller —
#         `DEF-PAY-5394`
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────

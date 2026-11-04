# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the balance-forward stamp) · OQ-530 CLOSED
#           (PO 2026-08-27, the migrated opening balance is the first bill's
#           PREVIOUS BALANCE)   Screens: S30 · S31 step 6 · S32 · the bill
# Rules:    BR-BIL-035 (previous balance − payments received + this period =
#           total due) · BR-CUS-048 (opening balances are FOUR AGED BUCKETS) ·
#           BR-CUS-049 (dated at cutover) · CLAUDE.md rule 1 (tenant scoping) ·
#           rule 2 (money is a Decimal, never a float) · rule 4 (the stamp
#           lands on an immutable record) · B1 (no cross-module import)
# Tests:    06-backend/tests/test_oq530_opening_balance_on_the_first_bill.py
# Impacts:  apps/billing/issue._stamp_balance_forward (the only caller) ·
#           apps/customers/selectors.opening_position_for_account (the owner,
#           resolved BY NAME)
# ───────────────────────────────────────────────────────
"""billing → customers SEAM: *what did this account bring with it at cutover?*

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this figure lands in `previous_balance` on
an immutable bill and is what a customer is asked to pay (CLAUDE.md 🔒 + rule
4). AI-authored 2026-08-27 under the PO ruling of 2026-08-09; it has a row in
`12-governance/09-human-review-ledger.md`.

⚠ CORRECTED 2026-08-31 — THE PARAGRAPH BELOW IS HISTORY, NOT THE CURRENT STATE.
A glob in 10-scripts/gates/human_owned.txt DOES match this file now: the PO
ruled on 2026-08-31, having been shown all 62 unguarded files in five groups,
that groups one to four go on the watched list — "56 files" in their own words
— and this file is one of them. G7 checks it from that commit. The paragraph is
kept because WHY it went unguarded is worth knowing (DEF-2790: the check
written to catch exactly this looked for the wrong marker for three days), and
nothing below it should be read as describing today.

⚠ **NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS FILE**, so G7
does not read the markers above — MEASURED 2026-08-27, not assumed. **That is
the FOURTH recorded occurrence of this exact escape on a money path**, and the
guard list itself carries the first three in its own text: `issue.py` (*"the
file already carried HUMAN-REVIEW-PENDING and a ledger row and NO glob here
matched it, so G7 reported conform over an unguarded money path — hard-won law
1, in the guard list itself"*), `decisions.py` and `read_analysis.py`, each with
the same sentence. Three occurrences, one cause, stated there: *"this list is
maintained by hand and a new money file joins the CODE without joining the
LIST."*

Editing that list is a **process event** — its own header says the guarded set
must not drift with whoever is coding, and the two most recent additions were
made BY PO RULING (*"add it"*, *"Human confirmation means yu ask me questions"*)
rather than by the lane that wrote the file. So this line is **REPORTED for the
PO batch and never self-granted**, which is the posture `payments_seam.py`,
`posting_seam.py`, `delivery_seam.py` and `pending.py` all took from the same
position.

╔══════════════════════════════════════════════════════════════════════════╗
║  A MIGRATED OPENING BALANCE IS NOT AN INVOICE. THAT IS THE WHOLE DEFECT. ║
╚══════════════════════════════════════════════════════════════════════════╝

`issue._stamp_balance_forward` has written the balance-forward block since
DEF-116, and its `previous_balance` reads **open INVOICES only** — payments'
published set of `issued` and `paid` bills. A utility that migrates onto this
product brings its receivable with it: it lands in `account_opening_buckets`
(BR-CUS-048, four aged bands) with a balanced opening journal entry, and there
is no invoice anywhere. So a customer who arrived owing **$8,240.00** got a
first bill whose previous balance read `—`, and the product told them they were
square.

**PO, 2026-08-27, closing OQ-530 — verbatim:**

    "so when we run first bill; we have to take opening balance into account.
     you will generate first bill and against previous balance you will
     mention the opening balance."

────────────────────────────────────────────────────────────────────────────
WHY BILLING ASKS INSTEAD OF COMPUTING (B1, and it is not a style preference)
────────────────────────────────────────────────────────────────────────────
`account_opening_buckets` is CUSTOMERS' table. Billing owns no opening bucket
and must compute none — the same reason `payments_seam.prior_position_for_
account` asks payments for the allocated half rather than counting allocation
rows itself. So the read is resolved BY NAME at call time (`import_module`,
`getattr`, a `None` the caller handles), no `import apps.customers` binds the
two modules (B1, gate G6), and the contract is greppable from both sides.

────────────────────────────────────────────────────────────────────────────
AN UNREACHABLE SEAM REPORTS. IT NEVER ANSWERS ZERO.
────────────────────────────────────────────────────────────────────────────
`amount is None` means *nobody could ask*. `Decimal("0")` means *this account
brought nothing with it*, which is the ordinary case for every account that was
created in this product rather than migrated into it. The two are different
facts and only one of them is a claim about a customer's money: a `0.00`
written for an unreachable seam would tell a customer in arrears that they are
square, on a page that is immutable the moment it is written.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

from core.pagination import ListParams

#: The owning module and its published read, named once so the contract is
#: greppable from BOTH sides of the boundary — the discipline
#: `payments_seam.PRIOR_POSITION_READ` and `issue.GL_REVENUE_READ` already keep.
CUSTOMERS_MODULE = "customers"
OPENING_POSITION_READ = "opening_position_for_account"  # (account_id) -> Mapping

#: ── BR-BIL-025's TWO ACCOUNT FACTS (CR-052 task 12) ────────────────────────
#: The rule is *"the template resolves per ACCOUNT: account override → category
#: default → tenant fallback"* and `billing.templates_service.resolve_for` has
#: implemented all three legs since 2026-08-15. What it never had was the first
#: two INPUTS, and its own docstring says why: *"THE OVERRIDE IS AN ARGUMENT,
#: NOT A LOOKUP. BR-BIL-025 puts it on the ACCOUNT and the account is customers'
#: row; billing has one reviewed FK into customers (`invoices.account_id`) and
#: no column for this. So the caller supplies it."* This is that supply.
#:
#:     apps.customers.selectors.bill_template_election_for_account(account_id)
#:         -> {"template_override_id": uuid|None, "consumer_category": str|None}
#:         -> None when the account is not this tenant's
#:
#: Named as a STRING and resolved at call time for the module docstring's stated
#: reason (B1): no `import apps.customers` binds the two modules, and the
#: contract is greppable from both sides.
TEMPLATE_ELECTION_READ = "bill_template_election_for_account"

#: ── BR-NOT-029's DISCRETE MAILING ADDRESS (CR-053 task 13) ────────────
#: The print hand-over is a PDF set plus a manifest, and clause (a) of the rule
#: is what makes this a seam rather than a join: *"Every manifest address is
#: written from DISCRETE columns, never assembled from or split out of a single
#: field."* The columns are `customers.addresses`, which billing does not own
#: and has no FK into — `invoices.account_id` is its ONE reviewed FK into that
#: module (B1) — so the address is asked for by name, like the two facts above.
#:
#:     apps.customers.selectors.print_address_for_account(account_id)
#:         -> {"line1", "line2", "city", "state", "postal_code", "country",
#:             "source", "missing": [...]}
#:         -> {"unanswerable": True} when metering could not be asked
#:         -> None when the account is not this tenant's
#:
#: ⚠ **IT READ `mailing_address_for_account` UNTIL 2026-09-24 (`DEF-BIL-6373`).**
#: That read never falls back, while the delivery queue addresses a bill with
#: no mailing row to the SERVICE address (`DEF-PAY-6342` part 1) — so one bill
#: was queued to the premises and held out of the print file as *no address*.
#: The PO's ruling of 2026-09-23 (*"ensure you update correct address - mailing
#: or service"*) settles it: the print set follows the queue, and customers
#: answers both from ONE resolver (`_postal_recipient`).
#:
#: ⚠ **IT IS A READ AND THERE IS NO WRITING COUNTERPART, BY RULE.**
#: `BR-CUS-674` (PO 2026-08-31, verbatim *"we cannot make chnges until account
#: confirm it"*): an address changes when the account holder tells us and by no
#: other route, so nothing a print vendor ever says about where a customer lives
#: comes back through here. `G60` fails on any address write from a
#: notifications or vendor-return path, and the absence it guards is the reason
#: this constant has no sibling.
PRINT_ADDRESS_READ = "print_address_for_account"

#: ── THE SAME QUESTION, ASKED OF A WHOLE SELECTION AT ONCE (`DEF-BIL-5354`) ──
#: Screen 28 says *"404 will print · 8 held back"* before a clerk commits a
#: worker to an archive, and `BR-NOT-029` clause (b) makes an incomplete
#: postal address the reason a bill is held. Asked through the read above that
#: is two statements a bill; this is a few statements for the whole selection.
#:
#:     apps.customers.selectors.account_ids_without_print_address(account_ids=None)
#:         -> QuerySet of account ids
#:
#: ⚠ **IT IS COMPOSED, NOT ITERATED.** `print_set` puts it inside
#: `account_id__in=<this>` so the count is taken in the database. Since
#: `DEF-BIL-6373` it is no longer ONE lazy statement — the service-address leg
#: is metering's table, reached only through metering's read — but it is the
#: same handful of statements at 40,000 accounts as at 80 (`NFR-3`).
PRINT_ADDRESS_GAP_READ = "account_ids_without_print_address"


@dataclass(frozen=True)
class OpeningPosition:
    """What this account brought with it at cutover — or why nobody could ask.

    `amount` is the Σ of the account's four BR-CUS-048 bands at the amounts they
    were MIGRATED with. It is `None` when the seam could not be reached and
    `Decimal("0")` when the account has no migration; see the module docstring
    for why those must never be spelled the same way.

    `buckets` is how many band rows stood behind the figure — `0` on an account
    that was never migrated, and the number a reviewer can tie back to GT-16's
    four. `as_of` is BR-CUS-049's cutover date, carried so a stamped bill can
    always say *"aged as of when?"* without a join to a run that may be years
    old.
    """

    account_id: str
    amount: Decimal | None = None
    buckets: int = 0
    as_of: date | None = None
    currency: str | None = None
    problems: tuple[dict[str, Any], ...] = ()


def _resolve(module: str, attribute: str) -> Any:
    """The owning module's callable, or None while it has not published one.

    getattr at CALL time — the idiom `payments_seam.py`, `posting_seam.py`,
    `delivery_seam.py` and `gather.py` all use, so no import statement binds
    billing to customers' internals (B1) and nothing here needs re-wiring when
    the owner moves a function.
    """
    try:
        target = import_module(f"apps.{CUSTOMERS_MODULE}.{module}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _unwired(account_key: str) -> OpeningPosition:
    return OpeningPosition(
        account_id=account_key,
        problems=(
            {
                "code": "customers_opening_position_for_account_not_published",
                "br_ref": "BR-BIL-035 · BR-CUS-048",
                "detail": f"apps.{CUSTOMERS_MODULE}.selectors.{OPENING_POSITION_READ} is not "
                "published, so a migrated opening balance could not be read. The whole "
                "balance-forward section is withheld rather than printed short: an account "
                "that arrived owing money would otherwise be shown a previous balance of "
                "0.00, which tells a customer in arrears that they are square on a page "
                "that is immutable the moment it is written (PO 2026-08-27, OQ-530).",
            },
        ),
    )


def opening_position_for_account(account_id: Any) -> OpeningPosition:
    """BR-BIL-035's fourth source — the migrated receivable, asked for by name.

    ❄️ **Worked on GT-16's own account `A-12103`:** four bands `84.20 / 62.10 /
    0.00 / 121.00` sum to **267.30**, so its first bill reads
    **267.30 − 0.00 + <this period> = <total due>** where it used to read `—`.

    ⚠ **NOTHING HERE ROUNDS AND NOTHING HERE AGES.** The figure is a sum of
    already-migrated amounts; B4's rounding law is ❄️ FROZEN and a seam is not
    where one of its decisions is taken. The bands' AGE is `apps/customers/
    selectors.ageing_segments_for`'s answer and belongs on a collections screen,
    not on a bill.
    """
    account_key = str(account_id)
    read = _resolve("selectors", OPENING_POSITION_READ)
    if read is None:
        return _unwired(account_key)
    return _opening_position(account_key, read(account_id))


#: 🔒 DEF-BIL-8696 — the same read for a whole bill run.
OPENING_POSITIONS_READ = "opening_positions_for_accounts"


def opening_positions_for_accounts(account_ids: Any) -> dict[str, OpeningPosition] | None:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-8696` — `opening_position_for_account`
    for every bill of a run, asked BY NAME in one batch (Sign off asked it once
    per account: 40,000 statements). Every account asked about is a key, each
    answer read through the SAME `_opening_position` as the singular, so a
    migrated $267.30 reads $267.30 either way. None when customers does not
    publish the batch — the caller then asks per account, as before."""
    read = _resolve("selectors", OPENING_POSITIONS_READ)
    if read is None:
        return None
    asked = account_ids if hasattr(account_ids, "query") else [str(a) for a in account_ids]
    return {key: _opening_position(key, answer) for key, answer in read(asked).items()}


ACTIVITY_KEY_READ = "activity_key_for_accounts"


def activity_key_for_accounts(account_ids: Any) -> str | None:
    """`DEF-BIL-8696` — customers' key over these accounts' rows and opening
    buckets (`core.row_versions`), asked BY NAME. None — *cannot tell* — when
    customers does not publish it or the database cannot say."""
    read = _resolve("selectors", ACTIVITY_KEY_READ)
    if read is None:
        return None
    return read(account_ids if hasattr(account_ids, "query") else [str(a) for a in account_ids])


def _opening_position(account_key: str, answer: Any) -> OpeningPosition:
    """One account's answer from customers, checked and carried — the one
    statement both reads above share."""
    amount = answer.get("amount") if answer is not None else None
    if not isinstance(amount, Decimal):
        # The owner answered something that is not money. Refused rather than
        # coerced (CLAUDE.md rule 2) and reported rather than defaulted to
        # zero: "the read returned nothing usable" is not "the account owes
        # nothing", and the second is a claim about a customer's money.
        return OpeningPosition(
            account_id=account_key,
            problems=(
                {
                    "code": "opening_position_is_not_a_decimal",
                    "br_ref": "BR-BIL-035 · BR-CUS-048",
                    "detail": f"apps.{CUSTOMERS_MODULE}.selectors.{OPENING_POSITION_READ} "
                    f"answered {amount!r} where a Decimal amount belongs — money is never a "
                    "float and never cents (CLAUDE.md rule 2). Nothing was assumed; the "
                    "balance-forward section is absent rather than printed as zero.",
                },
            ),
        )
    return OpeningPosition(
        account_id=account_key,
        amount=amount,
        buckets=int(answer.get("buckets") or 0),
        as_of=answer.get("as_of"),
        currency=answer.get("currency"),
    )


@dataclass(frozen=True)
class TemplateElection:
    """BR-BIL-025's ACCOUNT half of the template chain — or why nobody could ask.

    `readable is False` means the question could not be put (customers publishes
    no read, or this account is not this tenant's). It is NOT the same as an
    account that states no override and whose category has no template: that
    account is `readable=True` with two `None`s, and BR-BIL-025 then resolves the
    tenant FALLBACK, which is the correct answer and the one every tenant with a
    single template already gets.

    The distinction decides what `issue_run` does. Unreadable → the RUN's own pin
    stands and the run says so on its result, which is exactly today's behaviour
    and moves no customer's document. Readable → the chain runs for this account.
    """

    account_id: str
    readable: bool = False
    template_override_id: Any = None
    consumer_category: str | None = None
    problem: dict[str, Any] | None = None


def template_election_for_account(account_id: Any) -> TemplateElection:
    """BR-BIL-025's *account override* and *consumer category*, asked for by name.

    HUMAN-OWNED · HUMAN-REVIEW-PENDING — it decides which LAYOUT is frozen onto
    an immutable bill (hard rule 4), and a reprint renders that version for ever
    (BR-BIL-026/033).

    ⚠ **IT DECIDES NOTHING.** The resolution ORDER is `templates_service
    .resolve_for`'s and stays there — one implementation of the ruled chain, not
    two. This seam carries two facts across the boundary and takes no precedence
    decision of its own, which is the same shape `gather._tariff_config_for`
    takes for BR-RAT-028's two thresholds (*"a projection — no precedence, none
    invented"*).

    An account customers cannot resolve comes back `readable=False` with its
    reason, and the caller keeps the run's pin rather than issuing a bill
    against a template nobody chose.
    """
    account_key = str(account_id)
    read = _resolve("selectors", TEMPLATE_ELECTION_READ)
    if read is None or account_id is None:
        return TemplateElection(
            account_id=account_key,
            problem={
                "code": "customers_bill_template_election_not_published",
                "br_ref": "BR-BIL-025",
                "detail": f"apps.{CUSTOMERS_MODULE}.selectors.{TEMPLATE_ELECTION_READ} is "
                "not published, so this account's template override and consumer "
                "category could not be read and the RUN's pin stands. That is the "
                "behaviour every bill in this product had before CR-052 task 12; it is "
                "reported rather than left silent, so a per-category template that is "
                "not being honoured is visible instead of invisible.",
            },
        )
    answer = read(account_id)
    if not isinstance(answer, dict):
        return TemplateElection(
            account_id=account_key,
            problem={
                "code": "customers_bill_template_election_unanswerable",
                "br_ref": "BR-BIL-025",
                "detail": "customers could not resolve this account, so BR-BIL-025's "
                "account override and consumer category are UNKNOWN — not absent. The "
                "run's pin stands; nothing is guessed.",
            },
        )
    return TemplateElection(
        account_id=account_key,
        readable=True,
        template_override_id=answer.get("template_override_id"),
        consumer_category=answer.get("consumer_category"),
    )


@dataclass(frozen=True)
class MailingAddress:
    """Where a bill is POSTED, in the discrete parts a mail house needs.

    `readable is False` means the question could not be put — customers
    publishes no read, or this account is not this tenant's. It is NOT the same
    as an account whose address is incomplete: that one is `readable=True` with
    `missing` naming the parts, and `BR-NOT-029` clause (b) then holds its bill
    OUT of the file. Collapsing the two would tell a clerk that a deployment
    problem and a customer's blank postcode are one thing.

    ⚠ **THE NAME SAYS *MAILING* AND SINCE 2026-09-24 IT IS THE POSTAL
    ADDRESS (`DEF-BIL-6373`)** — the account's mailing row, else the service
    address its premises gives, exactly as the delivery queue addresses the
    same bill. `source` says which (`mailing_address` · `service_address`), so
    a held bill's sentence can send the clerk to the right record. The class
    keeps its name because it is still the fields of one envelope.

    ⚠ **`line2` AND `country` ARE OFTEN None AND THAT IS A SCHEMA FACT, NOT A
    BUG HERE** — `DEF-2847`: both are NULL on every mailing row written before
    `customers 0039`, and a premises holds no country. On a service address
    `line2` is the unit's LABEL (hard rule 8). They are carried as fields so the
    manifest's ruled column list is written from named values rather than from
    blanks somebody has to remember to leave blank.

    ⚠ **NOTHING HERE COMPOSES A STRING.** A single-line address cannot be
    CASS-certified, cannot be barcoded, and is mailed at a higher rate or not at
    all (`BR-NOT-029`), which is the whole reason the parts travel apart.
    """

    account_id: str
    readable: bool = False
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    #: `mailing_address` or `service_address` — the delivery snapshot's words.
    source: str | None = None
    #: The parts `BR-NOT-029` clause (b) requires and this address cannot
    #: supply. EMPTY is the only value that lets a bill into the print file.
    missing: tuple[str, ...] = ()
    problem: dict[str, Any] | None = None

    @property
    def is_complete(self) -> bool:
        """Ready to mail: the question was answerable and nothing is missing."""
        return self.readable and not self.missing


def print_address_for_account(account_id: Any) -> MailingAddress:
    """`BR-NOT-029`'s address fields for one bill, asked for BY NAME (B1).

    The mailing row, else the service address (`DEF-BIL-6373`) — see
    `PRINT_ADDRESS_READ`. Named `mailing_address_for_account` until 2026-09-24.

    ⚠ **READ-ONLY, AND THE ONE DIRECTION IS THE RULE** (`BR-CUS-674`, PO
    2026-08-31). We hand a mailer discrete fields; the mailer mails. Nothing it
    answers about where that customer now lives reaches `premises`,
    `service_requests` or any account, and there is no function in this module
    that could carry one back.

    ⚠ **IT TAKES NO DECISION ABOUT COMPLETENESS AND MERELY REPORTS ONE.**
    Which parts are mandatory is `BR-NOT-029` clause (b) — city, state, postal
    code — and the owning module names them
    (`selectors.REQUIRED_ADDRESS_PARTS`), so the list is not re-declared here
    where it would drift. This seam carries the answer across the boundary and
    adds nothing, the same posture `template_election_for_account` takes above.

    An unpublished read or an account this tenant does not hold comes back
    `readable=False` with its reason, and the caller HOLDS the bill rather than
    printing an envelope with no address on it.
    """
    account_key = str(account_id)
    read = _resolve("selectors", PRINT_ADDRESS_READ)
    if read is None or account_id is None:
        return MailingAddress(
            account_id=account_key,
            problem={
                "code": "customers_mailing_address_not_published",
                "br_ref": "BR-NOT-029",
                # BR-NOT-029 clause (b), applied to the seam as well as to the
                # data. The sentence below reaches a clerk, so it names neither
                # the rule nor the module — see G28 and CLAUDE.md's DEF-1931.
                "detail": "this account's address could not be read at all, so the "
                "bill is held back rather than listed with its address columns empty. A "
                "line the mail house cannot deliver is worse than a bill you are told "
                "about.",
            },
        )
    answer = read(account_id)
    if not isinstance(answer, dict):
        return MailingAddress(
            account_id=account_key,
            problem={
                "code": "customers_mailing_address_unanswerable",
                "br_ref": "BR-NOT-029 · BR-TEN-003",
                "detail": "this account could not be looked up, so where its bill should "
                "be posted is unknown — which is not the same as having no address. "
                "Nothing is guessed and the bill is held back.",
            },
        )
    if answer.get("unanswerable"):
        # The account has no mailing row and metering could not be asked for
        # its premises: a fact about the PLATFORM, never an incomplete address
        # (`BR-BIL-036`), so it is held as UNREADABLE and says so.
        return MailingAddress(
            account_id=account_key,
            problem={
                "code": "customers_service_address_unanswerable",
                "br_ref": "BR-NOT-029 · BR-BIL-036",
                "detail": "this account has no mailing address and the address of the "
                "property it is at could not be read, so where its bill goes is unknown. "
                "Nothing is guessed and the bill is held back.",
            },
        )
    missing = answer.get("missing")
    return MailingAddress(
        account_id=account_key,
        readable=True,
        line1=answer.get("line1"),
        line2=answer.get("line2"),
        city=answer.get("city"),
        state=answer.get("state"),
        postal_code=answer.get("postal_code"),
        country=answer.get("country"),
        source=answer.get("source"),
        missing=tuple(str(part) for part in missing) if isinstance(missing, (list, tuple)) else (),
    )


#: ── `DEF-BIL-8283` · WHO THE BILL IS FOR, ASKED ONCE AT DRAFT ─────────────
#:
#:     apps.customers.selectors.bill_addressee_for_account(account_id)
#:         -> {"customer_name", "service": {parts} | None, "mailing": {parts} | None}
#:         -> None when the account is not this tenant's
BILL_ADDRESSEE_READ = "bill_addressee_for_account"


def _one_line(*parts: Any) -> str | None:
    """Parts joined as the line a customer reads — a blank part is DROPPED.

    `street, unit, city, ST 12345`. Nothing is filled in: a premises with a
    street and no city prints the street, and one with nothing prints nothing
    (the document then names the absence). The same shape as
    `gather._service_address`, so a cycle bill and a one-time bill print one
    address the same way.
    """

    def text(value: Any) -> str | None:
        return value.strip() or None if isinstance(value, str) else None

    *head, state, postal_code = parts
    region = " ".join(p for p in (text(state), text(postal_code)) if p) or None
    joined = [p for p in (*(text(h) for h in head), region) if p]
    return ", ".join(joined) or None


def bill_addressee(account_id: Any) -> dict[str, Any]:
    """`DEF-BIL-8283` — the customer's name and both addresses, as bill text.

    Stage 6 stamps these into `bill_payload` for EVERY bill kind, frozen with
    the rest of the snapshot (BR-BIL-030): a customer renamed or re-addressed
    after issue does not reprint a bill already sent.

    Returns `{"customer_name", "po_number", "service_address", "unit_label",
    "mailing_address", "mailing_address_source"}`:

      * `service_address` is the premises' street, city, state and postal code
        — walked, never stored (hard rule 8) — WITHOUT the unit, because the
        document prints the unit on its own line directly below it (and
        `gather._service_address` has always stamped it that way).
      * `mailing_address` is the account's mailing row where it has one, else
        the SERVICE address WITH the unit (`street, Unit A, city, ST zip`) —
        B2 §2's *"an absent mailing row means same as service"*, and an
        envelope to a flat without its unit reaches the building and not the
        customer. `mailing_address_source` says which (`mailing_address` ·
        `service_address`, the delivery snapshot's own words).

    DEGRADES to `{}` when customers publishes no read: this supplies WORDS for
    a document, not a fact any money depends on, and the document then names
    each absence (the same posture as `tenancy_seam.bill_masthead`).
    """
    read = _resolve("selectors", BILL_ADDRESSEE_READ)
    if read is None or account_id in (None, ""):
        return {}
    answer = read(account_id)
    if not isinstance(answer, dict):
        return {}
    service = answer.get("service") if isinstance(answer.get("service"), dict) else None
    mailing = answer.get("mailing") if isinstance(answer.get("mailing"), dict) else None
    service_address = (
        _one_line(
            service.get("line1"),
            service.get("city"),
            service.get("state"),
            service.get("postal_code"),
        )
        if service
        else None
    )
    if mailing:
        mailing_address = _one_line(
            mailing.get("line1"),
            mailing.get("line2"),
            mailing.get("city"),
            mailing.get("state"),
            mailing.get("postal_code"),
        )
        country = mailing.get("country")
        if mailing_address and isinstance(country, str) and country.strip():
            mailing_address = f"{mailing_address}, {country.strip()}"
        source = "mailing_address" if mailing_address else None
    else:
        mailing_address, source = None, None
    if mailing_address is None and service:
        mailing_address = _one_line(
            service.get("line1"),
            service.get("unit_label"),
            service.get("city"),
            service.get("state"),
            service.get("postal_code"),
        )
        source = "service_address" if mailing_address else None
    name = answer.get("customer_name")
    unit_label = service.get("unit_label") if service else None
    po_number = answer.get("po_number")
    return {
        "customer_name": name.strip() or None if isinstance(name, str) else None,
        # `DEF-BIL-9787` — the account's PO, printed on its bills (display only).
        "po_number": po_number.strip() or None if isinstance(po_number, str) else None,
        "service_address": service_address,
        "unit_label": unit_label.strip() or None if isinstance(unit_label, str) else None,
        "mailing_address": mailing_address,
        "mailing_address_source": source,
    }


def account_ids_without_print_address(account_ids: Any = None) -> Any:
    """Accounts whose bill cannot be posted, as a queryset — or **None**.

    `account_ids` narrows the question to one page (`forecast_rows`). Named
    `account_ids_without_mailing_address` until 2026-09-24 (`DEF-BIL-6373`).

    `None` means the owning module has not published the read, which is NOT the
    same as *"every address is complete"*: the caller states the absence rather
    than forecasting a zero, because a screen that says *"0 held back"* when it
    could not ask has made a promise about somebody's post (hard-won law 2's
    mirror, and `BR-SHL-020`).
    """
    read = _resolve("selectors", PRINT_ADDRESS_GAP_READ)
    if read is None:
        return None
    return read() if account_ids is None else read(account_ids=list(account_ids))


#: `P2.12`/`P2.3` — customers' OWN published account search, resolved by name.
#: The register's `q` searches a bill number (billing's column) and the
#: customer (customers' columns), and `B1`/`BR-TEN-013` forbid billing joining
#: the second. The published read returns a LAZY queryset of account ids, so
#: composing it with `Q(account_id__in=...)` costs a nested subquery and no
#: round trip.
REGISTER_SEARCH_READ = "account_ids_matching_debtor_search"


def account_ids_matching_search(term: str) -> Any:
    """Account ids whose number or customer name matches `term` — or **None**.

    **`None` means customers publishes no such read on this deployment**, and
    it is NOT an empty result: a register that answered "no bills" because it
    could not ask would be telling a clerk their customer has never been
    billed. `billing.reporting.billing_register` narrows to the columns it has
    and REPORTS the narrowing by name (BR-REP-024).

    ⚠ **THE READ IS NAMED `..._debtor_search` AND IS NOT ONLY THE DEBTOR
    SCREEN'S.** It was published for the AR ageing's `q` (p035) and it answers
    exactly the register's question too — *account number or customer name*,
    the two legs, `icontains`, lazy end to end. Resolving it here rather than
    publishing a second, identical read is B14 rule 43's argument applied to a
    seam: two spellings of one search is how two screens start disagreeing
    about which customer matched.
    """
    read = _resolve("selectors", REGISTER_SEARCH_READ)
    if read is None:
        return None
    return read(term)


#: Customers' BATCHED primary-contact read. `DEF-2723` published it for the
#: accounts list; `CR-138-BRC07` `P4.1` put `/outstandings` on it; `P2.21` put
#: the AR ageing on it. The billing register is the fourth and last caller
#: that was still asking one name at a time.
REGISTER_NAMES_READ = "primary_contact_names_for"


def primary_contact_names_for(account_ids: Any) -> dict[str, str | None] | None:
    """A PAGE's customer names — ONE query — or **None** when unpublished.

    ⛔ **THE REGISTER RESOLVED THE SINGULAR ONCE PER ROW UNTIL `P2.12`.**
    Measured on PostgreSQL 16.13 over a 39,981-row register: a fifty-row page
    cost **56 statements**, fifty of which were this column, and the UNPAGED
    read before `P2.12` made one per bill — **39,981 round trips for one
    column**. It is the same defect `DEF-2723` closed on the accounts list and
    `P2.21` closed on the ageing, in its fourth home.

    `None` is not an empty map: the caller falls back to the singular read
    rather than emptying the Name column, because a column that silently went
    blank is worse than a slow one.
    """
    ids = list(account_ids)
    if not ids:
        return {}
    read = _resolve("selectors", REGISTER_NAMES_READ)
    if read is None:
        return None
    return {str(key): value for key, value in read(ids).items()}



# ══════════════════════════════════════════════════════════════════════════
# §05 SCREEN 25's TWO CROSS-MODULE TILES
# ══════════════════════════════════════════════════════════════════════════
# Both return `(value, reason_it_is_absent)` and never a substituted 0. A KPI
# tile showing `0` says *nobody*; a tile showing a dash with a line under it
# says *nobody could ask*, and on a screen about what customers pay every month
# those are not the same statement (BR-SHL-020, and hard-won law 2's mirror).


def account_count() -> tuple[int | None, str | None]:
    """*"218 enrolled **of 1,284 accounts**"* — the denominator, through customers.

    ⚠ **IT ASKS FOR A QUERYSET AND COUNTS IT IN SQL.** `account_list` builds a
    row per account with its ledger, ageing and premise reads attached; calling
    it to take a length would be a full materialisation of every account on the
    tenant to render one number, which at the top of the ICP (T5, 40,000
    accounts) is the shape `NFR-3` exists to forbid. `account_list_queryset` is
    the same read one layer down and is published for exactly this.
    """
    read = _resolve("selectors", "account_list_queryset")
    if read is None:
        return None, (
            f"apps.{CUSTOMERS_MODULE}.selectors.account_list_queryset is not published, so "
            "the number of accounts on this tenant could not be read. The tile states that "
            "rather than showing a total it could not check."
        )
    return int(read(ListParams()).count()), None


def level_pay_asks_waiting() -> tuple[int | None, str | None]:
    """*"ASKS WAITING — 6, from the portal"* — **NOT SERVED, AND THE REASON IS
    THE FINDING.**

    ⚠ **A LEVEL-PAY ASK IS NOT DISTINGUISHABLE FROM ANY OTHER SERVICE REQUEST
    IN THIS PRODUCT TODAY, AND IT NAMES NO ACCOUNT.** The portal's ask
    (`apps/portal/services._hardship_ask`) raises an ORDINARY service request —
    which is `BR-CWP-066` working exactly as ruled, *"never a request of a new
    kind"* — and the only thing marking it as a level-pay ask is the English
    sentence `HARDSHIP_ROUTE_WORDS["level_pay"]` inside `what_they_said`.
    `create_from_portal` *"links no account and changes none"* (`BR-CWP-026`),
    so there is no account id on the row either.

    **Counting them would mean matching a prose sentence**, which would make a
    KPI on a money screen depend on nobody ever editing a piece of copy — a
    figure that goes quietly wrong the day somebody improves the wording. So
    this answers null with its reason and the screen says so.

    ⚠ **AND THE MARKER IS NOT EVEN REACHABLE FROM HERE, WHICH IS THE HALF THIS
    DOCSTRING MISSED UNTIL 2026-09-15.** The sentence to match is built from
    `HARDSHIP_ASK_MARKER`, and that constant lives in
    `apps/portal/seams/customers_seam.py` — **`portal`'s file**. Billing may not
    import portal (B1, `G6`), so matching the prose is not a bad option billing
    is declining; it is an option billing does not have. Copying the constant
    would be two spellings of one sentence in two modules, which is the drift
    the original paragraph warned about, arriving by a different door.

    The durable fix is a FILTERABLE FACT on the request (a route or a kind
    column, and the account it is about), which is customers' to add.

    ⚠ **IT IS NOW `OQ-BIL-12359` AND FOR FOURTEEN DAYS IT WAS ONLY THIS
    PARAGRAPH.** This docstring said the fix was *"reported rather than reached
    for from here"* — and nothing was reported anywhere a register could count
    it. That is CLAUDE.md hard rule 4's own lesson, verbatim: *"a finding
    recorded only in the file you happen to be in is a finding nobody can
    count."* `DEF-BIL-5331` is the row; the question is the register's.
    """
    absent = _level_pay_asks_absent()
    return None, absent


#: ── §05 ENTRY 25.3's QUEUE — `Asks from the portal` ────────────────────────
#: The read CUSTOMERS would publish, named as a STRING and resolved at call
#: time for the module docstring's stated reason (B1): no `import
#: apps.customers` binds the two modules, and the contract is greppable from
#: both sides. The same discipline as `OPENING_POSITION_READ` above.
#:
#:     apps.customers.service_request_reads.level_pay_asks_page(
#:         limit: int, offset: int
#:     ) -> {"count": int,
#:           "rows": [{"reference":   "SR-26-0087",   # request_no, never the id
#:                     "asked_on":    "2026-11-08",   # ISO date
#:                     "account_id":  "<uuid>",       # what billing levels
#:                     "account_no":  "ACC-10519-C",  # what the screen prints
#:                     "customer_name": "Nguyen, T.",
#:                     "level_shown": "112.0000"}]}   # 4dp string, or None
#:
#: ⚠ **`level_shown` IS THE ONE FIELD THAT EXISTS NOWHERE TODAY**, in any
#: module. The other four are on the row or one walk away; this one was never
#: captured, because the portal's ask writes a sentence and a sentence has no
#: place to put a figure the product will later be held to. `OQ-BIL-12359`
#: asks where it is kept.
LEVEL_PAY_ASKS_READ = "level_pay_asks_page"

#: The module that would publish it. `service_request_reads` and not
#: `selectors`, because that is where customers already keeps every read of
#: this table (`list_queryset`, `list_row`, `kpi_strip`, `detail`).
LEVEL_PAY_ASKS_MODULE = "service_request_reads"


def _level_pay_asks_absent() -> str:
    """ONE sentence, read by the tile AND by the table.

    ⚠ **THEY SHARE IT SO THEY CANNOT DISAGREE.** A KPI saying *nobody could
    ask* above a table saying something else about the same rows is two answers
    to one question, and on a money screen the clerk believes whichever they
    read first.
    """
    return (
        "an ask to level payments is raised as an ordinary service request and carries no "
        "route, no kind and no account of its own, so the requests waiting to be put on a "
        "level cannot be told apart from every other request a customer has raised. The "
        "queue is withheld rather than filled with rows nobody checked."
    )


def level_pay_asks(*, limit: int, offset: int) -> tuple[dict[str, Any] | None, str | None]:
    """§05 entry 25.3's rows — or `(None, reason)` while nothing can serve them.

    ⚠ **AN UNREACHABLE SEAM REPORTS; IT NEVER ANSWERS AN EMPTY LIST.** This
    module docstring's own rule, one screen along. `[]` on this table says *six
    people asked and none of them qualifies*; `None` says *nobody could ask*.
    A clerk reading the first closes the tab, and the customers who asked hear
    nothing — which is the exact failure the drawing's own note names: *"a
    customer who asked online and heard nothing asks again by telephone."*

    ⚠ **IT IS PAGED AT THE SEAM AND NOT AFTER IT** (`NFR-3`). `limit`/`offset`
    travel to the owner so the queue can never become the unpaginated list four
    endpoints already ship by naming the old 3,000-connection ceiling as their
    excuse (`DEF-PAY-4221`). At the top of the ICP — T5, 40,000 accounts — a
    queue that materialises every open request to render fifty rows is the
    shape `NFR-3` exists to forbid.

    **WHY THIS IS NOT A STUB THAT RAISES.** The prime directive's
    `NotImplementedError("OQ-###")` is for a code path that would otherwise
    GUESS a value. Nothing here guesses: the question is *where does the fact
    live*, and until it is answered the honest behaviour is the one this file
    has taken on every other unreachable read since `OQ-530` — answer null,
    carry the reason, and let the screen say it in its own words. A raise would
    turn a screen a clerk can read into a 500 they cannot.
    """
    read = _resolve(LEVEL_PAY_ASKS_MODULE, LEVEL_PAY_ASKS_READ)
    if read is None:
        return None, _level_pay_asks_absent()
    # Reached only once customers publishes the read above. The shape is the
    # owner's to honour and is asserted by the hold-expiry test rather than
    # trusted here — `tests/test_s253_budget_asks.py::test_hold_expires`.
    page = read(limit=limit, offset=offset)
    return dict(page), None


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-530 CLOSED (12-governance/02-decision-log.md, 2026-08-27) +
#         BR-BIL-035 (04-docs/05-modules/07-billing/02-business-rules.md) +
#         BR-CUS-048/049 (03-customers) + B1 (no cross-module import) +
#         ❄️ B5 GT-16 (04-docs/02-decisions/05-golden-tests.md)
# generated: 2026-08-27 by the OQ-530 opening-balance lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a seam) E=deferred(no-frontend-half:
#         the figure lands in `bill_payload.previous_balance`, which the existing
#         renderer already prints — see the lane's report) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_oq530_opening_balance_on_the_first_bill.py —
#         the unwired seam and the not-a-Decimal answer were each driven RED
#         before being trusted green (hard-won law 7)
# exceptions: (0) NO GLOB IN human_owned.txt MATCHES THIS FILE, so G7 does not
#         read its markers — the FOURTH recorded occurrence of that escape on a
#         money path (issue.py, decisions.py and read_analysis.py carry the
#         first three in the guard list's own text). REPORTED for the PO batch,
#         never self-granted: editing that list is a process event.
#         (1) AN UNPUBLISHED READ WITHHOLDS THE WHOLE BLOCK rather than
#         stamping the invoice half alone — a previous balance short by the
#         migration is the defect this seam exists to close.
#         (2) THIS SEAM STATES THE GROSS MIGRATED FIGURE. What has been PAID
#         against it is `payments_seam`'s half, and the fact that this product
#         records no allocation against an opening bucket is OQ-570.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


#: `DEF-BIL-9787` — the account's PO number, for the one-time PREVIEW:
#:     apps.customers.selectors.account_po_number(account_id) -> str | None
ACCOUNT_PO_READ = "account_po_number"


def po_number_for(account_id: Any) -> str | None:
    """`DEF-BIL-9787` — the PO this account's bills quote, or None.

    Words on a document, never a money input: an unpublished read degrades to
    None, and the bill then simply prints no PO line (the same posture as
    `bill_addressee`)."""
    read = _resolve("selectors", ACCOUNT_PO_READ)
    if read is None or account_id in (None, ""):
        return None
    value = read(account_id)
    return value.strip() or None if isinstance(value, str) else None


#: `CR-185-BRC10` — a move-out's tie-back to the owner posts when its FINAL bill
#: issues (coordinator ruling 2026-10-14: *"the transfer must move only money
#: that is IN THE BOOKS"*):
#:     apps.customers.move_out_settlement.post_pending_balance_to_owner(
#:         account_id, *, invoice_id, entry_date, posted_at, actor) -> Mapping
BALANCE_TO_OWNER_CALL = "post_pending_balance_to_owner"


def post_pending_balance_to_owner(
    invoice: Any, *, issued_at: Any, actor: Any = None
) -> dict[str, Any]:
    """🔒 HUMAN-REVIEW-PENDING · `CR-185-BRC10` — ask customers to post the tie-back.

    Billing names the bill and the moment; customers owns the tie-back row and
    the figure, and the LEDGER writes the entry (hard rule 5). Billing writes
    nothing here and imports no customers or ledger internals (B1): the
    callable is resolved by name at call time.

    A FINAL bill only — a cycle bill on an open account has no tie-back, and
    asking would be a query for nothing. An unpublished call answers a named
    absence rather than raising: a bill is never refused for want of a
    tie-back (BR-BIL-055).
    """
    if getattr(invoice, "bill_type", None) != "final":
        return {"posted": False, "reason": "not_a_final_bill"}
    call = _resolve("move_out_settlement", BALANCE_TO_OWNER_CALL)
    if call is None:  # pragma: no cover - customers publishes it
        return {"posted": False, "reason": "customers_publishes_no_tie_back"}
    return dict(
        call(
            str(invoice.account_id),
            invoice_id=str(invoice.pk),
            entry_date=issued_at.date(),
            posted_at=issued_at,
            actor=actor,
        )
    )

# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-001 (premises list — asset/account counts) · US-MET-002 (units
#           list — occupancy DERIVED, meters cell) · US-MET-003 (guided add —
#           inline meter creation, default-plan reference) · US-MET-004 (bulk —
#           asset columns reference OR create) · US-MET-005 (routes/cycles
#           progress from committed reads)   Screens: S14, S15, S16, S26, S27
# Rules:    BR-MET-036 (occupancy derived from the active account) · BR-MET-037
#           (delete guards probe account/asset/read references) · BR-MET-043
#           (asset tagging from the unit side, BR-AST-028) · BR-MET-011
#           (progress derives from committed reads, never stored counters) ·
#           BR-MET-007/BR-CUS-013 (unit plan history is rating-owned)
# Tests:    06-backend/tests/test_us_met_001_002_lists.py (stubbed seams) ·
#           test_us_met_003_wizard.py · test_us_met_005_006_routes_cycles.py ·
#           test_cr047_per_record_load.py (CR-047 — `occupying_account_status_codes`)
# Impacts:  apps.assets (asset create/link/probe) · apps.customers (accounts —
#           W2 lane) · apps.rating (tariffs + unit_plan_assignments) ·
#           apps.tenancy (service catalog + enabled services, read path)
# ───────────────────────────────────────────────────────
"""metering → other-module SEAMS: every cross-module call this module makes.

B1/B8: metering NEVER touches another module's ORM. Everything it needs from a
neighbour is one of the documented callables below, resolved AT CALL TIME from
`apps.<module>.services` (or the owning module's `selectors` for pure reads —
B1 "cross-module data flows through the owning module's service/selector").
While a neighbour's function is not authored yet (concurrent/later waves) the
seam reports "not wired" and the caller takes the DOCUMENTED fallback; nothing
here guesses a business answer.

Documented contracts (the owning lanes implement these signatures):

  apps.assets.services.create_asset_for_unit(actor, payload) -> dict
  apps.assets.services.attach_existing_asset(actor, asset_no, unit_id, ...) -> dict
    BR-AST-028 premises-first creation: the unit wizard creates/links asset rows
    in the ONE registry (BR-MET-006/039/043). Authored by the assets lane in the
    same W1 packet — wired today.

  apps.assets.services.asset_reference_count(unit_id=...) -> int
  apps.assets.selectors.assets_on_unit(unit_id) -> list[dict]
    BR-MET-037 delete guard input + the S15 "Meters" cell (meter numbers with
    (sub)/(master) qualifiers).

  apps.customers.selectors.customer_exists(customer_id) -> bool
    CR-039 wave C task 12 / BR-MET-150: `premises_owners.customer_id` is the
    OPTIONAL *"link to the customer they already are"* (PO 2026-08-27). This
    module validates that id WITHOUT reading customers' ORM. WIRED — authored
    by the customers module in the same packet. A cross-tenant id answers
    False rather than raising, the same posture `account_or_404` takes.
    When it is unresolvable the id is accepted as given (skip-until-wired) and
    the database FK is still what refuses a genuinely dangling one, so the
    fallback cannot corrupt anything.

  apps.customers.selectors.occupying_status_codes() -> Iterable[str]
    CR-047 / BR-CUS-017 + BR-CUS-022: which account statuses TAKE a unit, so
    stage 3 can tell a draft row (lawful on an occupied unit, lawful with no
    start date) from a row being activated. NOT AUTHORED YET — the seam falls
    back to the customers module's own published constants and says in its
    docstring exactly what that fallback cannot see.

  apps.customers.services.active_account_for_unit(unit_id) -> dict | None
  apps.customers.services.account_reference_count(unit_id) -> int
    BR-MET-036 occupancy + BR-MET-037/047 guards. UNWIRED TODAY (W2): the
    customers module owns no tables yet, so it can hold no account — "no active
    account" is true BY CONSTRUCTION, not a guess (same posture as the tenancy
    currency-lock probe).

  apps.metering read-side (this module) — meter_reads is the W2 reads lane's
    table (r16 #4). `read_reference_count()` / `committed_read_count()` return
    0/None until it lands; a read cannot exist without the table, so 0 is
    true by construction and the S26/S27 progress figures render as null
    rather than a fabricated zero.

  apps.rating.services.record_unit_plan_assignment(...) -> dict | None
    BR-CUS-013 / BR-MET-041: unit_plan_assignments is RATING-owned (B2 r16 #6).
    UNWIRED (rating services are a stub) — the metering half of the assignment
    (units.rate_plan_id / plan_effective_from / plan_locked) still commits
    and the response reports `history_recorded: false`, never a silent gap.

  apps.tenancy.selectors.services_overview() / .number_series_row(series)
    BR-MET-003 (services ⊆ tenant-enabled) and the EP-TEN-08 series format.
    Owning-module SELECTOR reads — the sanctioned cross-module read path.
"""

from collections.abc import Callable
from importlib import import_module
from typing import Any
from core import batch_reads


def resolve(module: str, attribute: str, kind: str = "services") -> Callable[..., Any] | None:
    """The owning module's callable, or None while its lane has not landed."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    fn = getattr(target, attribute, None)
    return fn if callable(fn) else None


# ── work: the field app's capture credential (READ) ─────────────────────────
def field_captor_from_token(token: str, *, allow_expired: bool = False) -> tuple[Any, Any]:
    """`(actor, technician)` for a field app CAPTURE TOKEN — work's own
    `mobile.captor_from_token`, the one verifier the job door uses
    (`BR-WRK-059`). The reads door calls it so a route reading is recorded as
    its CAPTOR's, not the courier's who is signed in when it is sent
    (`DEF-FLD-10358`). Raises work's `AuthError` naming why
    (`work.mobile.capture_token_invalid` · `…_expired`)."""
    fn = resolve("work", "captor_from_token", "mobile")
    if fn is None:  # pragma: no cover — work is always installed
        raise RuntimeError("work.mobile.captor_from_token is not available")
    return fn(token, allow_expired=allow_expired)


def field_technician_of(actor: Any) -> Any | None:
    """The signed-in caller's `technicians` row, or None — work's own
    `mobile.technician_of`. The reads door names a finding's captor this way
    when the item carried no capture token (the web, older builds)."""
    fn = resolve("work", "technician_of", "mobile")
    return fn(actor) if fn is not None else None


def work_route_findings() -> Any:
    """Work's route-finding service (`apps.work.route_findings`), by name.

    `BR-WRK-067` (PO 2026-10-22): a finding a reader sends through THIS door
    is Work's to keep and to turn into a job, so the reads door hands the item
    over (`receive`) rather than storing it — Work writes its own table, and
    nothing here writes Work's. Returned as the module because the door needs
    its refusal type (`FindingRefused`) as well as its two functions."""
    return import_module("apps.work.route_findings")


def work_refused_items() -> Any:
    """Work's keeper of refused field items (`apps.work.refused_items`), by
    name — `CR-194-BRC10` (PO 2026-10-26, *"store on both"*). The reads door
    hands each refused item over (`keep`) and closes an earlier copy when its
    key is later stored (`close_applied`); Work writes its own table and
    nothing here writes Work's. Returned as the module for `DOOR_READS` and
    `mark_kept` as well as the two functions."""
    return import_module("apps.work.refused_items")


def work_job_template(template_id: Any) -> dict[str, Any] | None:
    """MQ-033 — the Work job TEMPLATE a read-format question's `raise_work`
    names, as `{id, name, template_no, published, service}`, or None. Work's
    own read (`route_findings.read_format_template`); metering never reads
    Work's tables. A hard import: Work is always installed, and a soft
    fallback would let a question name a job type that does not exist."""
    return import_module("apps.work.route_findings").read_format_template(template_id)


def work_raise_for_read_answer(actor: Any, **fields: Any) -> tuple[dict[str, Any], bool]:
    """MQ-033 — hand a matched answer to Work, which raises ONE job of the
    question's template through the route-finding raise path (`BR-WRK-067`'s
    `_convert`), idempotent on the key. Work writes its own rows; nothing in
    metering writes Work's."""
    return import_module("apps.work.route_findings").raise_for_read_answer(actor, **fields)


def work_unable_reason_counts(folded_codes: list[str]) -> dict[str, int]:
    """DEF-MET-10609 — casefolded can't-read code → JOB readings answered
    *Unable to read* with it, from Work's own count
    (`evidence.unable_reason_counts`). The other half of *used*: a reason a
    job reading names cannot be deleted. Metering never reads Work's tables. A
    hard import: Work is always installed, and a soft fallback answering 0
    would let a used reason be deleted."""
    return import_module("apps.work.evidence").unable_reason_counts(folded_codes)


# ── tenancy: the custom-field vocabulary a read question is typed in ────────
def custom_field_vocabulary() -> dict[str, Any]:
    """MQ-033 (PO 2026-10-24: *"this will be similar to custom fields"*) — the
    custom-field data types and the shape limits a read question is defined
    with, READ from tenancy's own module (`custom_fields.DATA_TYPES` is
    `CUSTOM_FIELD_DATA_TYPES`), never copied: a seventh custom-field type
    reaches read questions without an edit here."""
    from apps.tenancy import custom_fields

    return {
        "data_types": tuple(custom_fields.DATA_TYPES),
        "select_types": tuple(custom_fields.SELECT_TYPES),
        "key_re": custom_fields.KEY_RE,
        "derive_key": custom_fields.derive_key,
        "label_max": custom_fields.LABEL_MAX,
        "help_text_max": custom_fields.HELP_TEXT_MAX,
        "option_max": custom_fields.OPTION_MAX,
        "options_min": custom_fields.OPTIONS_MIN,
        "options_max": custom_fields.OPTIONS_MAX,
    }


# ── notifications (the ONE cross-module write B1 opens) ─────────────────────
def queue_document(**message: Any) -> Any:
    """`notifications.queue_document` — the only door to `outbound_messages`.

    `outbound_messages` is the one table B1 opens to cross-module writes (B2 r16
    #7), and this is what that exception means: the service resolves the
    recipient, honours the idempotency rule and audits — all of which a caller
    reaching for the ORM would skip. `apps/customers/seams.py` publishes the
    same seam for the same reason; metering needs it for `BR-MET-115`.

    ⚠ **Unwired ⇒ None ⇒ THE CALLER REPORTS THAT NOTHING WAS QUEUED.** It never
    reports a notification it did not queue — the same discipline that stops a
    toast saying *"customer notified"* when no row exists.
    """
    fn = resolve("notifications", "queue_document")
    return fn(**message) if fn is not None else None


def deliveries_for_source(source_type: str, source_id: Any) -> list[dict[str, Any]] | None:
    """`notifications.selectors.deliveries_for_source` — what was queued for ONE
    source record, every channel and copy (`CR-163-BRC10` items 26–27).

    `None` while unpublished, which the caller states as *could not ask* rather
    than *nothing was sent*: the Messages tab's whole defect was a table that
    never asked and said *Not sent* on every row for ever.
    """
    fn = resolve("notifications", "deliveries_for_source", kind="selectors")
    return None if fn is None else list(fn(source_type, source_id))


def message_recipient(*, channel: str, address: str | None, name: str | None) -> Any:
    """`notifications.services.Recipient` for a recipient the CALLER names — the
    co-applicant, who has no account for `queue_document` to resolve one from.
    `None` while unpublished; the caller then refuses rather than guessing."""
    cls = resolve("notifications", "Recipient")
    if cls is None:
        return None
    return cls(channel=channel, address=address, snapshot={"name": name} if name else None)


def template_pin(code: str) -> Any:
    """`notifications.services.TemplatePin` naming the CLASS a letter renders
    from — `queue_document` refuses a row that names neither a code nor a pin
    (US-NOT-001 §1), and resolves the version itself at queue time. `None`
    while unpublished."""
    cls = resolve("notifications", "TemplatePin")
    return None if cls is None else cls(code=code)


def connection_message_preview(
    *, template_code: str, category: str | None, language: str | None, context: dict[str, Any]
) -> dict[str, Any] | None:
    """`notifications.connection_events.preview_occasion` — one letter rendered
    for THIS build, nothing written. `None` while unpublished."""
    fn = resolve("notifications", "preview_occasion", kind="connection_events")
    if fn is None:
        return None
    return dict(
        fn(template_code=template_code, category=category, language=language, context=context)
    )


def request_co_applicant(request_id: Any) -> dict[str, Any] | None:
    """`customers.selectors.request_co_applicant` — contact only, or `None`."""
    fn = resolve("customers", "request_co_applicant", kind="selectors")
    return None if fn is None else fn(request_id)


def delivery_recipients(account_id: Any, *, channels: tuple[str, ...]) -> dict[str, Any] | None:
    """`customers.selectors.delivery_recipients_for_account` — WHO a message goes to.

    ⚠ **THE SAME READ `queue_document` USES, RESOLVED HERE FOR THE SAME ACCOUNT
    SO A SCREEN AND A QUEUE ROW CANNOT DISAGREE.** New Connect's step 7 draws a
    read-only *Who we are telling* block; if it read an address from anywhere
    else, a clerk could confirm an address no letter ever used and nothing in
    the product would report it.

    An owning-module SELECTOR read — the sanctioned cross-module read path.
    None while unpublished, and the caller reports that rather than inventing
    an address: BR-TEN-017's *"nobody could look"* is a different fact from
    *"they have no email"*.
    """
    read = resolve("customers", "delivery_recipients_for_account", kind="selectors")
    return None if read is None else dict(read(account_id, channels=tuple(channels)) or {})


def account_language(account_id: Any) -> str | None:
    """`customers.selectors.account_preferred_language` — what the owner STATED.

    ⊕ **2026-10-29 — EVERY MESSAGE NOW FOLLOWS THIS (PO option B, *"Question:
    which language should messages be sent in? - B"*), so the 2026-10-02
    narrowing below is the rule rather than an exception, and the 2026-09-23
    paragraph after it is HISTORY.** `notifications.queue_document` reads the
    account's language itself and asks for it first.

    ⊕ **AMENDED 2026-10-02 FOR NEW CONNECTION LETTERS ONLY (`DEF-CUS-9195`).**
    PO ruling of that day (decision log, *"SEVEN PO ANSWERS IN ONE MESSAGE"*,
    item 2): *"A with the English fallback. She asked for Spanish. Today her
    choice is saved but never used."* `connection_messages._letter_language`
    reads this to send a New Connection letter in the owner's language where the
    utility published wording in it. Every OTHER message keeps the paragraph
    below.

    ⚠ **NOT THE LANGUAGE A LETTER GOES IN — AMENDED 2026-09-23
    (`OQ-CUS-12619`, `DEF-NOT-6354`).** This docstring read *"one of
    `BR-BIL-025`'s three axes … a letter to a Spanish-preferring owner picks
    the Spanish variant only if somebody passes this"*, and `queue_on_commit`
    passed it. The PO then ruled, verbatim, *"(a) Portal only; emails in
    English."*: a message takes the utility's default language
    (`tenant_default_language` below) and the account's preference drives the
    customer portal alone. It is still read for the step-7 card, which shows
    the owner's stated preference beside their other contact facts.

    None means one of two things and the caller must keep them apart: the read
    is unpublished, or this account states no preference. Only one of them is
    worth reporting to a clerk.
    """
    read = resolve("customers", "account_preferred_language", kind="selectors")
    return None if read is None else read(account_id)


def connection_templates(*, search: str | None = None) -> tuple[dict[str, Any], ...] | None:
    """`notifications.connection_events.connection_templates` — the step-7 picker's rows.

    Resolved by name, like every other cross-module door here. None while
    unpublished, which a picker renders as *no wording yet* rather than as a
    broken screen.
    """
    read = resolve("notifications", "connection_templates", kind="connection_events")
    return None if read is None else tuple(read(search=search))


def close_service_request_if_field_work_done(actor: Any, source_ref: Any) -> dict[str, Any] | None:
    """B19 §12.3 — *"A request closes on its own when the job it created
    finishes."* Customers' own door, called BY NAME (CR-070 wave P).

    ⚠ **METERING WRITES NO `service_requests` ROW AND THIS IS WHY IT DOES NOT
    HAVE TO.** The acceptance of a field result is metering's act; deciding
    whether an APPLICATION is now finished is customers' judgment, and it needs
    facts metering does not hold (what state the request is in, whether every
    job it raised has been accepted). So metering hands over one reference and
    customers answers.

    Answers None while the door is unpublished, and a caller that gets None
    changes nothing — the request simply stays in fulfilment until somebody
    closes it by hand, which is `manual_close` and already exists.
    """
    fn = resolve("customers", "close_if_field_work_done", kind="service_request_service")
    return None if fn is None else fn(actor, source_ref)


def queue_refusals() -> tuple[type[BaseException], ...]:
    """`notifications.QueueWriteRefused` — the exception the queue raises when a
    caller asks for something the platform has no writer for.

    Resolved by name for the same reason the callable is: half a published
    interface is not an interface. `apps/customers/seams.py` publishes the same
    tuple. An empty tuple when unwired means `except tuple(...)` catches nothing,
    which is correct — there is no queue to refuse anything.
    """
    refused = resolve("notifications", "QueueWriteRefused", kind="services")
    return (refused,) if isinstance(refused, type) else ()


def one_time_charge_door() -> Any:
    """`billing.one_time.create` — the door to a SINGLE-CODE one-time charge.

    ⚠ **THIS DOCSTRING SAID THIS DOOR *"CANNOT EXPRESS"* A BUILD'S QUOTE UNTIL
    2026-09-16, AND THAT IS NO LONGER TRUE OF THE MODULE — ONLY OF THIS
    FUNCTION.** It read: *"PUBLISHED SO THAT ITS LIMIT IS VISIBLE, NOT BECAUSE
    IT FITS … The New Connect quote is four coded lines with quantities, and
    this door cannot express it."* `CR-109` widened billing's fee path to take
    coded LINES with counts, so the limit has a door now and it is
    `quote_bill_door()` below. **A stated absence outlives its subject faster
    than anything else in this repo (hard-won law 1), so it is corrected here
    rather than left to be inferred from the presence of its replacement.**

    `OneTimeRequest` still takes ONE `connection_charge_code` and still has no
    `amount`, no `description` and no `lines` member — BR-BIL-020 enforced as an
    absent field rather than a removable validation. That has not changed and
    must not: this is the door for a fee that is one code, and the multi-line
    door is a different function with its own shape.
    """
    module = import_module("apps.billing.one_time")
    return getattr(module, "create", None)


def quote_bill_door() -> Any:
    """`billing.fee_bill.raise_and_issue_quote_bill` — a QUOTE to a receivable.

    ⚠ **ADDED 2026-09-16 (`CR-109`), AND IT IS THE DOOR `OQ-379` SAID DID NOT
    EXIST.** A build's quote is coded lines with counts; this raises them as one
    `fee` invoice against one account and issues it in the same transaction, so
    the charge reaches `1200 Accounts receivable` and the codes' own revenue
    accounts instead of being recorded on a `connections` row and posted by
    nothing.

    **BILLING PRICES IT, NOT METERING.** What crosses this seam is a list of
    `(charge_code, quantity)` and never a figure — BR-BIL-020, and CLAUDE.md
    hard rule 2's *"no figure is multiplied up anywhere but the server"* means
    the server that owns the price list. Metering counts the build; billing
    prices it.

    Unwired ⇒ None ⇒ the caller REPORTS that nothing was posted and does not
    claim a charge it did not raise, which is `queue_document`'s discipline on
    a money path.
    """
    module = import_module("apps.billing.fee_bill")
    return getattr(module, "raise_and_issue_quote_bill", None)


def quote_preview_door() -> Any:
    """`billing.fee_bill.price_quote_preview` — a quote PRICED FOR A SCREEN.

    ⚠ **`quote_bill_door()` ABOVE CANNOT ANSWER THIS QUESTION AND THAT IS WHY
    THERE ARE TWO (`DEF-CUS-6115`).** That door RAISES a receivable: it needs an
    account to bill and it writes an invoice. New Connect step 6 needs the same
    arithmetic over the same lines **before anything exists** — `BR-MET-112`,
    *nothing is written until step 8* — so the clerk can read what the build
    will cost while they can still change it. Six builds were committed in the
    acceptance walk without a figure ever appearing on that screen.

    **BILLING STILL PRICES IT.** What crosses this seam is `(charge_code,
    quantity, basis)` and never a figure, exactly as the raising door's own
    note says. Metering counts the build; billing owns the price list.

    Unwired ⇒ None ⇒ the caller REPORTS that nothing could be priced, and the
    screen states an absence rather than a `$0.00` — which is `_money`'s rule on
    the build record's tiles, one screen over.
    """
    module = import_module("apps.billing.fee_bill")
    return getattr(module, "price_quote_preview", None)


def quote_pricing_refusals() -> tuple[type[BaseException], ...]:
    """`billing.BillingRuleError` — what the pricing doors raise when a charge
    code cannot be priced.

    Resolved by name for `queue_refusals`' reason, which this file already
    states: **half a published interface is not an interface.** A caller that
    caught bare `Exception` around a money door would swallow a tenant-scoping
    failure and a programming error along with the one refusal it means to
    report, and an empty tuple means `except tuple(...)` catches nothing —
    correct, because with billing unpublished there is no pricing to refuse.

    ⚠ **IT IS CAUGHT ONLY ON THE PREVIEW PATH, AND THE RAISING PATH HAS ITS
    OWN ANSWER.** `commit_new_connect` catches billing's refusal BY CLASS and
    re-raises it as a refusal carrying the charges step's id (`DEF-MET-6110`,
    another lane, the same day) — never as a 500 and never as a catch-all. This
    seam is the PREVIEW's half: the same question asked before the press, so the
    clerk changes the code instead of losing the build to it.
    """
    module = import_module("apps.billing.exceptions")
    refused = getattr(module, "BillingRuleError", None)
    return (refused,) if isinstance(refused, type) else ()


def quoted_charge_shape() -> Any:
    """`billing.fee_bill.QuotedCharge` — the class the door above takes.

    Resolved by name for `queue_refusals`' reason: half a published interface is
    not an interface. Metering constructs these; it never constructs a figure.
    """
    module = import_module("apps.billing.fee_bill")
    return getattr(module, "QuotedCharge", None)


class QuoteRefusalUnavailable(Exception):
    """**NEVER RAISED.** What `quote_refusal_class()` answers while billing is
    unpublished, so an `except` clause always names a real class.

    ⚠ **IT IS NOT A CHECK THAT CANNOT FIRE (CLAUDE.md law 7's second shape) —
    IT IS THE OTHER HALF OF AN ABSENCE THAT ALREADY EXISTS.** With billing
    unpublished, `quote_bill_door()` answers `None`, `_post_connection_quote`
    takes its `billing_quote_door_unpublished` branch and **nothing is called
    that could refuse**. So there is no refusal to catch, and a class that is
    never raised is the accurate statement of that — not a guard that quietly
    stopped working.
    """


def quote_refusal_class() -> type[BaseException]:
    """`billing.exceptions.BillingRuleError` — WHAT the quote door refuses with.

    ⚠ **A CLASS CROSSES THIS SEAM, NOT A CALL, AND THAT IS THE POINT
    (`DEF-MET-6110`).** Billing's rule refusals are deliberately NOT catalogue
    exceptions — `apps/billing/exceptions.py` says why: a stage running over
    thousands of accounts is not answering a request. **The New Connect commit
    IS answering a request**, and until 2026-09-21 it let those refusals leave
    as `SYS-INTERNAL`: a clerk who picked `TAP` out of the product's own picker
    pressed *Create connection* after thirty-three acts and read *"Something
    went wrong on our side."*

    Resolved by name for the same reason every other door here is: metering
    must not import billing at module scope, and a caller that hard-coded the
    class would break the day billing is not installed rather than falling back
    to the absence `quote_bill_door()` already reports.

    **Never `None`** — see `QuoteRefusalUnavailable`. An `except` clause needs a
    class, and a caller writing `except (x or Fallback)` would be the awkward
    half of this decision living at every call site instead of here.
    """
    module = import_module("apps.billing.exceptions")
    refusal = getattr(module, "BillingRuleError", None)
    if isinstance(refusal, type) and issubclass(refusal, BaseException):
        return refusal
    return QuoteRefusalUnavailable


def request_quote_lines(request_id: Any) -> list[dict[str, Any]]:
    """Customers' own read of a service request's UNWAIVED, unraised quote lines.

    Metering holds the build and customers holds the application that priced it;
    the link is `connections.service_request`. This is the read that turns that
    link into the lines a bill is made of, and it is customers' judgment which
    lines still count — a waived line and an already-invoiced one are both
    excluded there, not here, so the three readers of that table cannot drift.

    Empty list while the door is unpublished, which a caller reports as *no
    quote* rather than as *no charge*.
    """
    fn = resolve("customers", "quote_lines_for_request", kind="service_request_service")
    return [] if fn is None else list(fn(request_id))


def carry_request_custom_answers(actor: Any, request_id: Any, *, premises_id: Any) -> None:
    """`DEF-CUS-9211` — customers' own copy of a service request's custom-field
    answers onto the premises a build raised from that request now stands on.

    The answers live on the REQUEST, which is customers'; customers judges which
    still count and writes the premises back through `update_premises` (this
    module's own door), so no table is written across the boundary. A no-op
    while the door is unpublished: the answers stay on the request, which is
    where they were.
    """
    fn = resolve("customers", "carry_into_created", kind="request_custom_fields")
    if fn is not None and request_id and premises_id:
        fn(actor, request_id, premises_id=premises_id)


def mark_request_quote_invoiced(actor: Any, request_id: Any, *, invoice_ref: str) -> int:
    """Customers' own write stamping `invoice_ref` on the lines just raised.

    ⚠ **METERING WRITES NO `service_request_fees` ROW AND THIS IS WHY IT DOES
    NOT HAVE TO** — `close_service_request_if_field_work_done`'s reasoning,
    applied to money. Cross-module writes are forbidden (B2 §2); the owning
    module scopes the tenant, takes the lock and writes the audit row.

    Returns how many lines were stamped, so a caller states a number it was
    given rather than one it assumed. 0 while the door is unpublished.
    """
    fn = resolve("customers", "mark_quote_lines_invoiced", kind="service_request_service")
    return 0 if fn is None else int(fn(actor, request_id, invoice_ref=invoice_ref))


def payer_is_billable(account_id: Any) -> bool | None:
    """Is this account one BR-CUS-055 lets anybody bill? `None` = nobody can say.

    ⚠ **ADDED 2026-09-16 (`DEF-MET-5468`) SO THAT A BUILD IS NOT THROWN AWAY BY
    ITS PAYER.** `commit_connection` creates the premises, the units, the
    meters, the plan assignments, the owner's account and the work orders in ONE
    transaction, and then raises the quote. Billing refuses a pending-activation
    or closed account — correctly, BR-CUS-055 — by raising, and a raise at that
    point poisons the whole PostgreSQL transaction (hard-won law 14) with a
    message written for billing rather than for this clerk. So it is ASKED
    here, before the door, and reported as a coded absence.

    ⚠ **THIS DOCSTRING WENT ON TO SAY *"The build is not wrong; only the charge
    cannot be raised"* UNTIL 2026-09-28, AND THAT HALF IS SUPERSEDED BY
    `BR-MET-1187`** (PO: *"we create entries in books"*, *"do it at creation
    once submitted"*). An unbillable payer now REFUSES the commit — the books
    entry is part of the same act — so the build is not created either. **The
    reason for asking here is untouched and is the whole of why this seam
    exists**: asking gives a clean refusal naming the account, where catching
    gives `InFailedSqlTransaction` on PostgreSQL and a green suite on SQLite.
    What moved is what the caller DOES with the answer, which was never this
    function's to decide.

    **CUSTOMERS OWNS THE ANSWER AND IT IS NOT RESTATED.** `billable_accounts()`
    is BR-CUS-055's class set as a queryset and is the identical read billing's
    `single._unit_less_scope` makes; asking it here is a second READER, never a
    second statement. Metering does not know what "billable" means and must not
    learn.

    `None` while customers has not published it — the caller reports that
    nothing was posted rather than guessing a class it cannot see.
    """
    fn = resolve("customers", "billable_accounts", kind="selectors")
    if fn is None:
        return None
    return fn().filter(pk=account_id).exists()


# ════════════════════════════════════════════════════════════════════════════
# payments — THE MONEY A CLERK TAKES AT THE COUNTER WHEN A BUILD IS CREATED
# `BR-MET-1187` (PO 2026-09-28: *"we create entries in books"*, *"do it at
# creation once submitted"*), `CR-150-BRC09` task `B1`
# ════════════════════════════════════════════════════════════════════════════
#
# ⚠ **FOUR DOORS AND NOT ONE, BECAUSE THE RULE IS IN THREE DIFFERENT MODULES.**
# Recording a counter payment at a build's commit is *which till* (payments'
# `counters`), *what shape the instruction is* (payments' `allocation`) and
# *the write itself* (payments' `services`). Folding them into one metering
# helper would put three of payments' rules in this file, which is B2 §2's ban
# read the other way round: the neighbour owns the rule AND the vocabulary.
#
# ⚠ **NOTHING HERE IS A SECOND STATEMENT OF A PAYMENTS RULE.** Each function
# resolves the owner's own callable by name and hands its answer back
# unchanged. Metering decides *that* a payment was taken and *against which
# bill*; payments decides what a tender is, whether a till is open, how the
# money is allocated and what the books record.


def counter_till_for_tender(actor: Any, method_code: str | None) -> dict[str, Any]:
    """Which till this money is taken into, or why it cannot be taken at all.

        apps.payments.counters.assert_till_open_for_tender(actor, code)

    **PO ruling 2026-09-23 §3.4, verbatim:** *"(a) Refuse it. \\"Start your
    counter first.\\" One press, then take the money. It is the only option
    where every cash dollar belongs to somebody"*. Cash, cheques and money
    orders pass through a person's hands and belong to a drawer that gets
    counted; `ach`, `card`, `wire` and `lockbox` never reach a counter and
    bank under the day's system till.

    ⚠ **THE TILL IS RETURNED AND NOT DISCARDED, WHICH IS `DEF-PAY-6226`'s WHOLE
    LESSON.** `payments/api.py` called this same rule and threw its answer
    away, so the refusal worked, the task was marked DONE, and **no payment
    ever named the till it was taken at** — a clerk opened a counter at 08:55,
    took seventeen payments and closed an empty drawer at 17:30. One name on
    one line is the entire wiring (hard-won law 2). So this returns both
    halves and the caller stamps the id.

    Answers `{"till_id": <pk or None>, "refusal": <sentence or None>}`.
    `till_id` is `None` for the four tenders that never reach a drawer AND on a
    refusal; `refusal` carries payments' OWN sentence so metering raises its own
    catalogue message and never imports a payments exception — the posture
    `apps/customers/payments_seam.till_refusal` already takes at the other
    counter, so a clerk reads the same words at both.

    ⚠ **A `None` DOOR IS NOT A PASS.** With payments unpublished this answers a
    refusal rather than "no till needed", because the caller is about to take
    real money: *money that cannot be recorded must not be taken* is
    `record_counter_receipt`'s own rule, and the safe direction to be wrong in
    is refusing a build, which the clerk can re-enter.
    """
    fn = resolve("payments", "assert_till_open_for_tender", kind="counters")
    if fn is None:  # pragma: no cover - defensive
        return {
            "till_id": None,
            "refusal": (
                "payments is not published, so this money cannot be recorded. Nothing is "
                "taken that cannot be written down."
            ),
        }
    refusal_class = payment_refusal_class()
    try:
        till = fn(actor, method_code)
    except refusal_class as refused:
        return {"till_id": None, "refusal": str(refused)}
    return {"till_id": None if till is None else till.pk, "refusal": None}


#: ⚠ **THERE IS DELIBERATELY NO `tender_is_live()` HERE, AND THE ABSENCE IS
#: THE DECISION.** The obvious neighbour to ask is
#: `payments.counter_receipts.is_live_tender`, and it is the WRONG reader:
#: it runs a caller's word through `FEE_METHOD_TO_TENDER` first, which maps a
#: service request's `cheque` onto the tender `check`. Metering sending
#: `cheque` would therefore be told the tender is live and then refused by
#: `services._method`, which looks the raw code up in the tenant's own list —
#: two answers to *is this a tender*, one of them arriving after the invoice
#: exists. **`record_payment` refuses an unknown or DEACTIVATED code by name,
#: with a sentence written for a clerk, and that is the one implementation.**
#: A refusal there rolls the whole build back, which is exactly what
#: `BR-MET-1187` asks for: if the money cannot be recorded, the build is not
#: created. The codes are the tenant's own, served by `GET /payments`
#: `methods[]` — `cash`, `check`, `card`, `ach`, `wire`, `money_order` seeded
#: (`BR-PAY-026`) and extensible — so a screen offers that list and never a
#: hand-typed one.


def payment_door() -> Any:
    """`payments.services.record_payment` — ONE payment, all of it or none.

    `BR-PAY-022`'s field set, and the door every counter in the product
    already writes through: it takes the payment, allocates it, posts the
    balanced pair through the ledger posting service and writes its own audit
    rows, inside its own `transaction.atomic()` — which nests here as a
    SAVEPOINT rather than a second transaction, so `BR-MET-112`'s
    both-or-neither still holds over the whole build.

    ⚠ **`services` AND NOT `import_writer`.** The undecorated import writer
    exists because a deferred load runs in a worker carrying `_JobActor` — an
    id and no role. A build's commit is answered to a signed-in clerk under
    `AdminOrClerk`, so the ordinary service is the right door and its guards
    are guards we want.

    `None` while payments is unpublished — and the caller REFUSES the build
    rather than committing one with money it could not record.
    """
    module = import_module("apps.payments.services")
    return getattr(module, "record_payment", None)


def payment_entry_source() -> str | None:
    """`payments.idempotency.SOURCE_ENTRY` — the namespace this key lives in.

    **Hard rule 6, and `B2` DB-12's second row: `(tenant_id, webhook_key)` on
    `payments` is the one idempotency key a payment has.** Payments composes
    the string from a SOURCE and a REFERENCE (`"<source>|<reference>"`), and
    the source segment is what keeps namespaces apart — an `entry|…` key and a
    `webhook|…` key can never collide. A build's counter payment is a person
    pressing a button, which is `entry`, the same namespace the S22 form uses.

    ⚠ **RESOLVED AND NEVER SPELLED.** `inbound_payment_key` REFUSES a source it
    does not know, by name, precisely because *"a typo'd namespace is a key
    that will never match the row it was meant to dedupe against and the
    duplicate lands as a second payment"*. A literal `"entry"` here would be
    metering's copy of payments' vocabulary, and the day it moved, this path
    would silently stop deduping while every test went on passing.

    `None` while payments is unpublished — the caller refuses rather than
    recording money under a key it made up.
    """
    try:
        module = import_module("apps.payments.idempotency")
    except ImportError:  # pragma: no cover - defensive
        return None
    source = getattr(module, "SOURCE_ENTRY", None)
    return source if isinstance(source, str) else None


def payment_refusal_class() -> type[BaseException]:
    """`payments.exceptions.PaymentRuleError` — WHAT the door above refuses with.

    A CLASS crosses this seam and not a call, for `quote_refusal_class`'s
    reason word for word: metering must not import payments at module scope,
    and a caller that hard-coded the class would break the day payments is not
    installed rather than falling back to the absence `payment_door()` reports.

    **Never `None`** — an `except` clause needs a class, and
    `PaymentRefusalUnavailable` below is what it answers while payments is
    unpublished. That is not a check that cannot fire: with no door there is
    nothing to call and therefore nothing to refuse, which is the accurate
    statement of the absence rather than a guard that quietly stopped working.
    """
    try:
        module = import_module("apps.payments.exceptions")
    except ImportError:  # pragma: no cover - defensive
        return PaymentRefusalUnavailable
    refusal = getattr(module, "PaymentRuleError", None)
    if isinstance(refusal, type) and issubclass(refusal, BaseException):
        return refusal
    return PaymentRefusalUnavailable


class PaymentRefusalUnavailable(Exception):
    """**NEVER RAISED.** What `payment_refusal_class()` answers while payments
    is unpublished, so an `except` clause always names a real class. The twin
    of `QuoteRefusalUnavailable` above, and it exists for the same reason."""


def payment_against_one_bill(invoice_no: str) -> dict[str, Any] | None:
    """payments' own instruction for *this bill and no other*.

        apps.payments.allocation.ORDER_SPECIFIC + AllocationTargetLike

    ⚠ **OLDEST-FIRST IS THE WRONG DEFAULT HERE AND THAT IS THE WHOLE REASON
    THIS EXISTS.** `record_payment` defaults to `oldest_first`, which settles
    each open bill in turn. A build tagged to an account that ALREADY owes
    money would then take the developer's counter payment for the new
    connection and put it against last quarter's water bill — money applied to
    a debt nobody named, on a screen that says the connection charge was paid.
    The clerk took this money FOR THIS BUILD, so the instruction says so.

    `amount=None` is payments' `specific` instruction — *"this bill, up to
    whatever it owes"* — and anything the bill cannot absorb carries as an
    account credit and is REPORTED, never dropped (`BR-PAY-010`).

    `None` while payments is unpublished; the caller refuses rather than
    recording money under an instruction it composed itself.
    """
    try:
        allocation = import_module("apps.payments.allocation")
    except ImportError:  # pragma: no cover - defensive
        return None
    order = getattr(allocation, "ORDER_SPECIFIC", None)
    if not isinstance(order, str):  # pragma: no cover - defensive
        return None
    return {"order": order, "targets": (NamedBill(invoice_number=str(invoice_no)),)}


class NamedBill:
    """ONE bill a payment is aimed at — `payments.allocation.AllocationTargetLike`.

    A plain carrier, exactly as `payments/api.py::_Target` is: the allocator
    reads `invoice_number` and `amount` and nothing else, and that Protocol is
    the seam's published contract in `allocate_payment`'s own words (*"the
    argument names and shapes are that seam's published contract"*). Building
    it here rather than importing payments' private class is what keeps this
    module from binding to payments at import time; matching the Protocol
    rather than inventing a shape is what keeps it from being a second answer.
    """

    __slots__ = ("invoice_number", "amount")

    def __init__(self, *, invoice_number: str, amount: Any = None) -> None:
        self.invoice_number = invoice_number
        self.amount = amount


# ── tenancy (platform catalog + settings reads) ─────────────────────────────
def validate_custom_data(
    entity: str,
    submitted: Any,
    *,
    screen: str | None,
    existing: Any = None,
) -> dict[str, Any]:
    """The tenant's OWN field definitions, applied to a premises, unit or
    service point's `custom_data` (US-SHL-015; `CR-161-BRC10` W2,
    `DEF-MET-9226` / `DEF-MET-9227` / `DEF-MET-9173` / `DEF-MET-9172`).

    `apps.tenancy.services.validate_custom_data_for` is the ONE validator —
    unknown keys refused, types and options enforced, a required field binding
    only on the screen it is typed in on. No copy of it lives in metering.

    ⚠ **`screen` HAS NO DEFAULT, ON PURPOSE** — the customers seam's reason
    (`DEF-TEN-9157`): every door says which screen its form is (`"S16"` Add
    Premises, `"PREMISE_EDIT"`, `"NEW_CONNECTION_PREMISE"`, `"UNIT_ADD"`,
    `"UNIT_EDIT"`), and an import or a seed says `None`, of which nothing is
    required — so an import without the column is never blocked. `existing`
    makes it an EDIT and returns the merged blob.

    A HARD import rather than `resolve()`: a soft fallback here would silently
    accept whatever a client sent into a jsonb column (DEF-075's shape).
    """
    from apps.tenancy import services as tenancy_services

    return tenancy_services.validate_custom_data_for(
        entity, submitted, screen=screen, existing=existing
    )


def wizard_park_queryset(*, flow: str | None = None):
    """The parked wizard drafts for one flow, as a **LAZY QUERYSET**.

    ⚠ **METERING NEEDS ITS OWN DOOR, AND THAT IS NOT DUPLICATION.**
    `wizard_parks` is TENANCY-hosted and no module may import
    `apps.tenancy.models` (B1 / BR-TEN-013; G6 rule 4 refuses it). Customers
    already has this seam for the Move-ins, Move-outs, Transfers and Disconnects
    lists; the New connects list lives HERE, in metering, and a cross-module
    reach through `apps.customers.seams` would be metering depending on
    customers to reach tenancy — one more hop and one more module that has to
    stay still. Each module owns one read-only door onto the store, which is the
    `apps/work/seams/` shape (`CR-070` §2(a)) applied where it was already law.

    ⚠ **A QUERYSET AND NEVER A LIST (`NFR-3`, `DEF-SHL-5748`).** The New
    connects list pages a UNION of builds and drafts, and a `UNION` arm has to
    be a queryset: handed a list, the page would be sliced in Python after every
    parked draft in the tenant had been built — correct at three thousand
    accounts and thirteen times short at forty thousand.

    Nothing here re-implements a line of `wizard_parks.py`.
    """
    from apps.tenancy import wizard_parks

    return wizard_parks.parks_queryset(flow=flow)


def discard_wizard_park(actor: Any, park_id: Any) -> None:
    """Throw away the draft a finished build was being typed into.

    **`BR-SHL-048 (d)`, PO ruling 2026-09-21** — *"this is big problem - we
    cannot create two build - you can update the existing build"*. One piece of
    work is one row on the New connects tab, so the moment the last button
    finishes the build the draft that was holding its typing has nothing left
    to hold. Left behind it is a second row for one build, which is half of
    what the clerk saw on the acceptance walk.

    ⚠ **THIS CALLS TENANCY'S OWN SERVICE AND WRITES NOTHING ITSELF.** Cross-
    module writes are forbidden (B1/B8) and this is not one: `wizard_parks
    .discard` audits and deletes inside tenancy, which is the module that owns
    the table. The seam above takes the same posture on the read side, in its
    own words — *"Nothing here re-implements a line of `wizard_parks.py`."*
    ⚠ `customers.services._adopt_wizard_draft` reaches in and calls `.delete()`
    on the row itself; that is the shape NOT copied here.

    ⚠ **IT IS NOT A `try` AND MUST NOT BECOME ONE (CLAUDE.md hard-won law 14).**
    Every refusal `wizard_parks.discard` can raise — a missing id, a malformed
    id, another tenant's id — is a DOMAIN error raised before any statement
    fails, so nothing here poisons the caller's PostgreSQL transaction. The
    caller decides whether a missing draft should stop a build; see
    `commit_new_connect`, which decides that it must not.
    """
    from apps.tenancy import wizard_parks

    wizard_parks.discard(actor, park_id)


def service_catalog() -> list[dict[str, Any]]:
    """Every platform service with the tenant's enablement + UoM (BR-MET-003).

    ⚠ **THIS IS THE S8 SCREEN READ, AND AS OF DEF-1549 IT HAS NO CALLER LEFT IN
    `apps/`.** Measured on the test harness: **41 queries** on an empty tenant,
    and it grows by two more for every SERVICE POINT the tenant owns, because
    `services_overview()` asks `customers.active_account_count` once per active
    service. Both defects that ever came through this door — `DEF-324`
    (`enabled_service_codes`, 47 seconds of one provisioning request) and
    `DEF-1549` (`service_default_uom`, a gunicorn WORKER TIMEOUT on a twenty-row
    import) — were a caller wanting **one field** and paying for the screen.

    **So before you use it: are you DRAWING S8?** If not, the cheap read almost
    certainly already exists next to it in `apps.tenancy.selectors` —
    `enabled_service_codes()`, `service_default_uom()`, `service_default_uoms()`,
    `service_billed_uoms()`, `unmetered_service_codes()`. It is kept rather than
    deleted because it is a published seam and B16 §4.7 makes tenancy's screen
    payload metering's to read; it is not kept because anything needs it.
    """
    from apps.tenancy import selectors as tenancy_selectors

    return list(tenancy_selectors.services_overview())


def service_names_by_code() -> dict[str, str]:
    """`tenancy.selectors.service_names_by_code` — the utility's OWN word for
    each service code (`Water`, not `water`), for the high-consumption email
    (`CR-182-BRC10`). An owning-module SELECTOR read; `{}` while unpublished,
    which the email renders as a named absence rather than a code."""
    read = resolve("tenancy", "service_names_by_code", kind="selectors")
    return dict(read() or {}) if read is not None else {}


def custom_field_import_columns(entity: str) -> list[dict[str, Any]]:
    """CR-161-BRC10 W4 — the tenant's ACTIVE definitions for one record type, as
    `{key, label}` pairs in display order, for an importer that offers one
    column per field (the S28 reading upload). A read of tenancy's published
    registry; never its table."""
    from apps.tenancy import selectors as tenancy_selectors

    return [
        {"key": row["key"], "label": row["label"]}
        for row in tenancy_selectors.custom_field_registry(entity)
    ]


def enabled_service_codes() -> set[str]:
    """WHICH services this tenant sells — ONE query, not a whole screen payload.

    ⚠ DEF-324 (2026-08-19). This used to read `service_catalog()` and throw away
    everything but one boolean per row. `service_catalog()` is the S8 SCREEN
    read: ten catalog rows, each `select_related` across four FKs, each calling
    the rating seam for a rate-schedule count and the customers seam for an
    active-account count. **~150 queries and ~155 ms to answer a question one
    indexed query answers.** It is on the hot path of every premises, unit,
    meter, read and bill-line write (`create_premises`, `_create_unit_inner`,
    `create_asset`, the importers, the sample-data plant), so provisioning a new
    tenant called it **304 times and spent 47 of its 118 profiled seconds
    here** — 40% of the whole request, in a read-only lookup.

    `apps.tenancy.selectors.enabled_service_codes()` is the same question with
    the same answer and has been published since 2026-08-11 for the ledger. It
    is now the single definition; see its docstring for the `service__active`
    clause that makes the two agree exactly.

    Still a `set`: every caller does `code in enabled_service_codes()`, and the
    tuple the selector returns is ordered for a screen this one never draws.
    """
    from apps.tenancy import selectors as tenancy_selectors

    return set(tenancy_selectors.enabled_service_codes())


def enabled_service_codes_ordered() -> tuple[str, ...]:
    """The SAME enabled set, in catalog seed order — for the S64 panels, which
    draw one per enabled service and must draw them in the order every other
    service list in the product uses (CR-038 A1)."""
    from apps.tenancy import selectors as tenancy_selectors

    return tuple(tenancy_selectors.enabled_service_codes())


def unmetered_service_codes() -> frozenset[str]:
    """WHICH of this tenant's services are NOT MEASURED BY DESIGN — BR-RAT-081.

    `apps.tenancy.selectors.unmetered_service_codes()`, wrapped for the DEF-324
    reason every read in this block is wrapped: metering holds the service CODE
    and B1 forbids it reaching into tenancy's ORM for the declaration.

    ⚠ **AN UNPUBLISHED SELECTOR YIELDS THE EMPTY SET, AND THE EMPTY SET IS THE
    SAFE ANSWER (hard-won law 3 — the unsafe option is the one you type).**
    Empty means *every service is metered*, which is the behaviour this product
    had before DEF-161: a service point with no meter is reported as `no_meter`
    and a human decides. The degradation therefore REFUSES rather than billing
    a real unread meter as base-only, which is the failure DEF-161's ruling
    warns against by name.

    A `frozenset` because every caller asks `code in ...` once per service
    point, and the tuple tenancy returns is ordered for a screen this never
    draws.
    """
    from apps.tenancy import selectors as tenancy_selectors

    reader = getattr(tenancy_selectors, "unmetered_service_codes", None)
    return frozenset(reader()) if reader is not None else frozenset()


def metered_service_codes() -> frozenset[str] | None:
    """WHICH of this tenant's services a meter can serve — `metered` basis only.

    `apps.tenancy.selectors.metered_service_codes()`, wrapped for the same B1
    reason as `unmetered_service_codes` above. **`None` when tenancy publishes
    no such read**, so a caller can tell *nobody said* from *nothing is
    metered* and keep its own behaviour rather than filtering everything out
    (`DEF-MET-9056`).
    """
    from apps.tenancy import selectors as tenancy_selectors

    reader = getattr(tenancy_selectors, "metered_service_codes", None)
    return frozenset(reader()) if reader is not None else None


def service_size_class_index() -> dict[str, str]:
    """code/name (case-folded) → code for the tenant's ACTIVE utility-service
    size classes — the meters import's fourth lookup (BR-MET-530, PO ruling
    2026-08-28 *"Please do both"*).

    Wraps `tenancy.selectors.service_size_class_index()`, for the same B1/B2
    reason as every read in this block: tenancy hosts the list and metering may
    not reach into its ORM for the rows. Read ONCE per run by
    `_assets_measuring_indexes`' meters variant (DEF-324).

    ⚠ **EMPTY WHILE UNWIRED, AND THAT IS A REFUSAL, NOT A PASS.** With no index
    every named size resolves to nothing and `AST.SIZE_CLASS_IN_LOOKUP` rejects
    the row naming one. That is the deliberate direction (hard-won law 3 — the
    unsafe option is the one you type): a blank cell still loads, so an unwired
    list costs a utility the size column and never costs it the migration.
    """
    from apps.tenancy import selectors as tenancy_selectors

    reader = getattr(tenancy_selectors, "service_size_class_index", None)
    return dict(reader()) if reader is not None else {}


def asset_upload_scopes() -> dict[str, dict[str, Any]]:
    """Which service each active size class and unit of measure belongs to,
    plus the tenant's UoM lookup — `tenancy.selectors.asset_upload_scopes`,
    read ONCE per asset-upload run (plan U4, PO ruling 2026-09-30).

    ⚠ **EMPTY WHILE UNWIRED IS A REFUSAL, NOT A PASS** — the same posture as
    `service_size_class_index` above: with no UoM index a named unit resolves to
    nothing and `AST.UOM_FOR_SERVICE` rejects the row naming it; a blank cell
    still loads with the service's default unit.
    """
    from apps.tenancy import selectors as tenancy_selectors

    reader = getattr(tenancy_selectors, "asset_upload_scopes", None)
    if reader is None:
        return {"size_service": {}, "uom_index": {}, "uom_service": {}}
    return reader()


def ratified_size_class_codes(service_code: str) -> tuple[str, ...]:
    """`BR-TEN-171`'s ratified size-class codes for ONE utility service,
    smallest first — or an EMPTY tuple where the vocabulary does not answer.

    ⚠ **THIS IS NOT `service_size_class_index()` AND THE TWO ANSWER DIFFERENT
    QUESTIONS.** The index above is what THIS TENANT has and is what the import
    JUDGES against. This is which of the ratified codes belong to a given
    service, and it has exactly one caller: `sample_csv`, choosing a worked cell
    for the downloadable template. The template's size must agree with the
    template's SERVICE or the shipped file contradicts itself, and the list is
    unscoped (BR-TEN-078) so nothing in the tenant's own rows can say which
    service a code belongs to.

    ⚠ **EMPTY COVERS THREE FACTS AND THIS CALLER MUST NOT CARE WHICH** — the
    same collapse `assets.seams.service_size_class_codes` documents at length
    and for the same reason: sewer is ruled to have none (BR-RAT-015), thermal
    steam and battery were never ruled (OQ-560 / OQ-561), and *"ship the sample
    cell blank"* is the correct answer to all three. A blank size is lawful
    (BR-AST-500), so the template still round-trips (DEF-616).

    The `SizeClassNotRuled` catch is BY TYPE, never a bare `except`: an unknown
    service code still raises and is a bug.
    """
    from importlib import import_module

    try:
        module = import_module("apps.tenancy.service_size_classes")
    except ImportError:  # pragma: no cover - tenancy always present
        return ()
    fn = getattr(module, "size_classes_for_service", None)
    if not callable(fn):  # pragma: no cover - defensive
        return ()
    not_ruled = getattr(module, "SizeClassNotRuled", None)
    try:
        rows = fn(service_code)
    except not_ruled or NotImplementedError:
        return ()  # OQ-560 / OQ-561 — never ruled, so never sampled
    except KeyError:  # pragma: no cover - a code that is not one of the ten
        return ()
    return tuple(code for code, _name in rows)


def service_id_by_code(code: str) -> Any | None:
    """The platform catalog id for one service code, or None for a code the
    catalog does not carry. Wraps `tenancy.selectors.service_ids_by_code()`
    (published 2026-08-11 for billing's stamp — same B1 posture here: metering
    holds the CODE and needs the ID for its per-service settings FK, and may
    not reach into tenancy's ORM for the translation). CR-038 A1."""
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.service_ids_by_code().get(code)


def tenant_date_format() -> str | None:
    """WHICH date format this tenant DECLARES for itself — `MM/DD/YYYY`,
    `DD/MM/YYYY`, … — or None when it has never said.

    ⚠ **THIS EXISTS SO THE IMPORTER NEVER GUESSES BETWEEN US AND EVERYWHERE
    ELSE (CR-036 a).** `1/1/2026` is the same day in both readings and
    `3/4/2026` is two different real days in them, and neither reading errors —
    so a sniffer would mis-date a migration silently, which is far worse than
    refusing it. The tenant's own S8 Regional setting (`tenant_settings.
    date_format`, BR-TEN-020, defaulted to `MM/DD/YYYY` at provisioning) is a
    STATEMENT THEY MADE, not an inference we drew, and it is the only source in
    this product that can settle the question.

    Read ONCE PER RUN by `import_runs._apply_mapping` and passed down —
    DEF-324's lesson: a per-row settings read spent 40% of a provisioning
    request on a question one query answers.
    """
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.regional_settings().get("date_format")


def template_published_in(code: str, *, category: str | None, language: str) -> bool | None:
    """`DEF-CUS-9195` — does the utility hold PUBLISHED wording of the message
    class `code` in exactly `language`? `None` while notifications is unwired.

    Asked through `notifications.template_service.resolve`, the resolver
    `queue_document` itself pins with, so the answer and the pin cannot
    disagree: the variant counts only when the resolver's OWN answer is in that
    language, never when it fell back to the default wording. A refusal
    (nothing published at all) is *no*."""
    fn = resolve("notifications", "resolve", kind="template_service")
    if fn is None:
        return None
    from apps.notifications import template_service

    try:
        found = fn(code=code, category=category, language=language)
    except template_service.TemplateRefused:
        return False
    return getattr(found, "language", None) == language


def tenant_default_language() -> str | None:
    """The utility's default language — since 2026-10-29 (PO option B) the
    FALLBACK language of a letter to a customer, whose own preferred language
    is asked first by `notifications.queue_document`. The paragraph below is
    the 2026-09-23 history.

    `OQ-CUS-12619`, closed 2026-09-23, PO verbatim: *"(a) Portal only; emails
    in English."* `BR-NOT-006` amended the same day: a message resolves on the
    UTILITY's default language and never on `accounts.preferred_language`,
    which drives the customer portal alone. The variant model is untouched —
    this code is what the resolver is ASKED for, so a Spanish-default utility
    that published a Spanish variant sends it and one that did not gets its
    `default` variant.

    None when the utility never set one (`""` included), which resolves the
    `default` variant rather than a guessed English. Read through tenancy's own
    Regional selector, the one `tenant_date_format` above uses; customers reads
    it the same way (`apps.customers.seams.tenant_default_language`).
    """
    from apps.tenancy import selectors as tenancy_selectors

    code = tenancy_selectors.regional_settings().get("language")
    return str(code) if code else None


def tenant_currency() -> str | None:
    """`DEF-MET-9232` — the utility's currency code (`CHAR(3)`, CLAUDE.md rule
    2), the one a New Connection quote letter names beside its amount. Read
    through tenancy's own Regional selector, as billing's `_tenant_currency`
    does. None when the utility never set one: the letter then names the
    absence rather than printing somebody else's currency."""
    from apps.tenancy import selectors as tenancy_selectors

    code = tenancy_selectors.regional_settings().get("currency")
    return str(code) if code else None


def account_addressee(account_id: Any) -> dict[str, Any] | None:
    """`DEF-MET-9232` — `customers.selectors.bill_addressee_for_account`: the
    account holder's NAME and the SERVICE address walked to the premises (hard
    rule 8), the read a bill's stage 6 asks, so a New Connection letter and the
    build's bill name the same person at the same address. None while unpublished
    or for an account this tenant does not hold (HR-1)."""
    fn = resolve("customers", "bill_addressee_for_account", kind="selectors")
    return fn(account_id) if fn is not None else None


def master_account_search(term: Any) -> Any:
    """`CR-177-BRC10` task 1b — the tenant's MASTER accounts matching a name or
    number, as a LAZY queryset the caller pages (NFR-3). READ-ONLY: metering
    writes no `accounts` row (B2 §2). `None` while customers has not published
    it, which the caller reads as *no account found*, never as an error."""
    fn = resolve("customers", "master_account_search_queryset", kind="selectors")
    return fn(term) if fn is not None else None


def master_account_search_rows(accounts: Any) -> dict[str, dict[str, Any]]:
    """`CR-177-BRC10` task 1b — ONE page of `master_account_search` as rows a
    screen may show: number, name, account type name, person or company,
    status. `{}` while unpublished."""
    fn = resolve("customers", "master_account_search_rows", kind="selectors")
    return fn(accounts) if fn is not None else {}


def tenant_state() -> str | None:
    """WHICH US state this tenant DECLARES for itself, AS ITS POSTAL CODE — or
    None when it has never said. `tenants.state`, through tenancy's own regional
    selector and its `us_state_code` fold.

    ⚠ **THIS EXISTS SO THE SAMPLE ESTATE STOPS WRITING A DELIBERATE `None`
    INTO A COLUMN THE IMPORTER OFFERS (CR-039 wave E task 23, BR-MET-139).**
    The premises importer accepts `state` — alias `state` / `province` — and
    the seeder sent `"state": None` on all 44 rows while the tenant's own
    answer sat one table away. That is the CR's finding 11 in miniature: a
    demo tenant looking THINNER than an imported one on a column that
    exists, so nobody exercises it and nobody notices it is empty.

    **NONE IS A REAL ANSWER AND MUST STAY ONE.** `tenants.state` is not
    required at signup — DEF-444 is the whole story of what happens when it
    is missing — so a tenant that never named a state has premises with no
    state, which is the truth. Filling in a plausible `TX` because the
    fixture's map anchors sit in Austin would put a made-up fact on 44 rows
    and make it look decided (the sample-fixture spec's rule 7, applied to a
    FIELD rather than to a figure).

    ⚠ **IT ANSWERS THE POSTAL CODE, NOT THE WORD — `DEF-MET-4629`, PO ruling
    2026-09-08 (*"(a) Texas, fix the postcode"*).** `tenants.state` holds
    whatever the sign-up form put there, and the form's own list is
    `tenancy.selectors.US_STATES`, whose KEYS are names (*"Texas"*) and whose
    VALUES are codes (*"TX"*) — so the demo tenants declare **Texas** while
    `seed_demo.PREMISES`, `portal.sample_data` and `import_runs`' sample all
    write **TX**. Both then existed in one column: `select distinct state from
    premises` answered `Texas` AND `TX`, and one account's screen printed
    *Silver Creek, Texas 68901* over a mailing box reading *Silver Creek, NE*.

    The fold happens HERE, at the point the declaration becomes an ADDRESS
    COMPONENT, and not on `tenants.state` itself: what a clerk picked in a
    dropdown is their own record, and Settings goes on showing them the word
    they chose. `us_state_code` is the repo's own normaliser and is already the
    reader `DEF-444`'s tax-jurisdiction seeding goes through, so this uses one
    map rather than adding a second.

    ⚠ **A VALUE THE MAP CANNOT READ IS RETURNED VERBATIM, NEVER DROPPED.**
    Returning `None` for an unrecognised word would put an empty state on every
    premises of that tenant, which is exactly the shape `DEF-2848` cost a whole
    print run — `BR-NOT-029` clause (b) holds a bill with no state. So an
    unknown spelling survives as itself and is somebody's to look at, which is
    the same posture the premises importer takes on a stated service.

    Read ONCE PER BLOCK by `sample_data.seed_sample_records`, not per row —
    DEF-324's lesson, the same one `tenant_date_format` records above.
    """
    from apps.tenancy import selectors as tenancy_selectors

    value = tenancy_selectors.regional_settings().get("state")
    text = str(value or "").strip()
    if not text:
        return None
    return tenancy_selectors.us_state_code(text) or text


def service_row_id(service_code: str) -> Any | None:
    """The platform service catalog row id, for the reviewed FK
    service_points.service_id (B2 §2 / r16 #3). READ-ONLY probe on an
    RLS-exempt platform table — tenancy exposes no id-bearing selector yet
    (Eng disposition, recorded; no write ever crosses the boundary)."""
    from django.apps import apps as django_apps

    model = django_apps.get_model("tenancy", "Service")
    return model.objects.filter(code=service_code, active=True).values_list("id", flat=True).first()


@batch_reads.memoised(copy=True)
def service_ids_for_codes(service_codes: list[str]) -> list[Any]:
    """Catalog row ids for a list of service codes — the plural of the above.

    An UNKNOWN code contributes no id rather than raising: a bill run scoped to
    a service this tenant does not have covers nothing for it, which is the
    honest answer. Raising would make one stale scope entry abort a whole run.
    """
    from django.apps import apps as django_apps

    model = django_apps.get_model("tenancy", "Service")
    return list(
        model.objects.filter(code__in=list(service_codes), active=True).values_list("id", flat=True)
    )


def tenant_today() -> Any:
    """Today in the tenant's timezone (BR-TEN-020/043 — the event date the
    numbering kernel demands explicitly, never a wall clock read here)."""
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.tenant_today()


def tenant_timezone() -> Any:
    """The clock this utility is on — `tenant_today()`'s other half.

        apps.tenancy.selectors.tenant_timezone() -> ZoneInfo

    ⚠ **THE SAME SEAM `apps/customers/seams.py` GREW FOR `DEF-CUS-6433`, AND
    FOR THE SAME DEFECT.** An AGE is a subtraction of two DAYS, and
    `tenant_today()` alone gives you only the left one: the right one is a
    stored `datetime`, and turning that into a day needs the same zone or the
    two halves of one sum are read on two clocks. `DEF-CUS-6433` measured what
    that costs — from 19:00 in Brazos Bend until midnight UTC, five hours of
    every evening, every request on `REQ-01` read one day older than it was —
    and `DEF-CUS-7620` is the same fault on this module's `NCT-01`.

    B1 / `BR-TEN-013`: named here so a caller reaches tenancy's ONE derivation
    (`BR-TEN-081`) through the seam rather than importing `ZoneInfo` itself.
    """
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.tenant_timezone()


def age_is_accented(age_days: Any) -> bool | None:
    """**`BR-CUS-106`'s threshold, asked for rather than copied.**

        apps.customers.service_request.age_is_accented(age_days) -> bool | None

    The PO ruled on 2026-08-25 (decision D4) that an AGE column accents at
    **seven days or more, inclusive**, and `apps/customers/service_request.py`
    is where that figure lives — one place, *"so this row and any later caller
    cannot drift apart"*, which is the reason the function exists at all rather
    than a constant beside each screen.

    ⚠ **`None` IS *NOBODY COULD BE ASKED* AND IS NEVER `False`.** A missing
    implementer answering *"not old"* is `DEF-075`'s exact substitution on a
    column a clerk chases work from, and `False` renders identically to a real
    *plain* row. The caller states the absence instead.

    ⚠ **THE SIGNATURE WAS TAKEN ON `REQ-01` AND `NCT-01` WAS NOT SHOWN —
    `OQ-CUS-12771`.** Reusing the ruled figure is what stops a second number
    being minted here; whether a BUILD, which takes weeks rather than days,
    wants its own is a product judgment and that row is the place it returns
    to the agenda. Nothing is blocked and nothing is stubbed on it.
    """
    fn = resolve("customers", "age_is_accented", kind="service_request")
    if fn is None or age_days is None:
        return None
    result = fn(age_days)
    return None if result is None else bool(result)


def service_default_uom(service_code: str) -> str | None:
    """The tenant's primary UoM for a service (EP-TEN-06) — the default the
    asset wizard stamps EXPLICITLY on a measuring asset (CLAUDE.md rule 3).

    ⛔ **ONE QUERY. DEF-1549, AND IT IS THE SAME LESSON AS `enabled_service_
    codes` ABOVE.** This used to answer by walking `service_catalog()` — the S8
    SCREEN read — and taking one field out of the matching row. Every caller of
    this is a PER-ROW write loop (`assets._create_asset_inner`,
    `services._create_meter_for_unit`, `importers._asset_for_unit`), so each of
    them paid a whole screen per row: ~10 catalog services, four joins each,
    plus `customers.active_account_count` issuing **two queries per service
    point** inside it. The Product Owner's twenty-row meter import hit a
    gunicorn `WORKER TIMEOUT` on exactly this, the day after `DEF-1075` cleared
    the first N+1 in front of it.

    It now resolves `apps.tenancy.selectors.service_default_uom`, which answers
    the identical question — including for a present-but-off service, see its
    docstring for why that is load-bearing — in one indexed query.

    ⚠ **STILL THE SINGULAR, AND STILL NOT FREE.** A caller that needs the unit
    for MANY services in one pass wants `service_default_uoms()` below, which is
    one query for all of them; this one is a query each. The rule of thumb that
    `DEF-324` and this defect both cost a support cycle to learn: **a lookup
    inside a loop belongs outside it.**
    """
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.service_default_uom(service_code)


def service_default_uoms() -> dict[str, str | None]:
    """`{code: primary UoM}` for every ENABLED service, in ONE query.

    CR-039 wave A: the sample plant has to know what unit each service is
    measured in before it can build a meter in it, and asking
    `service_default_uom` once per service walks the whole S8 screen read each
    time (~150 queries a call — DEF-324). `None` for a service the tenant
    declares no unit for is the honest answer and the caller REPORTS it; there
    is no fallback here and there must not be one.
    """
    from apps.tenancy import selectors as tenancy_selectors

    return dict(tenancy_selectors.service_default_uoms())


def service_billed_uoms() -> dict[str, dict[str, Any]]:
    """`{code: {"billed_uom", "conversion_factor"}}` for every ENABLED service.

    BR-MET-143 (PO 2026-08-27): the sample plant needs the unit a service is
    BILLED in, beside the unit its register reads, before it can decide what
    multiplier the meter it plants carries. One query, same posture as
    `service_default_uoms` above — and NULLs are the ordinary answer, meaning
    "the register's own unit is billed", never "refuse".
    """
    from apps.tenancy import selectors as tenancy_selectors

    return dict(tenancy_selectors.service_billed_uoms())


def unit_reconciliation(reading_unit: str | None, pricing_unit: str | None) -> dict[str, Any]:
    """**BR-MET-143 published as a seam**: does a reading's unit match the unit
    of the thing that PRICES it, and if not, can the meter's multiplier close
    the gap?

    PO verbatim, 2026-08-27: *"we have to match utility service unit and meter
    reading unit - if it does not match then we have intriduce multiplier factor
    on meter."*

    The rule itself is `apps.metering.register_units.reconciliation`; this is
    the door another module uses, because the scale-versus-dimension judgment is
    metering's and must have exactly one implementation. `assets.sample_data`
    is the caller today — it plants the meters the rule describes.
    """
    from apps.metering import register_units

    return register_units.reconciliation(reading_unit, pricing_unit).as_dict()


def number_series_format(series: str) -> str | None:
    """The tenant's stored format for a series, or None when no row exists
    (BE-06: seeding series rows is provisioning's job)."""
    from apps.tenancy import selectors as tenancy_selectors

    from core import errors

    try:
        return tenancy_selectors.number_series_row(series)["format"]
    except errors.NotFoundError:
        return None


#: How many issued numbers a rehearsal prints before it stops and says "…".
#: Five, matching `assets.selectors.PREVIEW_NUMBERS_SHOWN`, so one rehearsal
#: panel renders every target the same way.
PREVIEW_NUMBERS_SHOWN = 5


def number_series_preview(series: str, *, count: int) -> dict[str, Any] | None:
    """**CR-046 D1 — THE NUMBERS A COMMIT WOULD ISSUE, WITHOUT ISSUING THEM.**

    `assets.selectors.asset_no_preview_run`'s contract for the three targets
    whose series has no per-type prefix: premises, units, accounts each take
    numbers straight off one counter, so the run is a contiguous block and no
    per-row code list is needed.

    ⚠ **IT ALLOCATES NOTHING AND ADVANCES NOTHING.** `core.numbering.preview`
    is BE-06's peek contract — *"validates + renders only, allocates nothing"* —
    and this walks it forward by an OFFSET rather than calling `next_number`
    N times. A rehearsal may lawfully be run twice; N allocations per rehearsal
    would burn numbers on rows that never load, which is the very thing the PO
    ruled against when they said the allocation belongs *"just before updating
    teh record in the database"*.

    `None` when the tenant has no row for this series, so the caller says
    *"your numbering is not set up"* rather than printing an invented range.

    ⚠ **A CR-005 RESTART PERIOD IS NOT MODELLED, AND THAT IS STATED RATHER THAN
    HIDDEN** — the counter rolls back to 1 when the period turns, so a
    rehearsal on the last day of a period can name numbers a commit on the next
    day would not use. `asset_no_preview_run` inherits the same limit
    deliberately rather than modelling a second, divergent answer.
    """
    from apps.tenancy import selectors as tenancy_selectors

    from core import errors, numbering as core_numbering

    if count <= 0:
        return None
    try:
        row = tenancy_selectors.number_series_row(series)
    except errors.NotFoundError:
        return None
    series_format = str(row.get("format") or "")
    if not series_format:
        return None
    try:
        start = int(row.get("next_number") or 0)
    except (TypeError, ValueError):  # pragma: no cover — tenancy stores an int
        return None
    if start <= 0:
        return None
    issue_date = tenant_today()

    def rendered_at(offset: int) -> str | None:
        try:
            return core_numbering.preview(series_format, start + offset, issue_date)
        except Exception:
            # A malformed stored format must not break a rehearsal — the
            # operator is trying to find out what is wrong with their file.
            return None

    numbers = [
        value
        for offset in range(min(count, PREVIEW_NUMBERS_SHOWN))
        if (value := rendered_at(offset)) is not None
    ]
    return {
        "series_format": series_format,
        "next_number": start,
        "count": count,
        "numbers": numbers,
        "last": rendered_at(count - 1),
    }


def save_import_mapping(**kwargs: Any) -> dict[str, Any] | None:
    """BR-AST-048 copy-on-write — `import_mappings` is TENANCY's table, so the
    runner's "Save mapping as template" writes through tenancy's own service.
    None while unwired: the save then refuses rather than half-writes."""
    fn = resolve("tenancy", "save_import_mapping")
    return fn(**kwargs) if fn is not None else None


def touch_import_mapping(mapping_id: Any) -> None:
    """BR-AST-048's most-recently-used clock — a tenancy-owned column, moved
    by tenancy's own service when a run is recognised as a template. A no-op
    while unwired: recognition is a convenience, never worth failing an
    extract over."""
    fn = resolve("tenancy", "touch_import_mapping")
    if fn is not None:
        fn(mapping_id)


def advance_number_series(actor: Any, series: str, minimum_next: int) -> int:
    """DEF-577 — move a series' counter FORWARD past numbers this module has
    already written under their own names (an import's customer-supplied
    numbers, a caller-supplied `unit_no`). `number_series` is tenancy-owned
    (B2 PM owner map), so the move is made by tenancy's own service; metering
    never writes another module's table. Forward-only by BR-TEN-035."""
    from apps.tenancy import services as tenancy_services

    return tenancy_services.advance_number_series_to(actor, series, minimum_next)


# ── assets (BR-AST-028 one registry, both creation directions) ──────────────
def create_asset_for_unit(**kwargs: Any) -> dict[str, Any] | None:
    fn = resolve("assets", "create_asset_for_unit")
    return fn(**kwargs) if fn is not None else None


def attach_existing_asset(**kwargs: Any) -> dict[str, Any] | None:
    fn = resolve("assets", "attach_existing_asset")
    return fn(**kwargs) if fn is not None else None


# ── CR-162-BRC10 · a build's activation, through each owner's own door ──────
def build_asset_rows(service_point_ids: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """`assets.services.build_asset_rows` — the assets on each service point.
    Unwired ⇒ `{}`, which the activation read reports as *no assets*."""
    fn = resolve("assets", "build_asset_rows")
    return dict(fn(service_point_ids)) if fn is not None else {}


def install_build_assets(
    actor: Any, *, service_point_ids: list[Any], install_date: Any
) -> list[dict[str, Any]] | None:
    """`assets.services.install_build_assets` — the ONE door that fits a build's
    earmarked assets. `None` = the assets module is not wired; the activation
    refuses rather than activating a service whose meter it could not fit."""
    fn = resolve("assets", "install_build_assets")
    if fn is None:
        return None
    return list(fn(actor, service_point_ids=service_point_ids, install_date=install_date))


def install_fitted_asset(actor: Any, *, asset_id: Any, install_date: Any) -> dict[str, Any] | None:
    """`assets.services.install_fitted_asset` — the meter a move-in visit was
    raised for, Installed at the visit's acceptance (`DEF-AST-9712`). `None`
    when nothing moved (already installed) or the assets module is not wired —
    the acceptance itself never fails over it."""
    fn = resolve("assets", "install_fitted_asset")
    return None if fn is None else fn(actor, asset_id=asset_id, install_date=install_date)


def hold_new_master_pending(actor: Any, account_id: Any) -> dict[str, Any] | None:
    """`customers.services.hold_new_master_pending` — the build's owner master
    account, held Pending at Create once its charges are on the books."""
    fn = resolve("customers", "hold_new_master_pending")
    return fn(actor, account_id) if fn is not None else None


def activate_pending_master_account(actor: Any, account_id: Any) -> dict[str, Any] | None:
    """`customers.services.activate_pending_master_account` — the build's owner
    master account, Pending → Active on the first activation."""
    fn = resolve("customers", "activate_pending_master_account")
    return fn(actor, account_id) if fn is not None else None


def assets_on_unit(unit_id: Any) -> list[dict[str, Any]]:
    fn = resolve("assets", "assets_on_unit", kind="selectors")
    return list(fn(unit_id)) if fn is not None else []


def assets_on_units(unit_ids: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """`assets_on_unit` for MANY units — `CR-131-BRC07`.

    `apps.assets.selectors.assets_on_units(unit_ids) -> {unit id: [asset, …]}`.
    SET-06 step 3 called the single-unit seam once per member and cost 5.1
    queries per unit — **3,711 round trips on a 726-unit route**, measured. An
    unpublished selector yields an EMPTY map, which reads as *no meters* — the
    same honest degradation `assets_on_unit` already gives by returning `[]`,
    and the reason `route_meter_picker` now says out loud when it could not
    ask rather than drawing an empty table over it.
    """
    fn = resolve("assets", "assets_on_units", kind="selectors")
    return dict(fn(list(unit_ids))) if fn is not None else {}


def asset_counts_for_units(unit_ids: list[Any]) -> dict[str, int]:
    """CR-029 D7 — how many assets each of MANY units holds, in one read.

    `apps.assets.selectors.asset_counts_for_units(unit_ids) -> dict[str, int]`.
    The routes and cycles lists take `len(assets_on_unit(...))` per member unit,
    which is the N+1 D7 ruled against; this is the same fact, batched. An
    unpublished selector yields an EMPTY map, which reads as 0 meters — the
    same honest degradation `assets_on_unit` already gives by returning [].
    """
    fn = resolve("assets", "asset_counts_for_units", kind="selectors")
    return dict(fn(list(unit_ids))) if fn is not None else {}


def billable_asset_count(unit_id: Any, service_code: str, as_of: Any) -> int | None:
    """BR-RAT-090's quantity — how many of this service's assets stand on this
    unit on `as_of`. **`None` means NOBODY LOOKED, and it is never a zero.**

    `apps.assets.selectors.billable_asset_count(unit_id, service_code, as_of)`
    owns the three predicates the rule names — on this unit on that DATE (from
    the dated, append-only `AssetAssignment`, BR-AST-017), IN SERVICE by the
    lifecycle stage's `behavior_class` and never by its label (BR-AST-031), and
    FOR THIS SERVICE through the service point. Metering asks by name rather
    than joining: assets is B2 r4's table and the join is the boundary B1 draws.

    ⚠ **THE UNPUBLISHED BRANCH ANSWERS `None`, NOT `0`, AND THAT IS THE WHOLE
    REASON THIS WRAPPER RETURNS AN OPTIONAL AT ALL.** Every other assets read in
    this block degrades to an empty answer, because an empty list of meters
    reads as *"no meter"* — an exception a human sees. A count does not have
    that property: `0` is a REAL and BILLABLE answer (*"the utility looked and
    this unit has no carts"*), so degrading to `0` would say the utility looked
    when nobody did, and a three-cart household would be billed **$0.00** for
    trash on a document that looks entirely normal. `assets.billable_asset_count`
    says so itself — *"the 'nobody looked' case is not expressible here and must
    never be invented as a zero — it is the seam's business"* — and this is that
    seam. `resolution.AssetCountUnavailable` refuses on the `None`.

    It is the unmetered twin of `billing_multiplier_for`'s absent branch and of
    `connection_size_for`'s `None`: a missing fact is reported, never filled in.
    """
    fn = resolve("assets", "billable_asset_count", kind="selectors")
    if fn is None:
        return None
    count = fn(unit_id, service_code, as_of)
    return None if count is None else int(count)


def billable_asset_size_classes(
    unit_id: Any, service_code: str, as_of: Any
) -> list[str | None] | None:
    """**WHAT this service's assets on this unit ARE — the size class of each,
    or `None` when NOBODY LOOKED.** `CR-062` D1 / H2.

    `apps.assets.selectors.billable_asset_size_classes(unit_id, service_code,
    as_of)` — the same three predicates, the same population and the same date
    as `billable_asset_count` above, which is the point: a bill that COUNTS and
    a bill that SUMS must be talking about the same equipment.

    ⚠ **THE UNPUBLISHED BRANCH ANSWERS `None`, NOT `[]`, FOR THE REASON THE
    COUNT ANSWERS `None` AND NOT `0`.** An empty list is a real, billable answer
    — *"the utility looked and this unit has no panels"*, which BR-MET-108's
    ruled zero prices at `$0.00` and puts on the document. Degrading to `[]`
    would say the utility looked when nobody did, and a 14 kW array would bill
    `$0.00` on a bill that foots and prints. It is the same distinction
    `billing_multiplier_for` and `connection_size_for` draw and the one this
    whole block exists to keep.

    ⚠ **A `None` INSIDE THE LIST IS A DIFFERENT FACT AGAIN** and is carried
    faithfully: that asset exists, it is in service, and nobody has recorded
    which type it is. It cannot be summed and must not be skipped —
    `_stamp_installed_capacity` refuses the total on it rather than quietly
    totalling the panels it does recognise.
    """
    fn = resolve("assets", "billable_asset_size_classes", kind="selectors")
    if fn is None:
        return None
    rows = fn(unit_id, service_code, as_of)
    return None if rows is None else list(rows)


def billable_asset_size_classes_by_asset(
    unit_id: Any, service_code: str, as_of: Any
) -> list[tuple[str, str | None]] | None:
    """`apps.assets.selectors.billable_asset_size_classes_by_asset` — each
    billable asset's NUMBER with its size class, for naming the asset whose
    size has no capacity (`DEF-RAT-10220`). `None` while assets has not
    published it: the refusal then stands without names, never with a guess.
    """
    fn = resolve("assets", "billable_asset_size_classes_by_asset", kind="selectors")
    if fn is None:
        return None
    rows = fn(unit_id, service_code, as_of)
    return None if rows is None else list(rows)


def capacity_uom_for_service(service_code: str) -> str | None:
    """**The unit this service's size classes SUM in, or `None` when they do not
    sum at all** — `BR-TEN-171` as tenancy holds it. `CR-062` D1 / H2.

    The sanctioned cross-module read of `apps/tenancy/service_size_classes.py`,
    beside `ratified_size_class_codes` above and for the same B1 reason: tenancy
    owns the ratified list, this module needs one fact out of it, and the module
    holds no model and issues no query, so this is an import of LAW rather than
    a reach into another module's tables.

    **THIS IS THE ONE CALL THAT TELLS THE TWO CAPACITY ARITHMETICS APART**, and
    it names no service:

        "solar"   -> "kW"    the installed capacities ADD UP
        "trash"   -> None    the carts are COUNTED (gallons + cubic yards add
                             up to nothing in any unit)
        "fire"    -> None    CR-063 — *"exactly like trash"*
        "water"   -> None    a band PICKS a rate and sums with nothing

    ⚠ **`None` MEANS *DO NOT SUM THESE* AND NEVER *SUM THEM IN SOME DEFAULT
    UNIT*.** There is no default: CLAUDE.md hard rule 3 forbids one.

    An unruled dimension (`SizeClassNotRuled`) and a service code the catalogue
    does not hold both answer `None` — for this caller the three collapse
    correctly, because *"do not sum"* is the right answer to all of them. The
    catch is BY TYPE and never a bare `except`, so a genuine programming error
    still raises.
    """
    from importlib import import_module

    try:
        module = import_module("apps.tenancy.service_size_classes")
    except ImportError:  # pragma: no cover - tenancy always present
        return None
    fn = getattr(module, "capacity_uom_for_service", None)
    if not callable(fn):  # pragma: no cover - defensive
        return None
    not_ruled = getattr(module, "SizeClassNotRuled", None)
    try:
        return fn(service_code)
    except not_ruled or NotImplementedError:
        return None  # OQ-560 — never ruled, so nothing to sum
    except KeyError:  # pragma: no cover - a code the catalogue does not hold
        return None


def total_installed_capacity(service_code: str, size_class_codes: list[str]) -> Any:
    """**The SUM of the installed capacities named by `size_class_codes`** —
    `apps.tenancy.service_size_classes.total_capacity`. `CR-062` D1 / H2.

    The Product Owner's own example, 2026-09-02: three panels of 2 kW, 4 kW and
    8 kW are **14 kW**, which at their `$14.00` per kW is **$196.00**.

    Returns `None` — never a number — where the total cannot be stated: a
    BANDED service (`NotACapacityService`) or a code this service does not have
    (`KeyError`, which is the one that would otherwise be SILENT, since solar
    and battery both sum in `kW`). The caller refuses on the `None`; it must
    never read it as a zero, for the reason the whole of this block exists.

    ⊕ **`DEF-RAT-10220` (PO 2026-10-17) — THE TENANT'S SIZE-CLASS ROWS ANSWER
    FIRST.** `tenancy.selectors.size_class_capacities` reads this tenant's own
    `capacity` column for the service (built-in rows carry the ladder's figure
    there; a tenant-added `SOL-P47.84` carries 47.84), and `total_capacity`
    lets a row win over the ladder. 47.84 + 10 kW = **57.84 kW**, which at
    $14.00 per kW is **$809.76**. An unpublished selector degrades to the
    ladder alone — the behaviour before — never to a guess.
    """
    from importlib import import_module

    try:
        module = import_module("apps.tenancy.service_size_classes")
    except ImportError:  # pragma: no cover - tenancy always present
        return None
    fn = getattr(module, "total_capacity", None)
    if not callable(fn):  # pragma: no cover - defensive
        return None
    not_capacity = getattr(module, "NotACapacityService", None)
    read_rows = resolve("tenancy", "size_class_capacities", kind="selectors")
    capacities = read_rows(service_code) if read_rows is not None else None
    try:
        return fn(service_code, size_class_codes, capacities)
    except not_capacity or NotImplementedError:
        return None  # a band picks a rate; it adds up to nothing
    except KeyError:
        return None  # a code this service does not have — never a plausible sum


def asset_ids_for_service_point(service_point_id: Any) -> list[Any]:
    """Meters on one service point — the reads seam's hop from service to meter.

    An unpublished selector yields NO meters, which the caller reports as
    `no_meter` on that service. That is the honest degradation: a service with
    no meter is an exception a human sees, where an invented meter id would be
    a read that does not exist.
    """
    fn = resolve("assets", "asset_ids_for_service_point", kind="selectors")
    return fn(service_point_id) if fn is not None else []


def billing_asset_ids_for_service_point(service_point_id: Any) -> list[Any]:
    """`DEF-BIL-10155` / `DEF-BIL-10156` — the meters whose readings are this
    point's BILLED measurement: the unit's own meter, never a sub-meter or the
    building's master beside it (the rule is the owner's docstring). While
    assets has not published it, every meter on the point — exactly the list
    `asset_ids_for_service_point` gives, which is the behaviour before."""
    fn = resolve("assets", "billing_asset_ids_for_service_point", kind="selectors")
    return fn(service_point_id) if fn is not None else asset_ids_for_service_point(service_point_id)


def in_service_asset_ids_for_service_point(service_point_id: Any) -> list[Any] | None:
    """The meters on one service point that are IN SERVICE now — PO 2026-09-30.

    `billing_reads_for_unit` splits a metered point into one row per meter
    (two meters = two lines) only across THESE, so a meter exchanged mid-cycle
    — the old meter retired but still attached — stays one row, as it always
    was. `None` while assets has not published the read: *nobody can tell*,
    and the caller then does not split, which is today's behaviour.
    """
    fn = resolve("assets", "in_service_asset_ids_for_service_point", kind="selectors")
    return fn(service_point_id) if fn is not None else None


def prime_assets_for_check(
    unit_codes: dict[str, tuple[str, ...]], service_point_ids: list[Any], *, as_of: Any
) -> dict[str, list[str]]:
    """B27 — `apps.assets.selectors.prime_check_batch`: one bulk Check batch's
    meters in a few queries, primed into the batch memo. `{}` while assets has
    not published it — each account then asks per point, exactly as before."""
    fn = resolve("assets", "prime_check_batch", kind="selectors")
    return fn(unit_codes, service_point_ids, as_of=as_of) if fn is not None else {}


def asset_reference_count(unit_id: Any) -> int:
    """BR-MET-037: assets ever attached to the unit (0 while unwired — no
    assets table would mean no asset can reference it)."""
    fn = resolve("assets", "asset_reference_count")
    return int(fn(unit_id=unit_id)) if fn is not None else 0


def retire_sample_replaced_meter(actor: Any) -> bool | None:
    """Sample fixture spec §4 case 3 — `apps.assets.services
    .retire_sample_replaced_meter(actor) -> bool`.

    ⛔ **DEF-660.** The old serial must come off AFTER its June read exists, and
    the two live in different blocks of the sample load: assets creates and
    retires meters, metering posts reads, and the module order puts assets
    first. So the reads block ASKS assets to retire, once its batches have
    posted. Assets performs the write — nothing here touches the `assets` table.

    `None` while assets publishes no such function: the reads still stand and
    the seeder reports the case-3 meter was left active, which is a visible gap
    rather than a silent one (the `record_unit_plan_assignment` posture).
    """
    fn = resolve("assets", "retire_sample_replaced_meter")
    return bool(fn(actor)) if fn is not None else None


# ── assets — the CR-028 import targets' seam (B16 §4.7: "writes via assets
# services only"). The runner stages/maps/validates in THIS module and every
# assets ROW is written by the owning module's service — the inverse of the
# `create_asset_for_unit` direction above, same law (B1/B2 r4).
def create_asset_from_import(**kwargs: Any) -> dict[str, Any] | None:
    """One import row → one asset (+ its BR-AST-045 assignment when a unit is
    tagged). None while assets is absent — the load then REFUSES rather than
    writes half a file (the record_unit_plan_assignment posture)."""
    fn = resolve("assets", "create_from_import")
    return fn(**kwargs) if fn is not None else None


def update_asset_from_import(**kwargs: Any) -> dict[str, Any] | None:
    """Insert-and-update's existing-row half — SPEC fields only (BR-AST-034)."""
    fn = resolve("assets", "update_from_import")
    return fn(**kwargs) if fn is not None else None


# ── customers — the CR-030 W1 accounts target's seam ────────────────────────
# Same law as the assets block above and for the same reason: the runner stages,
# maps and validates HERE, and every `accounts` row is written by the module that
# owns the table (B1/B2 §2). `accounts` is customers'; this module may not touch
# it. G20 asserts every documented seam has an implementer.
def confirm_opening_changeover(**kwargs: Any) -> dict[str, Any] | None:
    """⛔ **POST A HELD OPENING BATCH UNDER THE OPERATOR'S REAL CHANGEOVER
    DATE** (PO ruling 2026-08-27). The accounts loaded without one, their
    buckets carry a PROVISIONAL date, and no journal entry exists — which is
    the only state in which the date is still changeable (hard rule 4).

    `None` while customers cannot answer, and the caller REFUSES rather than
    reporting a batch posted whose journal entries do not exist (DEF-075)."""
    fn = resolve("customers", "confirm_opening_changeover")
    return fn(**kwargs) if fn is not None else None


def accounts_import_index() -> dict[str, dict[str, Any]]:
    """CR-046 C4 — LOWERED account number (and `ext:<external_ref>`) → the row,
    read ONCE per run (DEF-324). `{}` while customers cannot answer, which
    makes every quoted number read as invented — the honest outcome, because
    the alternative is matching against a world we could not see."""
    fn = resolve("customers", "account_import_index", kind="selectors")
    return fn() if fn is not None else {}


def update_account_from_import(**kwargs: Any) -> dict[str, Any] | None:
    """CR-046 C4 — insert-and-update's existing-row half, DETAIL fields only.

    ⚠ **IT NEVER RE-POSTS AN OPENING BALANCE, AND THAT IS HARD RULE 4 RATHER
    THAN A SCOPE CHOICE.** The four `ob_*` buckets became journal entries
    through the ledger at the first load (GT-16 ❄️). Journal entries are
    immutable; a correction is a NEW entry, never an edited one. So a re-run of
    a corrected file updates the account's DETAILS and leaves its books exactly
    where they are — which is also why the count it returns is `updated` and
    never `with_opening_balance`.

    `None` while customers cannot answer, and the load then REFUSES rather than
    writing half a file (the `create_asset_from_import` posture)."""
    fn = resolve("customers", "update_from_import")
    return fn(**kwargs) if fn is not None else None


def create_account_from_import(**kwargs: Any) -> dict[str, Any] | None:
    """One import row → one account (+ its customer link, its four
    `account_opening_buckets` rows and its deposit).

    None while customers cannot answer, and the load then REFUSES rather than
    writing half a file — the `create_asset_from_import` posture, and the
    DEF-075 lesson underneath it: `None` must never be read as *"this module has
    nothing"* when it means *"this module cannot answer"*."""
    fn = resolve("customers", "create_from_import")
    return fn(**kwargs) if fn is not None else None


def create_master_account_from_import(**kwargs: Any) -> dict[str, Any] | None:
    """`CR-058` W3 · `BR-MET-1030` — the premises import's owner account.

    ⚠ **THE SAME DOOR AS EVERY OTHER MASTER ACCOUNT, RESOLVED THROUGH A
    DIFFERENT NAME FOR ONE REASON: THE ROLE.** `customers.create_master_account`
    is `@require_role`-decorated and a DEFERRED import load runs in a worker
    carrying `_JobActor` — *"an id, and no role, BY DESIGN"* — so calling the
    decorated function would refuse every row of every large migration.
    `customers.import_writer.create_master_account_from_import` is customers'
    own undecorated implementer over the identical door, published for exactly
    this caller, and it is customers that states when its own guard does not
    apply (`DEF-1108`'s remedy: the role was checked at `load()`, where a role
    still existed).

    `None` while customers cannot answer, and the caller then falls back to the
    role-gated door rather than writing half a migration — the
    `create_asset_from_import` posture, and the `DEF-075` lesson underneath it:
    `None` must never be read as *"this module has nothing"* when it means
    *"this module cannot answer"*.
    """
    fn = resolve("customers", "create_master_account_from_import", kind="import_writer")
    return fn(**kwargs) if fn is not None else None


# ── work (CR-077 — the parts target's three doors) ──────────────────────────
#
# ⚠ **THE FIRST TIME THIS RUNNER HANDS ROWS TO `work`, AND THE THIRD MODULE IT
# WRITES THROUGH.** `accounts` is customers', the three assets targets are
# assets', and `parts` is Work's (`BR-WRK-002`; `G78` fails a foreign write
# from Work's first commit). The shape is `BR-MET-096`'s and is unchanged: a
# new target is a PARAMETER of the one runner, and the LOAD asks the owning
# module to write. Nothing in `apps/metering/` touches the `parts` table.


def parts_import_index() -> dict[str, dict[str, Any]]:
    """LOWERED part number → `{id, part_no, name}` — the existing-row index.

    Read ONCE per run and shared by stage 3 and stage 4, so the rehearsal and
    the commit resolve against the same world (`DEF-544` / `DEF-324`).

    `{}` while work cannot answer. ⚠ That is INDISTINGUISHABLE from *"this
    tenant has no parts yet"*, which is a real and common state — so the
    emptiness is never read as a verdict on its own: `_refuse_parts_unwired`
    is what decides whether work is reachable, and it asks for the WRITER."""
    fn = resolve("work", "parts_import_index", kind="import_writer")
    return fn() if fn is not None else {}


def part_category_index() -> dict[str, str]:
    """LOWERED category name AND code → the category's own name.

    Stage 3 has to judge an unknown category BEFORE anything is written, and
    `work.services._clean_part` resolves the same two ways. Asking rather than
    restating is what stops a rehearsal and a commit disagreeing about what the
    tenant's list holds."""
    fn = resolve("work", "part_category_index", kind="import_writer")
    return fn() if fn is not None else {}


def create_part_from_import(**kwargs: Any) -> dict[str, Any] | None:
    """One import row → one row in the parts register.

    ⚠ **RESOLVED FROM `work.import_writer` AND NOT FROM `work.services`, AND
    THE REASON IS `DEF-1108` RATHER THAN TIDINESS.** A deferred load runs in a
    worker carrying `_JobActor` — *"an id, and no role, BY DESIGN"* — so a
    `@require_role` writer would refuse every row of every large migration.
    Work publishes an UNDECORATED implementer for this one caller, exactly as
    `customers.import_writer.create_master_account_from_import` does, and it is
    Work that states when its own guard does not apply. `import_runs.load()`
    checks the role once, where a role still exists.

    `None` while work cannot answer, and the load then REFUSES rather than
    writing half a file — the `create_asset_from_import` posture, and the
    `DEF-075` lesson underneath it: `None` must never be read as *"this module
    has nothing"* when it means *"this module cannot answer"*."""
    fn = resolve("work", "create_part_from_import", kind="import_writer")
    return fn(**kwargs) if fn is not None else None


def update_part_from_import(**kwargs: Any) -> dict[str, Any] | None:
    """An existing part, updated from a file — the `upsert` half.

    `None` while work cannot answer, and the load refuses rather than writing
    half a file."""
    fn = resolve("work", "update_part_from_import", kind="import_writer")
    return fn(**kwargs) if fn is not None else None


def rollback_part_from_import(**kwargs: Any) -> str | None:
    """Reverse one part this run created — `reversed` · `kept_issued` ·
    `missing`, decided by work because work owns the table and the rule.

    `None` while work cannot answer, and the caller then reports the row as
    kept rather than claiming a reversal it did not make (`DEF-075`)."""
    fn = resolve("work", "rollback_part_from_import", kind="import_writer")
    return fn(**kwargs) if fn is not None else None


# ── payments (`P1.2` — the EIGHTH target's writer seam) ─────────────────────
#
# ⚠ **TWO NAMES, NOT FOUR, AND THE TWO MISSING ONES ARE THE RULE.** Every other
# `import_writer` seam above publishes create · update · rollback. Payments
# publishes **create and an index** and nothing else, because CLAUDE.md hard
# rule 4 forbids both of the others: a payment may not be UPDATEd, so there is
# no `upsert` half to reach, and a posted payment may not be un-written, so
# there is no rollback to call. `import_runs.rollback` refuses this target by
# name and `_load_payments_rows` creates no rollback point.
#
# ⚠ **A LANE ADDING `update_payment_from_import` OR
# `rollback_payment_from_import` HERE IS REVERSING A HARD RULE**, not filling a
# gap. The absence is the deliverable.


def payments_import_index() -> dict[str, Any] | None:
    """Every account, keyed the way a remittance file references one.

    Read ONCE per run and shared by stage 3 and stage 4, so the rehearsal the
    operator read and the commit they pressed resolve against the same world
    (`DEF-544` / `DEF-324`).

    ⚠ **`None` MEANS PAYMENTS CANNOT ANSWER AND THE LOAD REFUSES; `{}` MEANS
    THE UTILITY HAS NO ACCOUNTS** — the `DEF-075` distinction, and on this path
    it is the difference between *"nothing was written, ask support"* and four
    hundred rows each correctly reporting an account not on file. The two are
    never merged, which is why this one seam returns `None` rather than the
    `{}` its parts sibling returns: an empty account index on a money import is
    a sentence about a whole morning's takings.
    """
    fn = resolve("payments", "payments_import_index", kind="import_writer")
    return fn() if fn is not None else None


def create_payment_from_import(**kwargs: Any) -> dict[str, Any] | None:
    """One import row → one payment, written by the module that owns the table.

    ⚠ **RESOLVED FROM `payments.import_writer` AND NOT FROM
    `payments.services`, AND THE REASON IS `DEF-1108`.** A deferred load runs
    in a worker carrying `_JobActor` — an id and no role, by design — so a
    `@require_role` writer would refuse every row of a four-hundred-line
    morning file. Payments publishes an UNDECORATED implementer for this one
    caller, exactly as customers and work do, and it is payments that states
    when its own guard does not apply. `import_runs.load()` checks the role
    once, where a role still exists.

    ⚠ **IT REFUSES AN UNCERTAIN MATCH RATHER THAN POSTING ONE** (`P1.12`,
    CS-2 rule 2). A row matched only by the payer's name raises, the loader
    catches it inside that row's savepoint, and the row is REJECTED with its
    reason on the receipt — never quietly skipped, because money missing from a
    report is money nobody chases.

    `None` while payments cannot answer, and the load then REFUSES rather than
    writing half a file."""
    fn = resolve("payments", "create_payment_from_import", kind="import_writer")
    return fn(**kwargs) if fn is not None else None


def payments_match_account(**kwargs: Any) -> dict[str, Any] | None:
    """One row down payments' own match ladder — the verdict, not a payment.

    ⚠ **THIS IS WHY STAGE 3 AND STAGE 4 CANNOT DISAGREE, AND IT IS `DEF-544`'s
    LAW RATHER THAN AN OPTIMISATION.** The rules that flag a row at stage 3 and
    the writer that refuses it at stage 4 call the SAME pure function on the
    SAME index. A second matcher in this module would be two answers to *"whose
    money is this"* with one owner — the thing `BR-MET-096` and hard-won law 5
    both exist to stop — and the operator would read one verdict in the
    rehearsal and meet another at the commit.

    Pure: it reads the index it is handed and touches no database, so calling
    it once per row for a four-hundred-line file costs nothing.

    `None` while payments cannot answer. The rules then report NOTHING rather
    than reporting every row clean — an unwired matcher must never look like a
    file with no problems in it."""
    fn = resolve("payments", "match_account", kind="import_writer")
    return fn(**kwargs) if fn is not None else None


def payments_posted_cheques(keys: Any) -> dict[Any, str] | None:
    """`DEF-PAY-10697` (LBX-08) — which of a file's cheques payments ALREADY has.

        apps.payments.import_writer.posted_cheques(keys) -> {key: payment_no}

    A key is `payments.import_writer.cheque_key(account_id, amount, reference)`.
    `None` while payments cannot answer, and `PAY.CHEQUE_NOT_ALREADY_RECORDED`
    then reports nothing rather than reporting every row new."""
    fn = resolve("payments", "posted_cheques", kind="import_writer")
    return fn(keys) if fn is not None else None


def payments_cheque_key(account_id: Any, amount: Any, reference: Any) -> Any:
    """`payments.import_writer.cheque_key` — ONE definition of *the same cheque*
    (account · amount · reference), so stage 3's in-file rule and its
    already-recorded rule cannot disagree with payments about it. `None` while
    payments is unpublished."""
    fn = resolve("payments", "cheque_key", kind="import_writer")
    return fn(account_id, amount, reference) if fn is not None else None


def open_work_order_count_for_unit(unit_id: Any) -> int | None:
    """`CR-089` wave F `F3` — **HOW MANY JOBS ARE STILL RUNNING ON THIS UNIT.**

        apps.work.selectors.open_work_order_count_for_unit(unit_id) -> int

    The unit page's fourth tile. PO ruling 2026-09-08, verbatim: *"Kpis you
    ahve shown on Unit view - these KPis will be displayed across all views"*,
    and `CR-089`'s reading of it names the four — **Assets · Owed · Plan ·
    Open work**.

    ⚠ **METERING ASKS; IT DOES NOT COUNT (`B1`/`B2` §2, and this one is
    subtle).** The six Work tables are hosted in `apps/metering/connections.py`
    today — `CLAUDE.md`'s module map says so and `16-work/03-field-map.md` §4
    is where they move — so this module CAN reach `WorkOrder` and filter it. It
    must not, because the fact being asked for is not *how many rows* but **how
    many are OPEN**, and that word is `apps/work/seams/metering_seam
    .OPEN_WORK_ORDER_STATES` — `planned · in_progress · blocked`, the same set
    the dispatcher's own queue carves out. A tuple of three strings restated
    here would be a second definition of a queue with one owner, and it would
    be right on the day it was written (`DEF-127`'s shape, and hard-won law 1's).

    ⚠ **`None` IS *WORK CANNOT ANSWER* AND IT IS NEVER `0`** — `DEF-075`, one
    module over: a zero on the tile says *nobody is coming and nobody needs
    to*, and a screen that cannot tell that from *we could not ask* will
    eventually tell a clerk the first while meaning the second. The tile draws
    a dash on the null.
    """
    fn = resolve("work", "open_work_order_count_for_unit", kind="selectors")
    if fn is None:
        return None
    return int(fn(unit_id))


def open_work_at_premises(premises_id: Any) -> dict[str, Any]:
    """`CR-089` `F3` / `DEF-MET-4733` — **WHAT WORK IS STILL RUNNING AT THIS
    ADDRESS**, for the property page's fourth tile.

        apps.work.selectors.open_work_at_premises(premises_id)
            -> {"count": int, "next": {id, order_no, type, window_start} | None}

    ⚠ **METERING ASKS; IT DOES NOT COUNT** — the same boundary the unit's tile
    takes one function up, and for the same reason. The six Work tables are
    hosted in `apps/metering/connections.py` today, so this module CAN filter
    `WorkOrder`; what it must not own is the word **OPEN**
    (`apps/work/seams/metering_seam.OPEN_WORK_ORDER_STATES`) nor the five
    anchors that make an order *stand at* an address (`BR-WRK-006`, walked to
    the premises per `BR-MET-1161`). Both live in work, and work answers.

    ⚠ **`count: None` IS *WORK COULD NOT BE ASKED* AND IS NEVER `0`**
    (`DEF-075`). A zero on this tile says *nobody is coming and nobody needs
    to*; a screen that cannot tell that from *we could not ask* will eventually
    tell a clerk the first while meaning the second. The tile draws a dash on
    the null.
    """
    fn = resolve("work", "open_work_at_premises", kind="selectors")
    if fn is None:
        return {"count": None, "next": None}
    answer = fn(premises_id)
    return {"count": int(answer["count"]), "next": answer.get("next")}


def occupying_account_status_codes() -> frozenset[str] | None:
    """CR-047 · BR-CUS-017/022 — **which account statuses take a unit.**

    Stage 3's two new accounts rules (`ACC.UNIT_NOT_OCCUPIED`,
    `ACC.START_DATE_REQUIRED`) both need the same fact and neither may guess
    it: a row whose status is a DRAFT (`pending_activation`) is lawful on an
    occupied unit and lawful with no start date, because it never calls
    `_make_occupying`. Firing on every row regardless of status would reject
    rows the load would have written — the exact mirror of the defect these
    rules exist to close.

    ⚠ **THE VOCABULARY IS `customers`' AND IT IS READ, NEVER RE-STATED.**
    `BR-CUS-055` makes account statuses TENANT-EXTENSIBLE and keys occupancy
    off the behaviour CLASS, never the label, so a set of codes hard-coded in
    metering would be a second copy of a rule with one owner (B1/B2 §2).

    Two doors, in order:

      1. `apps.customers.selectors.occupying_status_codes() -> Iterable[str]`
         — the documented contract, and the ONLY one that can see a status
         this tenant added or renamed. It is not authored yet; the customers
         lane implements this signature and this seam then answers from it
         with nothing here changing.
      2. The module's own published CONSTANTS —
         `services.OCCUPYING_BEHAVIOR_CLASSES` × `services.SEED_ACCOUNT_STATUSES`
         — which is `BR-CUS-055`'s seeded vocabulary as customers declares it,
         read from the owning module rather than copied into this one. This is
         the `queue_refusals()` posture: a non-callable attribute resolved by
         name because half a published interface is not an interface.

    ⚠ **WHAT DOOR 2 CANNOT SEE, STATED RATHER THAN HIDDEN.** A status a tenant
    ADDED, or a seeded one whose behaviour class a tenant CHANGED, is invisible
    to it — those live in `account_statuses` rows, which is customers' table.
    A row carrying such a status is judged by stage 3 as a draft and reaches
    the loader, where `_make_occupying` refuses it correctly and CR-047's
    per-row savepoint turns that into ONE rejected row with its reason. So the
    residue costs a rehearsal that under-reports, never a run that half-loads.
    It is REPORTED, and door 1 closes it.

    `None` — NOT an empty set — when `apps.customers` cannot answer at all.
    `frozenset()` would say *"no status occupies a unit"*, which would silence
    both rules with a fabricated answer; `None` says *"nobody was asked"* and
    the evaluators report the rule as not measured (`unit_is_occupied`'s own
    posture, and DEF-075's lesson).
    """
    published = resolve("customers", "occupying_status_codes", kind="selectors")
    if published is not None:
        return frozenset(str(code).strip().lower() for code in published() if code)
    try:
        services = import_module("apps.customers.services")
    except ImportError:  # pragma: no cover — customers ships in-tree
        return None
    classes = getattr(services, "OCCUPYING_BEHAVIOR_CLASSES", None)
    seeded = getattr(services, "SEED_ACCOUNT_STATUSES", None)
    if not classes or not seeded:
        return None
    occupying = set(classes)
    return frozenset(
        str(code).strip().lower()
        for code, _name, behavior_class in seeded
        if behavior_class in occupying and code
    )


def owner_master_account_summary(account_id: Any) -> dict[str, Any] | None:
    """DEF-650 — the ACCOUNT behind a premises owner, read through the boundary.

    **PO 2026-08-27:** *"you ahve to showall details form account"*. The premises
    screens show an owner's account number, status, balance and contact — and
    every one of those facts lives in `customers`, so every one of them is
    fetched HERE rather than copied onto a metering row. `owner_selectors`
    serves what this answers and nothing else.

    ⚠ **`None` MEANS TWO DIFFERENT THINGS AND BOTH ARE HONEST** (the DEF-075
    posture, stated because this one is genuinely ambiguous and the ambiguity is
    harmless): *customers cannot answer* and *there is no such account*. Either
    way the premises screen has nothing to show and says so; no money decision
    is taken on this read, so the two need not be told apart.
    """
    fn = resolve("customers", "owner_master_account_summary", kind="selectors")
    return fn(account_id) if fn is not None else None


def master_account_numbers(account_ids: Any) -> dict[str, dict[str, Any]]:
    """`BR-MET-1181` — the NUMBER, NAME and status of many accounts, per PAGE.

    ⛔ **IT EXISTS SO A LIST CAN PRINT AN ACCOUNT NUMBER WITHOUT BUYING
    `DEF-324` A SECOND TIME.** `owner_master_account_summary` above is one
    account read PLUS one ledger derivation per call, and `DEF-324` measured
    what that costs on a list: *47 of 118 profiled seconds answering one question
    304 times*. So the premises list does not expand an account — and until now
    that left it holding an id it may not print (B14 rule 31) and no number it
    could. **This asks once per PAGE.** Not per row: that distinction is the
    whole point, and a caller that loops over it has re-created the defect.

    `{account_id: {"account_no", "name", "status", "kind"}}`, and an id with no
    entry is an account this tenant does not hold — the same answer as
    *customers cannot answer*, and harmlessly so, because the screen then draws
    the account it has an id for without its number rather than drawing no
    account at all.

    ⚠ **`name` JOINED THE ANSWER ON 2026-09-23 (`DEF-MET-6304`), AND IT IS THE
    REASON THE FIRST LINE NO LONGER SAYS *"IN ONE QUERY"*.** The Owner cell on
    S14 read **"No name recorded · AC-2026-00051"** beside a real, named
    company: the list had a number and no name, so it rendered the absence
    sentence — which states something about the ACCOUNT that is false. The name
    IS recorded. **It is not a column on `accounts`** — it is the account's
    primary CONTACT's `full_name`, a second table — so carrying it costs
    customers ONE MORE STATEMENT FOR THE PAGE. Measured on a PostgreSQL clone
    of `brazosbend`, 2026-09-23: **1 → 2 statements per page, at every page
    size from 2 to 50.** Still O(1); still nothing per row.

    ⚠ **IT CARRIES NO MONEY, DELIBERATELY, AND THE NAME DOES NOT OPEN THAT
    DOOR.** No balance and no arrears: a figure on a list is a figure somebody
    quotes, and `DEF-127`'s shape — the ledger's Σ, with a REASON where the
    books cannot be asked and never `0.00` substituted for *we could not tell* —
    cannot be served cheaply in bulk. A list that wants money asks the detail
    read. A name is not a figure and nobody reconciles against one.
    """
    ids = [str(value) for value in (account_ids or []) if value not in (None, "")]
    if not ids:
        return {}
    fn = resolve("customers", "master_account_numbers", kind="selectors")
    return fn(ids) if fn is not None else {}


def account_facts_for_unit(unit_id: Any, *, as_of: Any) -> dict[str, Any] | None:
    """CR-089 wave I — EVERYTHING the unit's Account tab shows, in one read.

        apps.customers.unit_account_facts.unit_account(unit_id, as_of=date)
            -> Mapping  {account, facts, owner_account, no_account_reason}
          where `facts` is {protections, customer_class, autopay, payment_plan,
               budget_billing, collections, bounced_payments, tax_exemption,
               deposit, notes, reach, external_ref, credit_tier}

    `DEF-CUS-4691`: the Account tab rendered five facts, every one correct, and
    **a supervisor standing on a unit arranging a shut-off could not see that the
    account carries a medical certificate.** The protection is a row in another
    module's table and no unit-side selector read it.

    ⚠ **ONE CALLABLE, NOT THIRTEEN.** Every fact above is customers', and the
    ones that are not (payment plans, the ladder, budget billing) are read by
    customers through ITS own seams. Resolving thirteen names from here would put
    metering inside three other modules' vocabularies and give the tab thirteen
    ways to be half-wired; the boundary this module actually has to defend is
    *metering does not touch another module's ORM* (B1/B8), and one name defends
    it as well as thirteen and drifts less.

    **`None` means customers cannot answer, and the caller states that** rather
    than drawing a tab of absences that would read as *"this account has none of
    these things"*. Every other absence inside the payload is already a first-
    class answer with its own reason — see that module's docstring.

    A PURE READ. There is no write to call and metering has no door to one.
    """
    fn = resolve("customers", "unit_account", kind="unit_account_facts")
    return fn(unit_id, as_of=as_of) if fn is not None else None


def account_exists(account_id: Any) -> bool | None:
    """Is this account id one THIS tenant holds? — the validator behind
    `link_owner_master_account`, and the reason metering never touches
    `accounts` to answer it (B1/B2 §2).

    ⚠ **`None`, NOT `False`, WHILE CUSTOMERS CANNOT ANSWER.** `False` would make
    the link refusable for a reason that is about US and not about the id, and
    the caller must be able to tell those apart — `customer_exists` above takes
    the same posture for the same reason."""
    summary = owner_master_account_summary(account_id)
    if summary is None:
        fn = resolve("customers", "owner_master_account_summary", kind="selectors")
        return False if fn is not None else None
    return True


def account_lookup_indexes() -> dict[str, dict[str, str]]:
    """LOWERED input → canonical CODE, for the accounts target's four lookups.

    ⚠ **CODE → CODE, NOT CODE → ID, AND THAT IS THE POINT.** The runner resolves
    a `KIND_LOOKUP` cell against this and stores the result; `customers`'
    `_validate_account` then takes a CODE (`residential`) and does its own row
    lookup. Handing it an id here would make the import speak a vocabulary no
    other door speaks, and would put a second resolver between a spreadsheet and
    a validated rule.

    What the index buys is the STAGE at which a bad value is caught: with it, a
    file saying `resedential` is rejected at stage 3 with the row number, beside
    every other rejection; without it, 1,199 rows load and the 1,200th explodes
    inside the writer — the shape this module's docstrings keep warning about.

    Empty while customers cannot answer, which makes every lookup cell
    unresolved and therefore refused — the safe direction."""
    fn = resolve("customers", "import_lookup_indexes", kind="selectors")
    return fn() if fn is not None else {}


def identity_crypto_contexts() -> dict[str, str]:
    """`customers`' OWN blind-index context per identity fact — `BR-MET-1032`.

    `{'ssn': 'customers.ssn', 'driving_licence': 'customers.driving_licence',
      'phone': 'customers.phone', 'tax_id': 'customers.tax_id'}`.

    ⚠ **RESOLVED, NEVER COPIED, AND THE REASON IS NOT TIDINESS.** A staged
    identifier's blind index has to EQUAL the token on the customer row or the
    matcher looks it up and finds nothing — so this is a cryptographic contract
    between two modules, not a label. A mirrored copy that drifted would not
    raise: it would return *"no customer on file"* for a person who is on file,
    and mint a second Customer # for them. That is `DEF-2587`'s own damage
    arriving through a constant instead of through a matcher.

    ⚠ **AND IT IS THE ONE SEAM HERE THAT READS A MODULE CONSTANT RATHER THAN
    CALLING A SERVICE**, which is deliberate: `identity_match.CRYPTO_CONTEXT` is
    the declaration itself, and wrapping it in a function inside `customers`
    purely so this seam could call one would put a second place for it to be
    wrong.

    Empty while customers cannot answer, and `import_identity.protect_cells`
    then protects NOTHING rather than encrypting under a guessed context — a
    value encrypted under the wrong context is a value nobody can ever match,
    and it would be written that way permanently. Refusing to guess is the safe
    direction here in the strongest sense: the alternative is silent and
    irreversible.
    """
    table = resolve("customers", "CRYPTO_CONTEXT", kind="identity_match")
    if isinstance(table, dict):  # pragma: no cover — `resolve` returns callables
        return dict(table)
    try:
        module = import_module("apps.customers.identity_match")
    except ImportError:  # pragma: no cover — defensive, as everywhere here
        return {}
    contexts = getattr(module, "CRYPTO_CONTEXT", None)
    return dict(contexts) if isinstance(contexts, dict) else {}


def post_account_opening_batch(**kwargs: Any) -> dict[str, Any] | None:
    """The BR-CUS-049 handoff, once per RUN rather than once per row.

    ⚠ **THE BATCH IS THE UNIT AND THAT IS NOT A CONVENIENCE LOOP.** GT-16's
    batch line — *"Σ of all opening JEs = Σ of all imported buckets (1,213
    accounts → $184,320.55)"* — is a statement about the BATCH, and no
    per-account call can make it. `apps.ledger.opening_balances` refuses to
    report success unless Σ AR debits = Σ clearing credits, which is the check
    that stops a migration landing 1,212 correct entries and one wrong one, to
    be found by a bookkeeper next quarter with no lawful way to edit any of them
    (hard rule 4).

    Customers owns the call because customers owns the buckets; the LEDGER
    writes the journal lines (hard rule 5). This module only asks."""
    fn = resolve("customers", "post_opening_batch_from_import")
    return fn(**kwargs) if fn is not None else None


def rollback_account_from_import(actor: Any, account_id: Any, *, run_no: str | None = None) -> str:
    """Reverse one created account; answers reversed | kept_billed | missing.

    ⚠ `kept_billed` is the one that matters and it is law, not policy: an
    account whose invoice has been issued CANNOT be rolled back, because hard
    rule 4 forbids deleting an issued invoice. B18 §5.9.4's *"rollback window ·
    30 days · unbilled accounts only"* states the courtesy; this states the
    law.

    ⛔ **AND IT CAN RAISE — OQ-352.** An account whose OPENING BALANCES were
    posted is not reversed at all: hard rule 4 keeps the balanced opening
    journal entry alive, and no signed document states the reversing entry or
    its date, so customers refuses by name rather than deleting the buckets
    underneath a live entry. `import_runs.rollback` refuses the whole run for
    the same reason and BEFORE it spends the rollback point; this is the
    boundary guard behind it, so the refusal is not a fourth outcome to count
    and no caller reaches the delete by another door."""
    fn = resolve("customers", "rollback_from_import")
    return fn(actor, account_id, run_no=run_no) if fn is not None else "missing"


def rollback_asset_from_import(actor: Any, asset_id: Any, *, run_no: str | None = None) -> str:
    """Reverse one created asset; answers reversed | kept_reads |
    kept_terminal | missing (the AST-04 callout's vocabulary). `missing` when
    assets cannot answer at all — reported on the receipt, never guessed."""
    fn = resolve("assets", "rollback_from_import")
    return fn(actor, asset_id, run_no=run_no) if fn is not None else "missing"


def assets_import_index() -> dict[str, dict[str, Any]]:
    """LOWERED asset number → {id, asset_no, behavior_class, type_code} — the
    assets targets' existing-row index, read ONCE per run (DEF-324)."""
    fn = resolve("assets", "asset_import_index", kind="selectors")
    return fn() if fn is not None else {}


def assets_number_preview(type_codes: list[str]) -> dict[str, Any] | None:
    """**THE NUMBERS A LOAD WOULD ISSUE — a PEEK, never an allocation.**

    PO ruling 2026-08-27: the meters import takes no number from the file, so
    the rehearsal has to say what the commit will CALL the rows it creates.
    BR-AST-026's per-type prefix and the tenant's `asset` series both live in
    `assets`, which owns them, so this asks rather than restating either
    (the second statement is how a preview and an allocator come apart).

    `None` while unwired or when the tenant has no `asset` series row — the
    rehearsal then states that the numbering is unset rather than printing an
    invented range."""
    fn = resolve("assets", "asset_no_preview_run", kind="selectors")
    return fn(list(type_codes)) if fn is not None else None


def assets_outcome_stages() -> dict[str, dict[str, str]]:
    """The two lifecycle stages an imported asset can land in, in the TENANT'S
    own words (CR-046 D2). `assets` owns lifecycle stages and BR-AST-031 lets a
    tenant rename them, so the labels are asked for rather than restated here.
    Empty while unwired — the rehearsal then states the split without naming
    the stages, which is less, not wrong."""
    fn = resolve("assets", "import_outcome_stages", kind="selectors")
    return dict(fn()) if fn is not None else {}


def assets_lookup_index(list_code: str) -> dict[str, str]:
    """code/name (case-folded) → code for one assets-owned reference list
    (`meter_types` · `read_methods` · `device_types`). Empty while unwired —
    every named value then flags as unknown, which is honest, not silent."""
    fn = resolve("assets", "import_lookup_index", kind="selectors")
    return fn(list_code) if fn is not None else {}


def assets_reference_options(list_code: str) -> list[dict[str, str]]:
    """`[{code, name}]` for one assets-owned reference list, ACTIVE rows only,
    seeded entries first - the PICKER half of `assets_lookup_index` above.

    Used for `read_methods`, the vocabulary BR-MET-123 tags a read batch with.
    Empty while unwired, and the S28 step-1 control then states that the list
    is unavailable rather than offering an invented one - the same honest
    posture the index's docstring describes one function up.
    """
    fn = resolve("assets", "reference_list_options", kind="selectors")
    return list(fn(list_code)) if fn is not None else []


def active_service_assignments() -> list[dict[str, str]]:
    """(unit_id · service · asset_no) for every in-service, currently assigned
    METER — the "unit already has an active meter for this service" world."""
    fn = resolve("assets", "active_service_assignments", kind="selectors")
    return list(fn()) if fn is not None else []


def current_unit_for_asset(asset_id: Any) -> str | None:
    """The master's current seat, for the sub-meters same-premises warning."""
    fn = resolve("assets", "current_unit_for_asset", kind="selectors")
    return fn(asset_id) if fn is not None else None


# ── customers (W2 — unwired by construction) ────────────────────────────────
def active_account_for_unit(unit_id: Any) -> dict[str, Any] | None:
    """BR-MET-036: the derived-occupancy input. None while customers owns no
    tables — no account can exist, so "vacant" is true, not assumed."""
    fn = resolve("customers", "active_account_for_unit")
    return fn(unit_id) if fn is not None else None


def account_ids_for_units(unit_ids: Any) -> dict[str, str]:
    """`{unit_id: account_id}` — `accounts_for_units` below with only the id,
    for a caller that COUNTS (`DEF-MET-8732`: the cycles list's Accounts column
    paid 18.5 s at 40,000 accounts for models and contact names it threw away).
    `apps.customers.selectors.account_ids_for_units`. Empty while customers is
    unwired, as `accounts_for_units` is."""
    fn = resolve("customers", "account_ids_for_units", kind="selectors")
    return dict(fn(list(unit_ids))) if fn is not None else {}


def accounts_for_units(unit_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """CR-029 D7 — `active_account_for_unit` for a LIST of units, in one read.

    `apps.customers.selectors.accounts_for_units(unit_ids) -> dict[str, dict]`,
    keyed by unit id, each value the same `{id, account_no, customer_name,
    status}` shape the single-unit seam documents. SET-06D's Accounts tab, the
    cycle's account count and the coverage list all ask this question about a
    whole route at a time; asking it per unit was two queries per unit.

    An EMPTY map while customers owns no rows — no account can exist, so
    "nobody is on this route" is true by construction, not a guess.
    """
    fn = resolve("customers", "accounts_for_units", kind="selectors")
    return dict(fn(list(unit_ids))) if fn is not None else {}


def account_references(account_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """`B30` — the ACCOUNT a committed reading was taken for, by its own id.

        apps.customers.selectors.account_references(ids)
            -> {account_id: {id, account_no, customer_name, status}}

    `meter_reads.account_id` has been a reviewed cross-module FK (B2 §2) since
    the table existed and `collection_account_id` has stamped it since DEF-658.
    **Nothing ever read it back**, so the reading detail printed *"The account is
    not served on a reading; open it through the unit"* over the top of a column
    that held the answer — a stored fact and a printed absence for the same
    thing, which the blueprint calls *"the two-homes problem waiting to
    happen"* (`B30` · `MR-39`).

    ⚠ **IT IS THE READ'S OWN ACCOUNT, NEVER THE UNIT'S CURRENT ONE.** The unit
    seams above answer *who is on supply now*; this answers *who was on supply
    when the meter was read*, and on a moved-out unit those are different
    accounts. Resolving the first would hand a year of somebody's consumption to
    the new occupant, which is exactly what `collection_account_id` stamps the
    column to prevent.

    An id the tenant does not hold is ABSENT from the map. An EMPTY map while
    customers publishes no such callable — the caller states the absence rather
    than drawing a link to nothing (the DEF-075 posture).
    """
    fn = resolve("customers", "account_references", kind="selectors")
    return dict(fn(list(account_ids))) if fn is not None else {}


def owed_for_units(unit_ids: list[Any]) -> dict[str, dict[str, Any]]:
    """CR-089 wave E (`E1`/`PUJ-22`) — what each unit OWES, for a whole page.

        apps.customers.selectors.owed_for_units(unit_ids)
            -> {unit_id: {account_id, account_no, balance, balance_currency,
                          balance_basis, balance_unavailable,
                          balance_not_yet_billable}}

    The S15 list carried no money at all. This is the figure the accounts list
    and the S21 header already show, forwarded rather than recomputed — the
    whole of `DEF-127` is what a second derivation of a balance costs.

    ⚠ **BATCHED ON PURPOSE, AND THAT IS THE CONTRACT.** `unpaid_balance_state`
    below answers the same books one unit at a time and is right for a
    deactivation guard, which asks about ONE unit. A list column asking it per
    row is a ledger read per row on a screen a utility opens all day — the N+1
    `accounts_for_units` was added to remove, one table over.

    An EMPTY map while customers publishes no such callable, and a unit ABSENT
    from the map has no occupying account. Neither is `0.00`: the caller says
    *vacant* or *could not be read*, and never substitutes a zero for either
    (that substitution IS `DEF-127`).
    """
    fn = resolve("customers", "owed_for_units", kind="selectors")
    return dict(fn(list(unit_ids))) if fn is not None else {}


def account_reference_count(unit_id: Any) -> int:
    fn = resolve("customers", "account_reference_count")
    return int(fn(unit_id)) if fn is not None else 0


def unpaid_balance_exists(unit_id: Any) -> bool:
    """BR-MET-047 deactivation blocker — **`True` now also means "unreadable"**.

    ⚠ DEF-138: customers used to answer this from the CACHED `accounts.balance`
    column, which nothing writes, so it said `False` for every unit in the
    product including one whose account held an unpaid **108.88** — this
    refusal had never once fired against a real debt. It is now derived from
    the LEDGER through `customers.unpaid_balance_state`, and a book that cannot
    be asked BLOCKS rather than permits: a guard that cannot check must not
    pass. Use `unpaid_balance_state` below when the caller needs to say WHICH.
    """
    fn = resolve("customers", "unpaid_balance_exists")
    return bool(fn(unit_id)) if fn is not None else False


def unpaid_balance_state(unit_id: Any) -> dict[str, Any] | None:
    """DEF-138 — the same answer, with its REASON, so a blocker can be named.

    `{"state": "clear" | "unpaid_balance" | "balance_unreadable", "amount",
    "currency", "unavailable"}`. `None` while customers publishes no such
    callable, in which case the caller falls back to the boolean above — the
    documented seam posture, never a guessed business answer.
    """
    fn = resolve("customers", "unpaid_balance_state")
    if fn is None:
        return None
    answer = fn(unit_id)
    return dict(answer) if answer else None


def meter_by_no(asset_no: str | None) -> Any | None:
    """The meter a read row names, resolved WITHIN this tenant (US-MET-008
    TC-9: two tenants may both own an "M-7001"). None = not in inventory —
    US-MET-008/TC-8's error, and never an invitation to auto-create a meter.

    READ-ONLY probe on the assets registry: apps.assets exposes no by-number
    selector (its `_asset_by_no` is private), so this follows the same
    documented Eng disposition the rating `tariff_ref` probe above records.
    No write ever crosses the boundary."""
    if not asset_no:
        return None
    from django.apps import apps as django_apps

    from core import tenancy as core_tenancy

    model = django_apps.get_model("assets", "Asset")
    return (
        model.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), asset_no=str(asset_no).strip()
        )
        # `service_point__unit` rides along for CR-038 W6: the premises a
        # reconciliation row is keyed by is reached through it (BR-MET-125),
        # and DEF-324's one-read-per-thing discipline says join it once here
        # rather than lazy-loading it per master row.
        # `type` too (CR-038 W6): `asset_types.category` is what tells a DEVICE
        # from a meter (BR-MET-124/135), and the validation context asks it of
        # every row.
        .select_related(
            "status", "type", "service_point", "service_point__service", "service_point__unit"
        ).first()
    )


def meter_by_id(asset_id: Any) -> Any | None:
    """Same probe, keyed by id (the S25/S29 fix actions address a meter by id)."""
    if not asset_id:
        return None
    from django.apps import apps as django_apps

    from core import tenancy as core_tenancy

    model = django_apps.get_model("assets", "Asset")
    return (
        model.objects.filter(tenant_id=core_tenancy.current_tenant_id(), pk=asset_id)
        # `service_point__unit` rides along for CR-038 W6: the premises a
        # reconciliation row is keyed by is reached through it (BR-MET-125),
        # and DEF-324's one-read-per-thing discipline says join it once here
        # rather than lazy-loading it per master row.
        # `type` too (CR-038 W6): `asset_types.category` is what tells a DEVICE
        # from a meter (BR-MET-124/135), and the validation context asks it of
        # every row.
        .select_related(
            "status", "type", "service_point", "service_point__service", "service_point__unit"
        ).first()
    )


def submeters_of(asset_id: Any) -> list[Any]:
    """**BR-AST-003: the sub-meters hanging off one master, newest-last.**

    CR-038 W6 (BR-MET-125). Sub-meter-ness is STRUCTURE, never a column in a
    read file: a sub-meter is an asset whose `parent_asset_id` is the master's.
    Nothing in a CSV ever says "this row is a sub-meter" and nothing here asks
    it to — which is why this probe exists at all.

    READ-ONLY probe on the assets registry, the same documented Eng disposition
    `meter_by_no` above records: apps.assets exposes no by-parent selector
    (`selectors.assets_on_unit` is unit-keyed and `_asset_by_no` is private).
    No write ever crosses the boundary.

    Returns `[]` for a master with no sub-meters — which is the ordinary case
    and is NOT the same as "we could not tell": the query ran, the answer is
    zero, and the reconciliation resolver treats those two differently.
    """
    if not asset_id:
        return []
    from django.apps import apps as django_apps

    from core import tenancy as core_tenancy

    model = django_apps.get_model("assets", "Asset")
    return list(
        model.objects.filter(tenant_id=core_tenancy.current_tenant_id(), parent_asset_id=asset_id)
        .select_related("status", "type", "service_point", "service_point__service")
        .order_by("asset_no")
    )


def asset_type_category(asset: Any) -> str | None:
    """**`asset_types.category` — meters · sub_meters · behind_the_meter.**

    CR-038 W6 (BR-MET-124/135). The ONE fact that separates a DEVICE from a
    meter: BR-AST-004's tab key, carried on the asset's type row. A device (PV,
    battery, EV charger, generator, comms, modem/CPE, cart…) is
    `behind_the_meter`; `meters` and `sub_meters` are the measuring registry.

    Read off the row already loaded — this issues no query of its own when the
    caller selected `type` (both probes above do). None = the caller handed us
    an asset with no type loaded, which is REPORTED by the rule that asked,
    never read as "not a device".
    """
    asset_type = getattr(asset, "type", None)
    category = getattr(asset_type, "category", None)
    return str(category) if category else None


def unit_is_occupied(unit_id: Any) -> bool | None:
    """BR-MET-036 derived occupancy, as the BR-MET-052 `vacant_unit` rule needs
    it: True/False when customers can answer, **None when it cannot**.

    The W1 posture ("no account can exist, so vacant is true by construction")
    expired when customers landed its `accounts` table in W2. It exposes no
    active-account selector yet, so this returns None and the validation engine
    REPORTS the rule as not evaluated. Returning False instead would flag every
    read in the system as a vacant-unit warning — a fabricated answer, which is
    exactly what the seam pattern exists to prevent."""
    fn = resolve("customers", "active_account_for_unit")
    if fn is None:
        return None
    return fn(unit_id) is not None


def service_billed_uom(service_code: str) -> tuple[str | None, Any]:
    """`(billed_uom, conversion_factor)` for a service (B2 r6.4 / OQ-004
    closure). Both None means no conversion is configured — the caller must
    then BLOCK or report, never convert on an assumed factor (the OQ-004
    closure is explicit: "no silent conversion")."""
    from django.apps import apps as django_apps

    from core import tenancy as core_tenancy

    service_model = django_apps.get_model("tenancy", "Service")
    service = service_model.objects.filter(code=service_code, active=True).first()
    if service is None:
        return None, None
    tenant_service_model = django_apps.get_model("tenancy", "TenantService")
    row = (
        tenant_service_model.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), service=service
        )
        .select_related("billed_uom")
        .first()
    )
    if row is None or row.billed_uom is None:
        return None, None
    return row.billed_uom.code, row.conversion_factor


# ── reads (W2 reads lane — meter_reads LANDED 2026-08-10) ───────────────────
def read_reference_count(unit_id: Any) -> int:
    """BR-MET-037 third probe. Wired now that meter_reads exists."""
    fn = resolve("metering", "read_reference_count_impl")
    return int(fn(unit_id)) if fn is not None else 0


def collected_read_count(*, route_id: Any = None, cycle_id: Any = None) -> int | None:
    """BR-MET-011: collected/progress derive from committed reads. None while
    the reads lane is unwired — the tab renders "—", never a fabricated 0."""
    fn = resolve("metering", "collected_read_count_impl")
    if fn is None:
        return None
    return int(fn(route_id=route_id, cycle_id=cycle_id))


def last_read_completion(route_id: Any) -> Any:
    fn = resolve("metering", "last_read_completion_impl")
    return fn(route_id) if fn is not None else None


def cycle_is_referenced(cycle_id: Any) -> bool:
    """BR-MET-009: delete audit-locked once a read batch or bill run references
    the cycle. Both owners unwired → False by construction."""
    for module, function in (("metering", "cycle_read_batch_count"), ("billing", "bill_run_count")):
        fn = resolve(module, function)
        if fn is not None and fn(cycle_id):
            return True
    return False


def period_consumed_by_run(cycle_id: Any, period_start: Any, period_end: Any) -> bool | None:
    """BR-MET-132 — *has a bill run consumed this cycle period?* READ-ONLY.

    The rule, verbatim (PO 2026-08-26, CONFIRMED): the Missing chip *"counts
    missing required records for windows that are OPEN or CLOSED-BUT-UNBILLED,
    and drops a period only when its bill run has consumed it"*.

    `bill_runs` is billing's table (B1), so billing publishes the predicate
    (`apps.billing.selectors.period_consumed_by_run`) and this resolves it late
    like every other probe here.

    **None IS A THIRD ANSWER AND THE CALLER MUST TREAT IT AS ONE.** It means
    *billing cannot tell us*, which is not *"no run has billed this period"* —
    the DEF-075 posture every seam in this module takes. `completeness.py`
    reads a None as NOT consumed, so the chip stays LOUD: a chip that keeps
    counting a period that was in fact billed costs a clerk one look, and a
    chip that goes quiet over a period nobody read is DEF-046 again.
    """
    fn = resolve("billing", "period_consumed_by_run", kind="selectors")
    if fn is None:
        return None
    return bool(fn(cycle_id, period_start, period_end))


# ── billing (US-MET-016: the invoice a BILLED read's correction names) ──────
def invoice_ref(invoice_id: Any) -> dict[str, Any] | None:
    """The invoice a `read_corrections` row will reference (J6 step 1 handoff).

    Metering NEVER touches the invoice — US-MET-016 §1 and J6 step 1 both say
    the original invoice is untouched. This is a READ, for one purpose: so the
    linkage cannot be written against an id that names nothing, or another
    tenant's bill. `apps.billing.selectors.invoice_or_404` raises the
    indistinguishable 404 for both cases (HR-1/G4), which is exactly the answer
    a cross-tenant probe should get, and `invoice_row` supplies the number for
    the audit payload.

    Returns None when billing publishes neither — REPORTS that it cannot answer
    rather than substituting an invoice (G20 / DEF-075). The correction service
    then REFUSES, because a linkage naming an unverifiable invoice is a promise
    that the read fix and the money fix travel together with nothing behind it.
    """
    lookup = resolve("billing", "invoice_or_404", kind="selectors")
    render = resolve("billing", "invoice_row", kind="selectors")
    if lookup is None or render is None:
        return None
    from core import errors

    try:
        return render(lookup(invoice_id))
    except errors.NotFoundError:
        raise


def issued_bill_count_for_unit(unit_id: Any) -> int | None:
    """*"How many bills has this unit produced?"* — `DEF-511`, `PUJ-55`.

    **THE CONTRACT BILLING IS ASKED FOR, DECLARED HERE AND NOWHERE ELSE:**

        apps.billing.selectors.issued_bill_count_for_unit(unit_id) -> int

    ⚠ **THE QUESTION HAS BEEN UNANSWERABLE SINCE 2026-08-21 AND THE MOVE SCREEN
    HAS SAID SO ON ITS FACE EVER SINCE.** `CR-024`'s ruled warning asks it to
    *"state how many bills"*; nothing in this product counts issued invoices by
    unit, so the screen states the number of ACCOUNTS — which it can read — and
    prints the absence rather than a plausible number. `DEF-511` is that row and
    it is still open.

    ⚠ **`None` IS *COULD NOT BE READ* AND `0` IS *NEVER BILLED*, AND THE TWO ARE
    DIFFERENT SENTENCES ON THE SCREEN.** This is `billable_asset_count`'s
    asymmetry one seam over (`DEF-1813`) and `DEF-127`'s third state: degrading
    to `0` here would tell a clerk *this unit has never billed* on the evidence
    that nobody looked, and *never billed* is exactly the fact that makes a move
    a harmless data-entry correction. So the honest absence is the fallback.

    **WHY THE COUNT IS NOT COMPUTED HERE.** `invoices.account_id → accounts.id →
    accounts.unit_id` is a two-hop join across two other modules' tables, and B1
    forbids this module touching either. Billing already owns the exact join —
    `billing.selectors.last_issued_bill_for_unit` filters
    `account__unit_id=…, status__in=INVOICE_LOCKED_STATUSES` — so the count is
    that queryset's `.count()` in the module that owns the rows. **One function,
    in `apps/billing/selectors.py`, is all that is owed**; the day it lands this
    seam resolves it and every screen reading it starts printing the number with
    no further change here or on the client.
    """
    fn = resolve("billing", "issued_bill_count_for_unit", kind="selectors")
    if fn is None:
        return None
    count = fn(unit_id)
    return None if count is None else int(count)


def quote_bill(invoice_id: Any) -> dict[str, Any] | None:
    """**The bill this build raised, WITH its charge lines** — `CR-126-BRC07`.

        apps.billing.selectors.invoice_detail(invoice_id)
            -> invoice_row(...) + {"lines": [{charge_code, description,
               quantity, unit_price, amount, ...}], ...}

    The build record's `CHARGES · STEP 6` table draws `CHARGE · BASIS · QTY ·
    UNIT · AMOUNT` under a `Quoted` total, and every one of those five is a
    column on an issued invoice line. **Billing owns them and billing renders
    them**: `_line_rows` already serves each figure as a decimal STRING at
    stored scale (hard rule 2 — never a float, and the rounding is billing's
    once, at finalization).

    ⚠ **THIS IS WHY `connections.quote_invoice_id` EXISTS.** Until it did, the
    commit knew the invoice for the length of one response and then forgot it,
    and the only durable trace was a stamp on `service_request_fees` — which
    hangs off the REQUEST, and a build raised directly has none (PO ruling
    2026-09-21). Nothing here touches a billing model, or an invoice id this
    module did not read off its own row.

    `None` while billing publishes no `invoice_detail`, so the caller states
    that it could not ask rather than drawing an empty charge table, which on
    a money screen reads as *this build was free*.

    ⚠ **A CROSS-TENANT ID IS A 404 AND NOT A NULL.** `invoice_or_404` raises
    the indistinguishable NotFound for *another tenant's bill* and *no such
    bill* alike (HR-1/G4), and that exception is allowed to travel exactly as
    `invoice_ref` above lets it travel.
    """
    fn = resolve("billing", "invoice_detail", kind="selectors")
    if fn is None or invoice_id is None:
        return None
    return dict(fn(invoice_id))


def settled_against_bills(invoice_ids: Any) -> dict[str, Any] | None:
    """**What has been PAID against these bills** — payments' own arithmetic.

        apps.payments.billing_seam.allocated_for_invoices(invoice_ids)
            -> {invoice_id: Decimal}

    The build record's `OUTSTANDING` tile is *quoted − taken*, and **only the
    second operand is in doubt**: billing owns what was billed and payments
    owns what has been allocated against it. `billing/payments_seam`'s own
    words for the split — *"Billing owns `invoices` and knows what was BILLED.
    It does not own `allocations` and cannot know what is OPEN"* — are exactly
    why this asks rather than computing.

    **THE BATCH FORM ON PURPOSE, EVEN FOR ONE BILL.** `allocated_so_far`
    beside it filters on `invoice_id` alone and leans on RLS `FORCE` for the
    tenant; `allocated_for_invoices` resolves the tenant BY NAME through
    `payments.selectors._tenant_id()` and refuses when none is set. On a money
    read, CLAUDE.md hard rule 1 wants the explicit filter first and RLS as the
    second guarantee, never the only one — and the test suite runs on SQLite,
    where RLS does not exist at all (hard-won law 14).

    A bill with NO allocation row is ABSENT from the map, which the caller
    reads as *nothing has been paid against it* — a true answer over payments'
    append-only table. Reversing rows are negative (`BR-PAY-031`), so each
    figure is the NET position and a bounced cheque re-opens the bill.

    ⚠ **`None` — NEVER AN EMPTY MAP — WHEN PAYMENTS PUBLISHES NOTHING.** An
    empty map cannot tell *nothing has been paid* from *nobody answered*, and
    substituting the first for the second on an outstanding figure is
    `DEF-127` on a screen a clerk chases money from.
    """
    fn = resolve("payments", "allocated_for_invoices", kind="billing_seam")
    if fn is None:
        return None
    return {str(key): value for key, value in fn(list(invoice_ids)).items()}


def payments_for_bills(invoice_ids: Any, *, entry_reference: str | None) -> list[dict[str, Any]] | None:
    """**Each payment behind a build's bills** — `CR-163-BRC10` item 20.

        apps.payments.selectors.payments_for_bills(invoice_ids, entry_reference=…)
            -> [{id, payment_no, posted_at, method_code, method_name,
                 confirmation, type, purpose, status, amount, applied, currency}]

    The *Paid so far* table on the New Connection detail. Payments owns the
    rows and decides membership (an allocation against one of the bills, or the
    build's own idempotency reference — see the read's docstring); nothing here
    filters, sums or rounds.

    `None` — never `[]` — while payments publishes no such read, so the screen
    says *could not ask* rather than *nothing was paid*: on a money screen the
    two must not look alike (`settled_against_bills` above, same reason).
    """
    fn = resolve("payments", "payments_for_bills", kind="selectors")
    if fn is None:
        return None
    return list(fn(list(invoice_ids), entry_reference=entry_reference))


# ── rating (plans + the unit-plan history table it owns) ────────────────────
def plan_ref(plan_id: Any) -> dict[str, Any] | None:
    """Read-only probe for the reviewed cross-module FK units → rate_plans.

    PO ruling 2026-08-11: a unit holds a PLAN (the bundle across its services),
    not one service's rate schedule. This replaced `tariff_ref`, whose model
    fallback is gone with it — rating authors `plan_ref` itself now, so there
    is nothing left to fall back FOR, and keeping a read-only model probe would
    only hide the day rating stopped publishing the selector.

    Returns the plan's `version` too, because the history row snapshots it
    (BR-CUS-013). No write ever crosses the boundary.
    """
    fn = resolve("rating", "plan_ref", kind="selectors")
    return fn(plan_id) if fn is not None else None


def assignable_plan_index() -> dict[str, Any]:
    """Lowered token (a plan's CODE **or** its NAME) → that token's verdict,
    for the units import's `Plan` column.

    ⚠ **RENAMED FROM `assignable_plan_ids_by_code` BY `DEF-771`, AND THE NAME
    WAS THE DEFECT.** The column is labelled *Plan* and accepts `plan`,
    `rate plan` and `tariff`; the index behind it held codes only, so a file
    headed with any of those and filled with plan NAMES mapped clean and loaded
    9,881 units unplanned. Rating's own docstring carries the whole reasoning,
    including why a draft and an archived plan are in the index and still
    unassignable.

    Read-only and read ONCE per run. Returns `{}` when rating is absent, which
    is the seam contract every probe here follows; the caller then flags every
    row that names a plan, which is `BR-MET-100`'s own outcome rather than a
    silent success.
    """
    fn = resolve("rating", "assignable_plan_index", kind="selectors")
    return fn() if fn is not None else {}


#: `plan_register_inputs` status vocabulary — VALUES, not prose, because the
#: completeness module maps each onto a named absence a screen groups on
#: (the `READ_ABSENT_*` discipline). `unwired` is "rating cannot answer",
#: which is NEVER read as "the plan expects nothing" (DEF-075).
PLAN_INPUTS_OK = "ok"
PLAN_INPUTS_UNWIRED = "rating_unwired"
PLAN_INPUTS_SERVICE_NOT_ON_PLAN = "service_not_on_plan"
PLAN_INPUTS_NO_VERSION = "no_version_in_force"


def plan_register_inputs(plan_id: Any, service_code: str, service_date: Any) -> dict[str, Any]:
    """Rating's pricing projection for ONE plan+service at a date — the read
    BR-MET-049's expected-register resolver derives the required channel set
    from (US-MET-018, CR-038 W1).

    Chained ENTIRELY through rating's own PUBLISHED selectors, resolved late:
    `plan_rate_schedules(plan_id)` names the plan's tariff per service (its
    docstring: *"Billing's gather step calls this to build its per-service
    pricing inputs"* — this is the same sanctioned hop), and
    `pricing_inputs(tariff, service_date)` is *"rating's answer to 'what does
    the engine need'"* — model, windows WITH their BR-RAT-067 stated channels,
    demand config — resolved at the version IN FORCE on the date (BR-RAT-007).
    The tariff row passes through this function OPAQUELY: metering never reads
    a field off it, it only hands rating's own row back to rating's own
    selector. Storage is not an interface, and none is read here.

    Returns `{"status": ..., "inputs": ...}` with the four statuses above.
    The distinctions matter and are kept apart deliberately:
      * `rating_unwired` — the selectors are absent. CANNOT ANSWER, which the
        resolver reports and never converts into "no registers expected".
      * `service_not_on_plan` — the plan genuinely names no schedule for this
        service, so it states no required set for it.
      * `no_version_in_force` — a schedule exists and no version covers the
        date (BR-RAT-007 has no fallback to today's prices, and this read
        inherits that law rather than re-deciding it).
      * `ok` — `inputs` carries rating's projection.
    """
    schedules_fn = resolve("rating", "plan_rate_schedules", kind="selectors")
    pricing_fn = resolve("rating", "pricing_inputs", kind="selectors")
    if schedules_fn is None or pricing_fn is None:
        return {"status": PLAN_INPUTS_UNWIRED, "inputs": None}
    row = next(
        (r for r in schedules_fn(plan_id) if r.get("service_code") == service_code),
        None,
    )
    if row is None:
        return {"status": PLAN_INPUTS_SERVICE_NOT_ON_PLAN, "inputs": None}
    inputs = pricing_fn(row["tariff"], service_date)
    if inputs is None:
        return {"status": PLAN_INPUTS_NO_VERSION, "inputs": None}
    return {"status": PLAN_INPUTS_OK, "inputs": inputs}


def record_unit_plan_assignment(**kwargs: Any) -> dict[str, Any] | None:
    """BR-CUS-013 dated history row. Rating owns the table (B2 r16 #6).

    WIRED 2026-08-11. This returned None from W1 until then — rating had never
    authored the function — so every plan assignment reported
    `history_recorded: false` and the unit knew only its current plan. It could
    not be written earlier: the table stores a `rate_plan_id` and the unit
    stored a TARIFF, so the foreign key would have rejected the row. The PO's
    ruling that a unit holds a PLAN is what made it writable.

    Still returns None rather than raising if rating is absent, because that is
    the seam contract every other probe here follows — but the metering caller
    now REFUSES a silent None instead of reporting it, since a plan change with
    no history row is a bill that cannot be priced.
    """
    fn = resolve("rating", "record_unit_plan_assignment")
    return fn(**kwargs) if fn is not None else None



# ═══════════════════════════════════════════════════════════════════════════
# CR-068 wave H (2026-09-04) — the CUSTOMER's view of the equipment on a unit
# ═══════════════════════════════════════════════════════════════════════════


def equipment_on_unit(unit_id: Any, *, today: Any = None) -> list[dict[str, Any]]:
    """`apps.assets.equipment_reads.equipment_on_unit(unit_id, today=…)`.

    `CWP-037`'s row — the serial on the box, where it is fitted, when it was
    fitted, the tenant's own status word and the derived next test
    (`BR-AST-007`). `metering.portal_reads.equipment_for_unit` joins the last
    read onto it, because `meter_reads` is this module's table and the registry
    is the assets module's (`B2` r4).

    ⚠ **NOT `assets_on_unit` WITH MORE KEYS** — that read answers the S15
    *Meters* cell and is called by the routes picker, the delete guard and the
    bill run's asset count, none of which want four more joins to draw a number
    they already have. `equipment_reads.py`'s own docstring records the split.

    An unwired assets module answers `[]`, the same honest degradation
    `assets_on_unit` gives: no equipment, which a screen must STATE
    (`US-CWP-043` TC-8) rather than score.
    """
    fn = resolve("assets", "equipment_on_unit", kind="equipment_reads")
    return list(fn(unit_id, today=today)) if fn is not None else []


# ═══════════════════════════════════════════════════════════════════════════
# MQ-033 (PO 2026-10-24) — identity: WHO MAY READ A ROUTE (READ ONLY)
# ═══════════════════════════════════════════════════════════════════════════
# A route's reader is assigned on Reads → cycle → Routes (`route_readers.py`).
# The candidate is a login of THIS tenant whose membership is ACTIVE and whose
# role is the field technician's. Identity owns users, roles and memberships;
# these functions READ them and write nothing (B2 §2 — `routes.assigned_to` is
# already the reviewed cross-module FK to `identity.User`).


def _field_technician_memberships() -> Any:
    from apps.identity import models as identity_models
    from core import permissions as core_permissions
    from core import tenancy as core_tenancy

    return (
        identity_models.TenantMembership.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(),
            status=identity_models.TenantMembership.STATUS_ACTIVE,
            role__code=core_permissions.FIELD_TECHNICIAN,
        )
        .select_related("user")
        .order_by("user__full_name", "user__email", "id")
    )


def field_technicians_queryset(q: str | None = None) -> Any:
    """Every ACTIVE field-technician membership of the tenant in context, by
    name; `q` matches the name or the email. A queryset, so the picker pages in
    SQL (NFR-3) and nothing caps it (NFR-5)."""
    from django.db.models import Q

    qs = _field_technician_memberships()
    term = (q or "").strip()
    if term:
        qs = qs.filter(Q(user__full_name__icontains=term) | Q(user__email__icontains=term))
    return qs


def field_technician(user_id: Any) -> dict[str, Any] | None:
    """`{id, name}` when `user_id` is an ACTIVE field technician of THIS tenant,
    else None — another tenant's user, a clerk, an invited or deactivated login
    all answer None, the same way."""
    row = _field_technician_memberships().filter(user_id=user_id).first()
    if row is None:
        return None
    return {"id": str(row.user_id), "name": row.user.full_name or row.user.email}


def user_display_names(user_ids: Any) -> dict[str, str]:
    """`{id: name}` for many users in ONE read — the name, else the email (a
    login invited and not yet named). An id this tenant does not hold is
    absent."""
    from apps.identity import models as identity_models
    from core import tenancy as core_tenancy

    ids = [value for value in set(user_ids) if value]
    if not ids:
        return {}
    return {
        str(row.id): (row.full_name or row.email or "")
        for row in identity_models.User.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), pk__in=ids
        )
    }


def notify_route_readers(changes: dict[Any, dict[str, Any]], *, actor_id: Any = None) -> None:
    """metering → work: *these readers' routes changed — ring their phones*
    (DEF-MET-10606, PO 2026-10-26 *"we will send this in notification"*).

    `changes` is `{user_id: {"gained": [{code, name}], "lost": [{code, name}]}}`.
    Scheduled with `transaction.on_commit`, so an assignment that rolls back
    pushes nobody; the callback re-enters the tenant captured NOW, because a
    job is per-tenant (B3) and the commit may land after the request's context.
    Work's ONE door for this is `apps.work.route_push.notify_routes_changed`
    (BR-WRK-002) — imported at call time, as every metering → work call is, so
    the two apps never import each other at load.
    """
    from django.db import transaction

    from core import tenancy as core_tenancy

    if not changes:
        return
    tenant_id = core_tenancy.current_tenant_id()

    def _ring() -> None:
        from apps.work import route_push

        if core_tenancy.current_tenant_id() == tenant_id:
            route_push.notify_routes_changed(changes, actor_id=actor_id)
            return
        with core_tenancy.tenant_context(tenant_id):
            route_push.notify_routes_changed(changes, actor_id=actor_id)

    transaction.on_commit(_ring)

# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-001@d76f5b4 (story+rules snapshot hash — EP-MET-01 lead story; co-packet EP-MET-02@8f2ab3c)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane) · AMENDED 2026-08-19 by story-coder (CR-017 lane — DEF-324: `enabled_service_codes` stops building the S8 screen payload to answer a one-column question; 47.3 s of a 118 s profiled provisioning run, 304 calls) · AMENDED 2026-08-22 by the CR-028 AST-W3 lane (the assets import-target seams (create/update/rollback_from_import, index + lookup reads) and the tenancy mapping-template seams (BR-AST-048))
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — seam module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ pytest tests/test_us_met_*.py 56 passed/0 skipped · tests/test_us_ast_*.py 73 passed/0 skipped (13 of the 129 are @pytest.mark.isolation, green on sqlite, deselected from the suite run and re-run under -m isolation: 13 passed, 20 postgres-only skipped) · suite `pytest tests -m "not golden and not isolation"` 566 passed, 9 skipped, 44 deselected✔ (shared tree — the concurrent rating lane's tests included; 365 was the pre-lane baseline) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently)
# exceptions: [W2 reads lane 2026-08-10] the three reads seams are WIRED now that meter_reads exists (read_reference_count / collected_read_count / last_read_completion no longer return the true-by-construction 0/None) — two existing tests that pinned the null posture were amended with the reason · `unit_is_occupied` returns None, not False, when customers exposes no active-account selector: False would flag EVERY read vacant_unit, which is a fabricated answer · `meter_by_no`/`meter_by_id`/`service_billed_uom` are READ-ONLY model probes (assets exposes no by-number selector; tenancy's services_overview omits billed_uom/conversion_factor) — same Eng disposition the rating tariff_ref probe records
# exceptions: customers/billing/rating/reads seams are DOCUMENTED and unwired — fallbacks are true-by-construction (no tables exist), never guesses · rating Tariff read falls back to a read-only django_apps.get_model probe (Eng disposition, identity precedent) · unit_plan_assignments history is rating-owned and NOT written here (reported per call)
# exceptions: [2026-08-26 CR-038 W1 lane] `plan_register_inputs` added — the BR-MET-049 resolver's read, chained through rating's PUBLISHED selectors only (`plan_rate_schedules` → `pricing_inputs`, both resolved late); the tariff row passes through OPAQUELY (handed straight back to rating's own selector, no field read). Four-status vocabulary keeps "rating cannot answer" apart from "the plan states no set" (DEF-075).
# exceptions: [DEF-1813 2026-08-28, BR-MET-710] `billable_asset_count` is the
#         ONE assets read in this module that degrades to `None` rather than to
#         an empty answer, and the asymmetry is the rule: an empty list of
#         meters reads honestly as *no meter*, but a count of `0` is a REAL and
#         BILLABLE answer (*the utility looked and this unit has no carts*), so
#         degrading to `0` would say somebody looked when nobody did and bill a
#         three-cart household $0.00 on a document that foots.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

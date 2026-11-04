# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-018 (capture a supplier invoice on S73: date · service ·
#           supplier FREE TEXT · amount · OPTIONAL volume · GL account ·
#           period — TC-1 RS-2607-0141, TC-2 the cost-only invoice, TC-5 the
#           closed-period auto-forward, TC-6/7/8/9 the refusals, TC-10
#           isolation) ·
#           US-LED-019 (the register: list · search · filter · edit while the
#           period is OPEN · VOID with reason, never delete — TC-1 the
#           $51,902.50 footer, TC-3 the volume-captured filter, TC-5 the void
#           to $51,747.50, TC-6 the delete refusal, TC-8 the OQ-203 stub)
#           Screens: S73
# Rules:    BR-LED-028 (capture, hold, reconcile, export — and process NOTHING:
#           no approvals, no payment runs, no vendor master, no ageing chase,
#           no cheque printing) · BR-LED-029 (what a captured invoice holds) ·
#           BR-LED-030 (the volume is OPTIONAL) · BR-LED-033 (a captured volume
#           carries an EXPLICIT unit) · BR-LED-034 (editable while the period is
#           OPEN; a closed-period date auto-forwards) · BR-LED-035 (void, never
#           delete; the reason is required and the row stays visible) ·
#           BR-LED-036 (every capture, edit and void writes audit_log) ·
#           BR-LED-037/038 (the GL account comes from the PROPOSED, UNSIGNED
#           cost section or from the tenant's own) · BR-TEN-038 / BR-LED-006
#           (the auto-forward) · BR-TEN-042 (the tenant currency lock) ·
#           BR-REP-006 (the service filter enumerates the LIVE service list) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money NUMERIC(18,6) +
#           CHAR(3), never float, never cents) · rule 3 (a quantity carries its
#           explicit unit) · rule 7 (every money action audits)
# Change:   CR-060 C1 / task T6 + T6a (PO ruling 2026-09-02) — a supplier cost
#           posts DR cost / CR cash when a clerk records `paid_on`. BR-LED-028
#           AMENDED that day: full accounts payable is STILL declined; a date
#           recording that payment happened elsewhere is not accounts payable.
# Tests:    06-backend/tests/test_us_led_018_capture.py ·
#           06-backend/tests/test_us_led_019_register.py ·
#           06-backend/tests/test_cr060_t6_settlement_posting.py
# Impacts:  apps/ledger/models.SupplierInvoice (the table this writes) ·
#           apps/ledger/cost_reconciliation.py (reads the live rows) ·
#           apps/ledger/exports.py (the cost section of the batch — ⚠ its
#           REGISTER-DERIVED label goes false for a settled row: CR-060 T6c,
#           NOT built here) · apps/ledger/tie_out.py (⚠ cost becomes a fourth
#           thing that can drift: CR-060 T6d, NOT built here) ·
#           apps/ledger/posting.post (the ONE journal writer — hard rule 5) ·
#           apps/ledger/close.resolve_entry_date (REUSED, never reimplemented)
# ───────────────────────────────────────────────────────
"""The payable side, CAPTURED — and processed by nothing.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module writes money rows and decides
which accounting period they land in. AI-authored 2026-08-15 under the PO ruling
of 2026-08-09. **A row in 12-governance/09-human-review-ledger.md is OWED**:
that directory is the Product Owner's to write, so the lane report names this
file and the row it needs rather than opening one on their behalf.

════════════════════════════════════════════════════════════════════════════
THE RULING THIS FILE IMPLEMENTS, IN THE PO'S OWN WORDS
════════════════════════════════════════════════════════════════════════════
PO 2026-08-12, closing OQ-188, verbatim:

    "we can make this system of record and capture Ap, AR both ; we dont have
     to process anything just capture and help Utility, Sub metering copany or
     HOA reconcile both sides as system of record"

**Capture, hold, reconcile, export — and NOTHING ELSE** (BR-LED-028). The
exclusions are stated AS RULE, not as v1 scope, so a later lane reads them as
law rather than as unbuilt features: **no approval workflow · no payment run ·
no vendor master · no supplier ageing or dunning · no cheque printing or
remittance advice · no paying anything.** Option (c), full accounts payable, was
put to the PO and DECLINED — every utility at this product's size already runs
QuickBooks or Xero, and duplicating payables here creates two sets of books that
disagree.

Three consequences you can see in the code below rather than only in prose:

  1. **`supplier_name` is a plain string with no lookup.** *"City of
     Rosenberg"* and *"City of Rosenberg - Water Dept"* are both stored as
     typed. No dedupe prompt, no merge, no vendor row (US-LED-018 TC-4). A
     payable naming no supplier cannot be reconciled against a supplier
     statement, which is why the field is required; a vendor MASTER is a
     different thing and is forbidden.
  2. **There is no `approve`, `schedule_payment`, `mark_paid` or `supplier_page`
     function**, and `refuse_processing_action` exists so that asking for one
     gets a refusal that NAMES BR-LED-028 (US-LED-018 TC-8, US-LED-019 TC-7).
     A silent absence reads as an unbuilt feature; a named refusal reads as law.
     ⚠ **AMENDED 2026-09-02 — `record_settlement` IS NOT `mark_paid`, AND THE
     DIFFERENCE IS THE 2026-09-02 RULING.** `mark_paid` belongs to a system that
     PAYS an invoice: it would move the row through a workflow this product does
     not have. `record_settlement` records that the utility's BANK moved the
     money, somewhere else, on a day a clerk read off a statement — the PO's own
     *"we can take input from Clark and close it"*. All five forbidden actions
     are still refused by name and none of them has grown a function.
  3. **`register()` returns `bulk_actions: ()`.** S73's bulk-actions cell is
     empty on purpose — a bulk action over captured payables is a payment run
     or an approval queue, and both are forbidden.

════════════════════════════════════════════════════════════════════════════
THE VOLUME IS OPTIONAL, AND THE PRICE IS PAID AT THE REPORT
════════════════════════════════════════════════════════════════════════════
BR-LED-030, PO verbatim (OQ-190): *"I dont know but we can make a provision and
make it optional"*. Nothing here refuses a cost-only invoice: CI-8's $1,845.50
of pipe and CI-9's $12,500.00 of meters go in with `volume = NULL` and the
capture says nothing about it.

What that costs is charged in `cost_reconciliation.py`, not here: BR-LED-031
makes the unaccounted-for percentage **all-or-nothing per service per period**,
because with one of five water purchases captured cost-only July's honest
**9.00%** becomes **−13.75%** — a utility that appears to have delivered more
water than it bought. **Optional at capture, all-or-nothing at report.**

What IS refused here is a half-filled pair: a volume with no unit (CLAUDE.md
rule 3 — *always with an explicit unit; never assume*) and a unit with no
volume. Omitting both is legal and is the whole point.

════════════════════════════════════════════════════════════════════════════
THE POSTING BOUNDARY — CAPTURE POSTS NOTHING; **SETTLEMENT POSTS**
════════════════════════════════════════════════════════════════════════════
⚠ **AMENDED 2026-09-02 (CR-060 C1 / task T6, PO ruling). BOTH HALVES ARE HERE
ON PURPOSE: the old boundary is not deleted, because it is the only record of
why the rule was what it was.**

**WHAT WAS RULED ON 2026-08-16 AND STILL STANDS.** OQ-200, PO verbatim: *"(b)
for R2, (a) once supplier payments exist"*. **Capturing an invoice posts
NOTHING**, and it still does not — `post_capture_to_journal` is a named no-op
today for exactly the reason it was then. The PO's reason was the rule and not
the preference: option (a) posts `DR cost-of-service / CR accounts payable`, and
BR-LED-028 forbids payment runs — so that liability **can never be drained
inside this product**. Twelve months at $3,100.00 of purchased water leaves
**$37,200.00** standing for invoices the utility settled by cheque. *A growing
false number is worse than an absent true one.*

**WHAT CHANGED ON 2026-09-02, AND WHY IT IS NOT A REVERSAL.** PO verbatim:

    "why cant to add the check that whether this is paid or unpaid and allow
     clark to udpaet it - that way we can reconcicle - again system of record we
     dont have to match we can take input from Clark and close it"

Option **(c)** — `DR cost / CR cash` — was rejected in 2026-08-16's sitting for
a *different* reason from (a): it *"asserts the invoice was paid, which is wrong
for anything unpaid"*. **Posting only when a clerk RECORDS the settlement
removes exactly that objection**, and creates no payable at all. So this is (c)
restricted to the case where its assertion is true, and it is neither of the two
things the PO declined. `record_settlement` below is that path;
`SETTLEMENT_RULING` is the sentence a screen prints.

**THE TWO STATES, IN THE CR's OWN WORDS (R8):** *"Recorded — held here, not in
the books"* and *"In the books — posted when you enter paid on: DR cost / CR
cash, one balanced entry, no payables balance ever created."*

**AND THE FIGURE THIS MOVES, STATED RATHER THAN DISCOVERED.** July's signed
trial balance is **598.69 = 598.69** (LE-1, golden test **GT-51**) and it stays
there while no row carries a `paid_on`. Settling all nine of LE-11's July
purchases — **$51,902.50** — takes it to **52,351.19 = 52,351.19** (⚠ CR-060 and the 2026-09-02 decision-log row both project **52,501.19**, which is 598.69 + 51,902.50 and is **150.00 HIGH**: a trial balance nets each account onto ONE side, LE-1 leaves 150.00 of debit in 1000 Cash, and paying suppliers credits cash so that account leaves the debit column altogether. MEASURED 2026-09-02 and corrected in the decision log; nothing signed moved — 598.69 is the signed figure and 52,501.19 was a projection, never a signature. `tests/test_cr060_t6_settlement_posting.py` asserts both numbers and the 150.00 between them). Moving LE-1's signed
figure at all takes the HUMAN-GUIDE §6 re-sign route and never an inline edit;
the re-sign is owed **when the first settlement is recorded**, not when this code
lands, because on a database with no `paid_on` set anywhere nothing posts.

Until a purchase is settled the accounting export's cost section is still
REGISTER-DERIVED and labelled so nobody adds it to a footer that does not
contain it (US-LED-021 TC-7, `exports.COST_SECTION_LABEL`). ⚠ **That label
becomes FALSE for settled rows and correcting it is CR-060 T6c**, a separate
task row this lane reports rather than builds — see `SETTLEMENT_INHERITS_T6C`.

════════════════════════════════════════════════════════════════════════════
THE AFTER-CLOSE CORRECTION — OQ-203, RULED 2026-08-16: YES, WITH A REASON
════════════════════════════════════════════════════════════════════════════
PO verbatim: **"Yes it can be corrected"** — option (b), editable with a reason
and an audit row, rather than frozen at close. `_require_after_close_reason`
enforces the condition and `_after_close_note` carries the consequence.

⚠ **THE CONSEQUENCE IS ACCEPTED AND MUST BE VISIBLE.** The export is idempotent
and a re-run is blocked (BR-LED-004), so a correction made after a batch has
left changes a reconciliation the ERP **already holds**, with no second handover
possible. The ruling's condition is that the utility be told **which exported
batch no longer matches**, so a human can fix it at the accounting system's end
— `exports.stale_batches` is that warning on S42, and building the edit without
it would be worse than freezing it.

The two rulings are one argument and must be re-read together: the correction is
safe to permit **because** capture posts nothing, so it moves no signed total.
That reasoning expires the day capture starts posting cost.

════════════════════════════════════════════════════════════════════════════
THE CLOSED-PERIOD AUTO-FORWARD IS BORROWED, NOT REBUILT
════════════════════════════════════════════════════════════════════════════
BR-LED-034 rides BR-TEN-038 and BR-LED-006 unchanged, and `close.resolve_entry_
date` is already that rule: LE-9's *"July closed Aug 5. Aug 7 a payment arrives
dated Jul 30 → posts into August automatically with an audit note"*. This module
CALLS it. A second implementation is how two callers forward the same event to
two different months, and `close.py` argues the choice of the period's first day
at length — that argument is not repeated here, it is depended on.

Note which date moves and which does not: **`invoice_date` is what the supplier
wrote and never changes**; the PERIOD is what moves. A capture dated 2026-07-30
into a closed July keeps that invoice date and lands in the August period, with
the note on its audit row.
"""

from __future__ import annotations

import math
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.ledger import chart, close, dimension_seam, models, posting, selectors, tenancy_seam
from apps.tenancy import document_models, document_store
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.pagination import filter_values
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

#: BR-LED-036 — the audit actions of the payable side, named once.
#: ⚠ AMENDED 2026-09-02 (CR-060 C1 / T6): there are now FOUR, not three.
AUDIT_CAPTURED = "supplier_invoice.captured"
AUDIT_UPDATED = "supplier_invoice.updated"
AUDIT_VOIDED = "supplier_invoice.voided"
#: `P5.11` — the supplier's own invoice attached to the purchase it settles.
#: Hard rule 7: capturing what a utility bought is a money path, and attaching
#: the evidence for it is part of that path.
AUDIT_DOCUMENT_ATTACHED = "supplier_invoice.document_attached"
#: The clerk recorded that this invoice was settled — the money action that
#: moves the books (hard rule 7). A code of its own rather than another
#: `supplier_invoice.updated`, because a month-end reviewer greps for *"what
#: posted, and who said it had been paid"* and must not have to read the
#: before/after payload of every edit to find them.
AUDIT_SETTLED = "supplier_invoice.settled"

#: The columns an OPEN-period edit may move (BR-LED-034). Deliberately a closed
#: list rather than "anything the caller passes": `status`, `void_reason`,
#: `voided_at`, `captured_by_user_id` and `tenant_id` are not editable facts,
#: and a void is its own audited action with its own required reason.
EDITABLE_FIELDS: tuple[str, ...] = (
    "invoice_date",
    "service",
    "supplier_name",
    "amount",
    "currency",
    "volume",
    "volume_unit",
    "ledger_account_id",
    "reference",
    "memo",
    # CR-060 C3 / task T4 — EDITABLE while the period is open, like every other
    # fact on the row. A building keyed onto the wrong invoice is exactly the
    # kind of correction BR-LED-034 exists for, and it moves no money: the
    # per-building recovery is a READ over this column, so re-keying it moves
    # a figure between two rows of a report and never a cent in the books.
    "premises_id",
)

#: ⚠ **`paid_on` IS DELIBERATELY NOT IN `EDITABLE_FIELDS`** (CR-060 C1 / T6,
#: 2026-09-02). Every field above is a captured FACT a clerk may re-type while
#: the period is open, and moving one of them moves no money. Recording a
#: settlement POSTS `DR cost / CR cash` through the ledger, needs the moment the
#: clerk acted (BR-TEN-043 — nothing here reads a clock), and writes its own
#: audit action. It is its own audited act, exactly as a VOID is, and it is
#: reached through `record_settlement` — so a generic `edit(paid_on=…)` is
#: refused by name rather than quietly moving the books through the edit form.
SETTLEMENT_FIELD = "paid_on"

#: The register's sortable columns (the S73 capability row: *"date, supplier,
#: service, amount, volume"*), mapped to their ORM fields.
SORTABLE: dict[str, str] = {
    "date": "invoice_date",
    "supplier": "supplier_name",
    "service": "service",
    "amount": "amount",
    "volume": "volume",
}

#: S73's default sort — *"invoice date desc"*.
DEFAULT_SORT = "-date"

#: IS-3 — server-side search needs at least two characters, so a single
#: keystroke does not scan the table.
MIN_SEARCH_CHARS = 2

#: `NFR-3`'s page. 25 is the size `BR-SHL-011` gives every other list in the
#: product, so a clerk moving between Finance tabs meets one pager, not five.
DEFAULT_PAGE_SIZE = 25
#: The ceiling a caller may ask for. It exists so `?page_size=100000` cannot be
#: used to ask for the unpaginated read this page contract replaced — which is
#: `NFR-5`'s shape: no hard cap on the DATA, a bound on one REQUEST.
MAX_PAGE_SIZE = 200

#: ⚠ REPORTED, NOT ENFORCED HERE (US-LED-018 TC-6, third clause). BR-LED-025
#: refuses a POSTING that carries more than two decimals, *"naming the amount
#: and the caller"* — and that refusal lives at the ledger's posting boundary,
#: which is STUBBED under OQ-200. US-LED-018 §7 is explicit about what THIS
#: story does with the number: *"the amount is stored exactly as keyed at six
#: decimals and is never rounded by the ledger, because rounding is the caller's
#: job and happens once at finalization"*. So a three-decimal amount is STORED
#: EXACTLY and comes back carrying this problem code — never silently rounded
#: (two rounding sites is how two figures start disagreeing) and never silently
#: accepted either. The day OQ-200 closes as reading (a), such a capture becomes
#: unpostable and this code is the warning that was already on the row.
AMOUNT_PRECISION_WARNING = "amount_carries_more_than_two_decimals"

#: ⚠ REPORTED (field map D-10 / BR-LED-037). Every capture result and every
#: register row carries this when its GL account is listed in
#: `chart.PENDING_FINANCE_RE_SIGN_COST`, because no column on `ledger_accounts`
#: says *"seeded pending a finance signature"* and US-LED-017 TC-5 forbids any
#: surface presenting one as signed.
#:
#: ⚠ **NO CAPTURE CARRIES IT TODAY (amended 2026-08-18).** This said the note
#: rides "one of the eight PROPOSED cost codes"; the Product Owner finance
#: re-signed all eight that day — their codes and names, in plain English, with
#: no dollar figure attached to any of them and with B4/B5 ❄️ FROZEN and
#: un-edited — so the register is empty and a capture against 5110 now comes
#: back clean. Flagging a ratified account would send a clerk to a reviewer for
#: nothing. The mechanism is held on a synthetic unsigned code in
#: `tests/test_us_led_017_cost_chart.py`.
UNSIGNED_ACCOUNT_NOTE = "gl_account_is_not_finance_signed"


class CostCaptureError(RuntimeError):
    """A capture, edit or void the ledger refuses, with the reason and the rule.

    Same shape as `posting.PostingError` and `exports.ExportError`: no HTTP
    surface here, and the API layer decides what a browser sees. `br_ref` is
    carried so a refusal that exists BY RULE (BR-LED-028's forbidden workflows)
    can be told apart from one that exists because a field was wrong — the first
    is law a later lane must not "fix", the second is a typo.
    """

    def __init__(self, message: str, *, br_ref: str | None = None):
        super().__init__(message)
        self.br_ref = br_ref


def _tenant_id() -> UUID:
    """CLAUDE.md rule 1 — no tenant table is touched without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _rows() -> Any:
    """Every supplier invoice of the CURRENT tenant, and no other.

    The explicit `tenant_id` filter is the app-layer half of CLAUDE.md rule 1.
    RLS FORCE (`db/rls_ledger_supplier_invoices.sql`) is the other half and is
    the one that holds when this filter is the thing that is buggy — but the
    developer database is SQLite and has no RLS at all, so this filter is the
    ONLY protection there and is never omitted for brevity.
    """
    return models.SupplierInvoice.objects.filter(tenant_id=_tenant_id())


def _tenant_currency() -> str | None:
    """The tenant's declared book currency, through tenancy's published read.

    BR-TEN-042's currency lock: a tenant declares one currency and its money
    rows are in it. Read rather than assumed — `exports._currency` and
    `apps/ledger/wire.py` take the same read for the same reason, and DEF-081
    is the mixed-currency lesson that made it non-optional.

    `None` when tenancy publishes nothing: the capture then requires the caller
    to state a currency and does NOT compare it to anything, because "the tenant
    has not declared one" and "the tenant declared USD" are different facts.
    """
    from importlib import import_module

    try:
        tenancy_selectors = import_module("apps.tenancy.selectors")
    except ImportError:  # pragma: no cover — defensive
        return None
    fn = getattr(tenancy_selectors, "regional_settings", None)
    if not callable(fn):
        return None
    value = (fn() or {}).get("currency")
    return str(value) if value else None


# ═══════════════════════════════════════════════════════════════════════════
# The cost-category vocabulary (BR-LED-029 · BR-REP-006)
# ═══════════════════════════════════════════════════════════════════════════
def cost_category_vocabulary() -> tuple[str, ...]:
    """The tenant's LIVE service list, plus O&M and Infrastructure.

    BR-LED-029, from OQ-188 verbatim: *"electric purchases   Water purchase
    O&M cost, infra cost"* — the PO's own five categories generalise to *the
    services this tenant sells* plus the two that belong to no service.

    **LIVE, never hardcoded** (BR-REP-006): a tenant that does not sell gas
    cannot capture a gas purchase, and a tenant that switches broadband on today
    can capture one tomorrow with nothing redeployed. The service half comes
    through `tenancy_seam.enabled_service_codes`, which REFUSES rather than
    answering `()` when tenancy publishes nothing — see that module's docstring
    for why an empty tuple would be the dangerous answer.

    ⚠ **AMENDED 2026-09-01 (CR-060 C15 · task T5) — THE NON-SERVICE HALF IS
    SIXTEEN, NOT TWO.** It was the tenant's services plus O&M and Infrastructure
    and nothing else, so **a tenant could not record payroll, insurance, a legal
    bill, postage, fuel or rent anywhere in this product** — the promise of
    *"everything in one place"* was not true. The list now covers five
    operating-statement groups and is declared once, in
    `chart.COST_CATEGORY_SPECS`. The SERVICE half is unchanged and still live.
    """
    return tuple(tenancy_seam.enabled_service_codes()) + chart.COST_CATEGORIES


def cost_category_catalog() -> tuple[dict[str, Any], ...]:
    """The vocabulary WITH its grouping, its cautions and its recovery flag.

    Served BESIDE the flat `categories` list rather than replacing it: a caller
    reading a list of strings keeps working, and a surface that wants to group
    the picker or print the payroll caution has somewhere to read it from.
    **The flat list stays the contract; this is additive.**

    A SERVICE row carries `group: "cost_of_service"` and
    `enters_recovery_denominator: True` — those categories ARE the tenant's live
    service codes (BR-REP-006), they are the ones that carry a volume, and they
    are what bought-versus-billed is computed over.
    """
    rows: list[dict[str, Any]] = []
    for code in tenancy_seam.enabled_service_codes():
        rows.append(
            {
                "code": code,
                # Decision log 2026-08-28, judgment 2: *"where a name is missing,
                # the CODE is capitalised — `.capitalize()`, never `.title()`"*.
                # `storm_water` → `Storm water`, which is the catalogue's own
                # spelling; `.title()` would invent *Storm Water*, a second name
                # for one service. The picker showed the bare code until
                # 2026-09-01 and the categories beside it now carry real names,
                # so leaving these raw would read as two different kinds of
                # thing in one list.
                "label": _readable(code),
                "group": "cost_of_service",
                "group_label": "Cost of service",
                "enters_recovery_denominator": True,
                "caution": None,
                "account_code": chart.cost_account_code_for_service(code),
            }
        )
    for spec in chart.COST_CATEGORY_SPECS:
        rows.append(
            {
                "code": spec.code,
                "label": spec.account_name,
                "group": spec.group,
                "group_label": spec.group_label,
                "enters_recovery_denominator": spec.enters_recovery_denominator,
                "caution": spec.caution,
                "account_code": spec.account_code,
            }
        )
    return tuple(rows)


def refused_category_catalog() -> tuple[dict[str, Any], ...]:
    """The capital names this tab refuses, each with the reason it points at.

    **Published rather than merely enforced.** A surface that only ever produces
    a refusal after the clerk has typed a whole invoice has taught them nothing;
    the picker can offer these as unavailable with the sentence that says where
    the money goes instead, which is the *"this looks like equipment: record it
    on the asset instead"* CR-060 §6 asks for. Same posture as
    `FORBIDDEN_ACTIONS` — a named refusal reads as law, a silent absence reads
    as an unbuilt feature.
    """
    return tuple(
        {"code": code, "label": _readable(code), "reason": reason, "record_on": "asset"}
        for code, reason in chart.CAPITAL_CATEGORIES.items()
    )


def _readable(code: str) -> str:
    """A code as a person reads it — `admin_office_rent` → `Admin office rent`.

    `.capitalize()`, never `.title()`, per the decision log of 2026-08-28
    (judgment 2): `storm_water` → `Storm water`, which is the service
    catalogue's own spelling, where `.title()` would invent *Storm Water* — a
    second name for one thing, which is the drift a catalogue exists to prevent.

    Used ONLY where no real name exists. A cost CATEGORY has one — the chart
    account's name, which is what the picker shows — so this is reached by the
    service half and by the refused capital names, and by nothing else.
    """
    return code.replace("_", " ").capitalize()


def _refuse_capital_category(service: str) -> None:
    """**A capital-asset category is refused BY NAME, pointing at the asset.**

    ⚠ **CR-060 C15 · task T5, and it lands BEFORE the settlement posting (T6)
    deliberately.** *A miscategorised row is a tidy-up until costs post, and a
    correction afterwards* — once `paid_on` triggers `DR cost / CR cash`, a
    capitalised asset recorded as a cost is a wrong number in a trial balance,
    and by the time anyone reads it, a signed figure in a closed month rather
    than a report anybody can re-run.

    **The damage, in the CR's own arithmetic:** a $40,000 truck recorded as an
    expense overstates this year's costs by $40,000, understates the next five
    years' by the depreciation that never happens, **and leaves the asset off
    the balance sheet entirely.** It is the most common bookkeeping error at
    this size of utility.

    **And it needs no new mechanism, because capital spending already has a
    home:** the assets module carries `purchase_cost`, `depreciation_method`,
    `expected_life_years` and a computed `book_value_amount`. This refusal NAMES
    that home instead of quietly accepting a category that would put the money
    in the wrong place.

    Raised BEFORE `_refuse_unknown_category`, because *"that is not a category"*
    and *"that is a category we refuse, and here is where it goes"* are
    different sentences and only the second is useful.

    ⚠ **`infrastructure` IS NOT REFUSED**, even though the fixture's CI-9 is
    $12,500.00 of meters. That category is live and rows point at it;
    re-categorising money a tenant has already captured is not this change's to
    do, and it would move a figure in a period that may already have been
    exported.
    """
    reason = chart.CAPITAL_CATEGORIES.get(service)
    if reason is None:
        return
    raise CostCaptureError(
        f"{service!r} is CAPITAL SPENDING and is refused here by name — {reason}. Record it "
        "on the asset (Assets → the meter, vehicle or plant item), not on this tab. "
        "BR-LED-029, as amended 2026-09-01: the cost vocabulary widened to sixteen operating "
        "categories and gained this refusal in the same change, and the refusal is the point — "
        "a category that quietly accepted a capitalised asset would misstate both the year's "
        "costs and the balance sheet.",
        br_ref="BR-LED-029",
    )


def _refuse_unknown_category(service: str) -> None:
    # ⚠ ORDER MATTERS. A capital name is a name we KNOW and refuse with a
    # pointer; an unknown name is a typo. Reversing these two lines would answer
    # "that is not a category" to a clerk who needs "record it on the asset".
    _refuse_capital_category(service)
    vocabulary = cost_category_vocabulary()
    if service in vocabulary:
        return
    groups = sorted({spec.group_label for spec in chart.COST_CATEGORY_SPECS})
    raise CostCaptureError(
        f"{service!r} is not a cost category this tenant can capture against. BR-LED-029 makes "
        "the vocabulary the tenant's LIVE service list plus the non-service categories, which "
        f"since 2026-09-01 (CR-060 C15) cover {len(chart.COST_CATEGORIES)} codes in these "
        f"groups: {', '.join(groups)}. This tenant's list is {vocabulary}. The SERVICE half is "
        "read live and never hardcoded (BR-REP-006), so a service switched on in Settings "
        "appears here with nothing redeployed — and a service the tenant does not sell cannot "
        "be captured against by accident.",
        br_ref="BR-LED-029",
    )


# ═══════════════════════════════════════════════════════════════════════════
# Money and quantity validation (CLAUDE.md rules 2 and 3)
# ═══════════════════════════════════════════════════════════════════════════
def _clean_amount(amount: Any) -> Decimal:
    """A Decimal, or a refusal naming rule 2. **Never a coercion.**

    A float is REFUSED rather than converted, and that is deliberate: converting
    it would hide the place where money became a binary fraction, and the place
    is what a reviewer needs. `apps/payments/billing_seam._as_decimal` refuses
    for the same reason, in the same words.

    An `int` is accepted (`Decimal(1240)` is exact and `1240` is a legitimate
    keying of $1,240.00) — but a float `1240.0` is not, because 1240.0 and
    1240.005 are the same TYPE and only one of them is safe.
    """
    if isinstance(amount, float):
        raise CostCaptureError(
            f"the amount arrived as a float ({amount!r}). CLAUDE.md rule 2 / DB-3: money is "
            "NUMERIC(18,6) with a CHAR(3) currency — never float and never cents. It is refused "
            "rather than converted, because converting it would hide the place where money "
            "became a binary fraction, and that place is the defect.",
            br_ref="BR-LED-029",
        )
    if isinstance(amount, Decimal):
        cleaned = amount
    elif isinstance(amount, int) and not isinstance(amount, bool):
        cleaned = Decimal(amount)
    else:
        raise CostCaptureError(
            f"the amount must be a Decimal (money is NUMERIC(18,6), CLAUDE.md rule 2); got "
            f"{type(amount).__name__}.",
            br_ref="BR-LED-029",
        )
    if cleaned <= 0:
        raise CostCaptureError(
            f"a captured supplier invoice must carry a POSITIVE amount; got {cleaned}. An "
            "invoice for nothing is not an invoice, and a negative one is a supplier CREDIT "
            "NOTE — which has NO PATH in this product today and is named rather than assumed "
            "(workbook V-12, EP-LED-06's parked variations). Capturing it as a negative "
            "purchase would silently reduce a bought-cost total nobody asked to reduce.",
            br_ref="BR-LED-029",
        )
    return cleaned


def _clean_currency(currency: Any) -> str:
    """A CHAR(3) code, uppercased, matching the tenant's lock if it has one."""
    text = str(currency or "").strip().upper()
    if len(text) != 3 or not text.isalpha():
        raise CostCaptureError(
            f"the currency must be a three-letter CHAR(3) code; got {currency!r}. CLAUDE.md "
            "rule 2 / DB-3 pairs every money column with one, and an amount with no currency is "
            "a number nobody can add up — US-LED-018 TC-6 refuses exactly this.",
            br_ref="BR-LED-029",
        )
    declared = _tenant_currency()
    if declared and text != declared.upper():
        raise CostCaptureError(
            f"this tenant's books are kept in {declared.upper()} and the capture states {text}. "
            "BR-TEN-042 locks a tenant to one currency, and DEF-081 is what a mixed-currency "
            "total costs: two currencies summed into one footer is a figure that is wrong in "
            "both. Refused, not converted — no exchange rate is signed anywhere in this product "
            "(workbook V-10).",
            br_ref="BR-TEN-042",
        )
    return text


def _clean_premises(premises_id: Any) -> str | None:
    """CR-060 C3 / task T4 — the building, or `None`, and never someone else's.

    **BLANK IS A REAL ANSWER AND IS NOT AN ERROR.** A utility running one
    distribution system has no building to name, and after T5 most of the
    vocabulary (payroll, insurance, rent, the utility's own taxes) has none by
    nature. `""` from an untouched form field means the same thing as absent —
    the same shape `volume` already takes for BR-LED-030.

    **A BUILDING THAT IS NOT THIS TENANT'S IS A REFUSAL, NOT A NULL** (CLAUDE.md
    rule 1). Silently dropping it would file the purchase tenant-wide and the
    clerk would never learn that the building they picked did not take; and the
    scoping check itself is metering's, resolved through the seam, never
    re-implemented here (BR-TEN-013).
    """
    if premises_id is None or str(premises_id).strip() == "":
        return None
    try:
        dimension_seam.premises_label_or_refuse(premises_id)
    except LookupError as problem:
        raise CostCaptureError(
            "that building is not in this utility's premises register, so the purchase cannot "
            "be filed against it. A cost with no building is lawful — leave it blank — but a "
            "cost against a building nobody here owns would put money on a per-building "
            "recovery row that no clerk could ever go and look at.",
            br_ref="BR-LED-029",
        ) from problem
    return str(premises_id)


def _clean_volume(volume: Any, volume_unit: Any) -> tuple[Decimal | None, str | None]:
    """`(volume, unit)` — both, or neither. CLAUDE.md rule 3 + BR-LED-030.

    Omitting BOTH is legal and is BR-LED-030's whole point (*"nothing refuses a
    cost-only invoice"*). Supplying one without the other is refused, because a
    quantity with no unit is what rule 3 forbids outright and a unit with no
    quantity is a half-filled field that would suppress a percentage for no
    reason.

    ⚠ **THE UNIT IS FREE TEXT AND THAT IS OQ-201, OPEN.** No signed document
    enumerates the purchase-side units per service, and whether a conversion
    factor may be applied is the same question. So the unit is normalised only
    by stripping whitespace — NOT lowercased, because `MMBtu` and `kWh` carry
    meaning in their capitals — and the reconciliation compares it to the billed
    unit as an exact string. Nothing converts.
    """
    unit = str(volume_unit).strip() if volume_unit is not None else ""
    if volume is None and not unit:
        return None, None
    if volume is None:
        raise CostCaptureError(
            f"a unit ({unit!r}) was given with no volume. Half a quantity is not a quantity — "
            "omit BOTH for a cost-only invoice, which is entirely lawful (BR-LED-030, PO "
            'verbatim: "I dont know but we can make a provision and make it optional").',
            br_ref="BR-LED-030",
        )
    if not unit:
        raise CostCaptureError(
            f"a volume ({volume}) was given with NO UNIT. CLAUDE.md rule 3: consumption is "
            "always recorded with an explicit unit and never assumed — 400,000 of water is "
            "gallons or litres or cubic feet and the difference is a factor of 264. The unit is "
            "not inferred from the service, because the same service is bought in different "
            "units by different utilities (BR-LED-033). Omitting BOTH volume and unit is legal "
            "(BR-LED-030); omitting one is not.",
            br_ref="BR-LED-033",
        )
    if isinstance(volume, float):
        raise CostCaptureError(
            f"the volume arrived as a float ({volume!r}). It is stored NUMERIC(18,6) beside the "
            "money for the same reason money is: 1,000,000 gallons that becomes 999,999.99999 "
            "in transit turns a clean 9.00% loss figure into a number with a tail nobody can "
            "explain. Refused rather than converted.",
            br_ref="BR-LED-033",
        )
    if isinstance(volume, Decimal):
        quantity = volume
    elif isinstance(volume, int) and not isinstance(volume, bool):
        quantity = Decimal(volume)
    else:
        raise CostCaptureError(
            f"the volume must be a Decimal; got {type(volume).__name__}.", br_ref="BR-LED-033"
        )
    if quantity < 0:
        raise CostCaptureError(
            f"a captured volume cannot be negative; got {quantity}.", br_ref="BR-LED-033"
        )
    return quantity, unit


def _amount_problems(amount: Decimal) -> tuple[str, ...]:
    """`AMOUNT_PRECISION_WARNING` when the amount carries more than 2dp.

    Reported, never rounded and never refused here — see the constant's own
    comment for the argument and for which rule owns the refusal.
    """
    exponent = amount.as_tuple().exponent
    if isinstance(exponent, int) and exponent < -2 and amount != amount.quantize(Decimal("0.01")):
        return (AMOUNT_PRECISION_WARNING,)
    return ()


# ═══════════════════════════════════════════════════════════════════════════
# The GL account (BR-LED-037 / BR-LED-038 — PROPOSED and UNSIGNED)
# ═══════════════════════════════════════════════════════════════════════════
def default_account_for(service: str, actor: Any = None) -> Any:
    """The account this category's purchases START pointing at, or None.

    A DEFAULT, exactly as `SERVICE_REVENUE_ACCOUNTS` is (BR-LED-038, from
    BR-BIL-067 verbatim: *"you create an account, but allow tenant user to
    override it"*). `None` is a real answer: four catalog services carry no
    proposed cost mirror, and a tenant may have deactivated the seeded one.

    ⚠ **AMENDED 2026-09-01 — A CATEGORY'S ACCOUNT IS MINTED ON FIRST USE, AND
    THAT IS HARD-WON LAW 4 RATHER THAN A CONVENIENCE.** `seed_chart_of_accounts`
    runs at PROVISIONING and nowhere else, so CR-060's fourteen new categories
    would have appeared in the picker of every tenant already live **with no
    account in their chart to point at** — the capture would refuse and tell
    them to pick an account that does not exist. `services.ensure_cost_category_
    account` is the lookup-and-top-up path `ensure_service_revenue_accounts`
    already uses to mint 5140 the day a tenant enables Gas (BR-LED-038), applied
    to a category. It creates the row marked UNSIGNED, audits the creation, and
    **does not resurrect an account the tenant deactivated** (IS-1, seed rule 1:
    the code stays theirs, so `None` comes back and the clerk picks one).
    """
    if service in chart.COST_CATEGORIES:
        existing = selectors.cost_account_for_category(service)
        if existing is not None:
            return existing
        # Imported HERE rather than at module scope: `apps/ledger/services.py`
        # is the chart writer and importing it at load time would be a cycle.
        # The dependency is one-way at import and two-way only at call time —
        # the same shape `_after_close_note` uses for `exports`.
        from apps.ledger import services as ledger_services

        return ledger_services.ensure_cost_category_account(service, actor)
    return selectors.cost_account_for_service(service)


def _resolve_account(service: str, ledger_account_id: Any, actor: Any = None) -> Any:
    """The account to classify this purchase to, or a refusal that names why."""
    if ledger_account_id is not None:
        account = (
            models.LedgerAccount.objects.filter(
                tenant_id=_tenant_id(), pk=ledger_account_id, deleted_at__isnull=True
            )
            .order_by("code")
            .first()
        )
        if account is None:
            raise CostCaptureError(
                f"no live chart account {ledger_account_id!r} belongs to this tenant. A "
                "deactivated account is not a valid target either (IS-1 deactivate-first: an "
                "account a tenant has retired is one they have said stop using).",
                br_ref="BR-LED-029",
            )
    else:
        account = default_account_for(service, actor)
        if account is None:
            raise CostCaptureError(
                f"no GL account was given and none is seeded for {service!r}, so this capture "
                "has nowhere to be classified. BR-LED-028 makes the chart the ONLY place a "
                "captured cost is classified — there is no vendor master and no other "
                "classification anywhere in the product. Two lawful reasons this happens and "
                "both need a human: BR-LED-037's PROPOSED section names cost mirrors for six "
                f"services and not ten ({sorted(chart.SERVICE_COST_ACCOUNTS)}), so solar, "
                "battery, storm_water and thermal_heat have no default; and a tenant may have "
                "deactivated the seeded account, in which case the code stays theirs and "
                "nothing here resurrects it. Pick an account (apps.ledger.selectors."
                "cost_accounts lists them, each with its `unsigned` marker).",
                br_ref="BR-LED-038",
            )
    if account.type != "expense":
        raise CostCaptureError(
            f"account {account.code} · {account.name} is a {account.type} account, and a "
            "captured supplier invoice is a COST. Classifying a purchase to revenue or to a "
            "liability would put it on the wrong side of every report built over the chart.",
            br_ref="BR-LED-029",
        )
    return account


# ═══════════════════════════════════════════════════════════════════════════
# THE POSTING BOUNDARY — CAPTURE POSTS NOTHING (OQ-200, 2026-08-16);
# **SETTLEMENT POSTS** (CR-060 C1 / T6, PO ruling 2026-09-02)
# ═══════════════════════════════════════════════════════════════════════════
#: PO 2026-08-16, closing OQ-200, verbatim: *"(b) for R2, (a) once supplier
#: payments exist"*. Capture is a FILING and RECONCILIATION feature and moves no
#: signed total. Named as a constant so a screen, a CSV header, an export label
#: and a test all print one string rather than four paraphrases.
#:
#: ⚠ **STILL TRUE AFTER 2026-09-02, AND THE VALUE IS DELIBERATELY UNCHANGED.**
#: The ruling of that day did not make a CAPTURE post; it made a SETTLEMENT
#: post. A screen or a CSV keyed on this string is still keyed on a true fact.
POSTING_RULED_NONE = "capture_posts_nothing_in_r2"

#: ⚠ **SUPERSEDED 2026-09-02 — KEPT, DATED, BECAUSE IT IS THE ONLY RECORD OF
#: THE CONDITION THE OLD RULING ATTACHED TO ITSELF.** It said: *the day a
#: supplier-PAYMENT path ships, option (a) becomes the ruling*. **No
#: supplier-payment path has shipped and none will** — BR-LED-028 still forbids
#: one — so that trigger never fired. What happened instead is that the PO ruled
#: option (c), restricted to the case where its assertion is true, and option
#: (a)'s accounts payable is created at no point. `SETTLEMENT_RULING` below is
#: the live sentence; this one is history and is not served anywhere.
POSTING_RULING_SUPERSEDED = (
    "SUPERSEDED 2026-09-02 (CR-060 C1 / T6). It read: 'a supplier-payment path ships. PO "
    "2026-08-16 (OQ-200): (b) for R2, (a) once supplier payments exist. On that day capture "
    "posts DR cost-of-service / CR accounts payable...'. That trigger never fired and cannot: "
    "BR-LED-028 still forbids a payment run. The PO instead ruled that a cost posts DR cost / "
    "CR cash when a clerk RECORDS that it was settled, which creates no payable at all."
)

#: The live sentence, served on the register so a screen prints the ledger's own
#: words rather than composing a paraphrase that drifts from them (the same
#: reason `POSTING_RULED_NONE` is a constant).
SETTLEMENT_RULING = (
    "Capturing a supplier invoice still posts nothing. The books move when you record that "
    "the invoice was PAID: entering 'Paid on' posts one balanced entry, DR the cost account / "
    "CR cash, and no payables balance is ever created. PO ruling 2026-09-02: 'why cant to add "
    "the check that whether this is paid or unpaid and allow clark to udpaet it - that way we "
    "can reconcicle - again system of record we dont have to match we can take input from "
    "Clark and close it'. Your entry is the authority; nothing has to match a bank feed."
)

#: The `br_ref` a refusal from the LEDGER carries back out of this module, so
#: the API classifies it once instead of matching on message text. The ledger's
#: own sentence is passed through verbatim — it names the amount, the account or
#: the rule, and re-wording it here would lose the only detail a clerk can act
#: on. The commonest case by far is BR-LED-025: an amount captured with three
#: decimals is stored exactly (US-LED-018 §7) and is UNPOSTABLE, and the row has
#: been carrying `amount_carries_more_than_two_decimals` since the day it was
#: captured saying so.
SETTLEMENT_LEDGER_REFUSAL_REF = "BR-LED-025"

#: ⚠ **WHAT TWO OTHER CR-060 TASK ROWS INHERITED FROM THIS ONE — BOTH NOW
#: BUILT, 2026-09-02.** Named as constants, and asserted by
#: `tests/test_cr060_t6_settlement_posting.py`, so that "we told somebody" was a
#: thing a grep could find rather than a sentence in a lane report nobody kept.
#: They are KEPT rather than deleted, and each now records what the hand-off
#: turned out to cost — the T6c one was not a tidy-up, it was `DEF-3380`.
SETTLEMENT_INHERITS_T6C = (
    "CR-060 T6c — BUILT 2026-09-02. The accounting export's cost section was labelled "
    "REGISTER-DERIVED (exports.COST_SECTION_LABEL) precisely BECAUSE nothing posted, and from "
    "the first settlement that label was FALSE for the settled rows: the same money left in "
    "one batch twice, once as a journal-derived debit and once as a register row saying it "
    "was not in the books (DEF-3380, measured at 4,340.00 of purchased water against 3,100.00 "
    "bought). The section now carries only invoices with no paid_on and states the settled "
    "count and total beside them."
)
SETTLEMENT_INHERITS_T6D = (
    "CR-060 T6d — BUILT 2026-09-02. The S36 tie-out panel proved receivables, deposits and tax "
    "payable against the books. Cost is the fourth thing that can drift: the supplier "
    "register's settled total against what those settlements posted. Until that row existed a "
    "divergence between them surfaced nowhere, which is OQ-1350's own argument. It is "
    "`tie_out.SUBLEDGER_COST` now, and it blocks a release like every other row."
)

#: The settlement's source document and event, for `posting.posting_key`. The
#: replay guard (hard rule 6) is composed from these two and the invoice id, so
#: a second settlement of one invoice is a NO-OP by construction rather than by
#: a check somebody has to remember to write.
SETTLEMENT_SOURCE_TYPE = "supplier_invoice"
SETTLEMENT_EVENT = "settled"


def post_capture_to_journal(invoice: Any, *, actor: Any = None) -> None:
    """**RULED: a capture posts NOTHING to the books in R2.** Deliberately a
    no-op, and deliberately still a named function.

    PO 2026-08-16, closing OQ-200, verbatim: **"(b) for R2, (a) once supplier
    payments exist"**.

    **THE REASON THE PO GAVE, which is the rule and not the preference.**
    Option (a) would post `DR cost-of-service / CR accounts payable`, and
    BR-LED-028 forbids payment runs — so **that liability can never be drained
    inside this product**. Twelve months at $3,100.00 of purchased water would
    leave **$37,200.00** standing for invoices the utility actually settled by
    cheque. *A growing false number is worse than an absent true one.*

    So: the books stay exactly as finance signed them, July's trial balance
    stays **598.69 = 598.69**, and the reconciliation (US-LED-020) and the
    accounting export (US-LED-021) both still work — the export section is
    REGISTER-DERIVED and labelled as such, which is `exports.COST_SECTION_LABEL`.

    **Why this is a function that does nothing rather than no function at all.**
    A deleted boundary is a boundary nobody can find again, and this one earned
    its keep: `tests/test_us_led_018_capture.py` asserted that this call posts
    zero journal lines, and when the boundary moved on 2026-09-02 that test was
    standing in exactly the right place with the ruling written beside it. It
    was **REWRITTEN and not deleted** (CR-060 T6a), which is why both halves of
    the argument survive.

    ⚠ **AMENDED 2026-09-02 — WHAT THIS FUNCTION IS *NOT*.** It is not the
    posting path. `record_settlement` is, and it posts `DR cost / CR cash` on the
    day a clerk records the invoice was PAID. This function is the CAPTURE
    boundary and a capture still posts nothing: an invoice that has arrived and
    has not been paid is a filing record, exactly as the PO ruled in 2026-08-16's
    sitting. **Do not "finish" this stub** — there is nothing missing from it.

    Also load-bearing: **no `2500 Accounts payable` is proposed in
    `chart.COST_OF_SERVICE_CHART`**, and under BOTH rulings none is needed. That
    absence was deliberate before 2026-08-16 (proposing it would have smuggled an
    answer into the chart), stayed correct after it, and stays correct now: the
    settlement credits CASH, so no payable is created at any point.
    """
    return None


#: The audit marker an after-close correction carries. PO 2026-08-16 closing
#: OQ-203, verbatim: **"Yes it can be corrected"** — option (b), *editable with
#: a reason and an audit row*, rather than frozen at close.
AFTER_CLOSE_CORRECTION = "corrected_after_period_close"

#: The problem code a corrected row carries when the money it moved has ALREADY
#: LEFT for an accounting system. Not a nicety — see `_after_close_note`.
EXPORT_ALREADY_HANDED_OVER = "exported_batch_no_longer_matches"


def _require_after_close_reason(reason: Any, action: str) -> str:
    """**RULED — OQ-203 CLOSED 2026-08-16. The correction is allowed; the
    REASON is the condition that makes it lawful.**

    PO verbatim: *"Yes it can be corrected"*. Option (b): editable with a reason
    and an audit row rather than frozen at close.

    **Why the reason is mandatory here and merely useful on an open-period
    edit.** An open-period edit changes a figure nobody outside this product has
    seen. An after-close edit changes a figure a month-end has already been
    signed off over and, very often, that an ERP is already holding — so the
    audit row is the only artifact that can ever explain the difference to
    whoever reconciles the two. A reasonless after-close correction is a
    discrepancy with no author.

    **Why this closure was safe to make at all, in the PO's own reasoning:**
    capture POSTS NOTHING in R2 (OQ-200, ruled the same day), so an after-close
    correction *moves no signed total* — it corrects a filing record and its
    export.

    ⚠ **AND THAT REASONING NOW HAS AN EDGE, NAMED 2026-09-02.** From the day a
    purchase is SETTLED its cost IS in the books, so an after-close correction to
    one of the fields the settlement entry copied would move a posted figure.
    That case is not decided here and is not silently allowed: `_refuse_if_
    settled` refuses it, citing the open question, and the correction of every
    other field on a settled invoice is untouched. The reasoning above still
    holds in full for an UNSETTLED purchase, which is every row in the product
    until a clerk types a date.
    """
    cleaned = str(reason or "").strip()
    if cleaned:
        return cleaned
    raise CostCaptureError(
        f"an {action} after the invoice's period has CLOSED needs a REASON. PO 2026-08-16 "
        "(OQ-203), verbatim: 'Yes it can be corrected' — the correction is lawful and the "
        "reason is the condition, because a month-end has already been signed off over this "
        "figure and the audit row is the only artifact that can explain the difference to "
        "whoever reconciles the two. State what is being corrected, and why.",
        br_ref="BR-LED-034",
    )


def _after_close_note(row: Any, action: str, reason: str) -> dict[str, Any]:
    """The audit fragment AND the screen warning for an after-close correction.

    ⚠ **THE CONSEQUENCE THE PRODUCT OWNER ACCEPTED, AND WHY IT MUST BE VISIBLE
    RATHER THAN MERELY TRUE.** The accounting export is idempotent and a re-run
    is blocked (BR-LED-004) — a utility must never receive one month twice. So a
    correction made AFTER a batch has left changes a reconciliation the ERP
    **already holds**, with no second handover possible. The PO accepted that
    consequence explicitly; what the ruling requires in exchange is that the
    utility be **told which exported batch no longer matches, so a human can fix
    it at the ERP end**. *Building the edit without that warning would be worse
    than freezing it*, and the registry row says so in those words.

    This function is the "told" half at the point of correction.
    `exports.stale_batches` is the same fact read from the export screen's own
    end, so S42 states it where a person goes to hand a month over — one of the
    two is where the clerk is, and the other is where the finance officer is.
    """
    # Imported HERE rather than at module scope: `apps/ledger/exports.py`
    # imports this module (it reads the register to build the cost section), so
    # a top-level import back would be a cycle. The dependency is one-way at
    # module load and two-way only at call time.
    from apps.ledger import exports

    batches = exports.batches_covering(period_start=row.period_start, period_end=row.period_end)
    note: dict[str, Any] = {
        "correction": AFTER_CLOSE_CORRECTION,
        "action": action,
        "reason": reason,
        "period": [row.period_start.isoformat(), row.period_end.isoformat()],
        "exported_batches": batches,
    }
    if batches:
        note["problem"] = EXPORT_ALREADY_HANDED_OVER
        note["detail"] = (
            "This period has ALREADY been handed over to an accounting system, and the export "
            "is idempotent — it cannot be re-run (BR-LED-004), because a utility must never "
            "receive one month twice. The batch(es) named here therefore no longer match this "
            "register, and the difference has to be corrected at the accounting system's end "
            "by a person. PO 2026-08-16 (OQ-203) accepted this consequence on the condition "
            "that it is NAMED rather than hidden."
        )
    return note


# ═══════════════════════════════════════════════════════════════════════════
# BR-LED-028's forbidden workflows — refused BY NAME, never merely absent
# ═══════════════════════════════════════════════════════════════════════════
#: The five things this product will never do to a captured payable, in the
#: rule's own order. Named as data so a caller can enumerate them and a test can
#: assert none of them grew a function.
FORBIDDEN_ACTIONS: tuple[str, ...] = (
    "approve",
    "schedule_payment",
    "mark_paid",
    "vendor_master",
    "supplier_ageing",
)


def refuse_processing_action(action: str) -> None:
    """Always raises. **This is the feature** (US-LED-018 TC-8, TC-7 of 019).

    A missing function reads as an unbuilt feature; a refusal that cites the
    rule reads as law. BR-LED-028 is the law, PO-CONFIRMED 2026-08-12 (OQ-188),
    and option (c) *full accounts payable* was put to the PO and **declined**.
    """
    raise CostCaptureError(
        f"{action!r} does not exist in this product and will not, BY RULE. BR-LED-028 (PO "
        "2026-08-12, OQ-188): the product is the system of record for AP and AR both and "
        "PROCESSES NEITHER — no approval workflow, no payment run, no vendor master, no "
        "supplier ageing or dunning, no cheque printing or remittance advice, no paying "
        "anything. Option (c), full accounts payable, was put to the Product Owner and "
        "DECLINED: every utility at this product's size already runs QuickBooks or Xero, and "
        "duplicating payables here creates two sets of books that disagree. The real payables "
        "reach the accounting system through the export (BR-LED-020 / BR-LED-039). This is a "
        "RULE and not a missing feature — do not implement it.",
        br_ref="BR-LED-028",
    )


# ═══════════════════════════════════════════════════════════════════════════
# CAPTURE (US-LED-018)
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-003")
def capture_supplier_invoice(
    actor: Any,
    *,
    invoice_date: date,
    service: str,
    supplier_name: str,
    amount: Decimal,
    currency: str,
    volume: Decimal | None = None,
    volume_unit: str | None = None,
    ledger_account_id: Any = None,
    premises_id: Any = None,
    reference: str | None = None,
    memo: str | None = None,
) -> dict[str, Any]:
    """LE-11 — one supplier invoice, recorded and processed by nothing.

    ⚠ **THE ROLE GATE IS A READING AND IS FLAGGED, NOT ASSUMED** (US-LED-018 §8).
    BR-LED-003 was amended by the PO on 2026-08-12 (OQ-175) to *"System Admin,
    Billing Clerk"*, and its own text says the substitution *"is owed anywhere
    'Finance/Owner' gates a ledger action in this module's epics … flagged, not
    assumed"*. **What was put to the PO was the REVERSAL** — capture was not
    separately raised — so TC-9's Executive refusal is this lane's reading of a
    ratified pattern and is carried as such, the same posture US-LED-014 takes
    for the remittance record and US-LED-015 for the close.

    Returns the stored row plus `problems`: an empty tuple is the clean case,
    and each code names something a reader must not discover later.
    """
    tenant_id = _tenant_id()
    if not isinstance(invoice_date, date) or isinstance(invoice_date, datetime):
        raise CostCaptureError(
            "invoice_date must be a date supplied by the caller. It is what the SUPPLIER wrote "
            "on the document, so nothing here reads a clock (BR-TEN-043, gate G6).",
            br_ref="BR-LED-029",
        )
    supplier = str(supplier_name or "").strip()
    if not supplier:
        raise CostCaptureError(
            "a captured supplier invoice must name its supplier. The field is FREE TEXT and "
            "there is no vendor master (BR-LED-028 forbids one), so nothing validates the "
            "spelling and two spellings of the same utility are both kept as typed — but a "
            "payable naming NO supplier cannot be reconciled against a supplier statement, "
            "which is the whole reason to capture it.",
            br_ref="BR-LED-029",
        )
    _refuse_unknown_category(service)
    money = _clean_amount(amount)
    money_currency = _clean_currency(currency)
    quantity, unit = _clean_volume(volume, volume_unit)
    premises = _clean_premises(premises_id)  # CR-060 C3 / task T4
    account = _resolve_account(service, ledger_account_id, actor)

    # ── BR-LED-034 · BR-TEN-038 — the closed-period auto-forward ────────────
    # `close.resolve_entry_date` is the rule, already built and argued for LE-9.
    # It is CALLED, never reimplemented: a second implementation is how two
    # callers forward the same event to two different months.
    landed_on, forward_note = close.resolve_entry_date(invoice_date)
    period_start, period_end = close.period_window(landed_on)

    problems: list[str] = list(_amount_problems(money))
    if account.code in chart.PENDING_FINANCE_RE_SIGN_COST:
        problems.append(UNSIGNED_ACCOUNT_NOTE)

    with transaction.atomic():
        row = models.SupplierInvoice.objects.create(
            tenant_id=tenant_id,
            invoice_date=invoice_date,
            service=service,
            supplier_name=supplier,
            amount=money,
            currency=money_currency,
            volume=quantity,
            volume_unit=unit,
            ledger_account=account,
            premises_id=premises,
            period_start=period_start,
            period_end=period_end,
            reference=(str(reference).strip() or None) if reference else None,
            memo=(str(memo).strip() or None) if memo else None,
            status=models.SUPPLIER_INVOICE_CAPTURED,
            captured_by_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        )
        after = _audit_snapshot(row)
        if forward_note is not None:
            # LE-9's note, carried onto the row that moved so the trail says WHY
            # a July-dated invoice is in the August period.
            after["period_auto_forwarded"] = forward_note
        after["gl_account_finance_signed"] = account.code not in chart.PENDING_FINANCE_RE_SIGN_COST
        core_audit.money_action(actor, AUDIT_CAPTURED, "supplier_invoice", str(row.pk), after=after)

    result = supplier_invoice_row(row)
    result["problems"] = tuple(problems)
    result["period_auto_forwarded"] = forward_note
    # Named on every capture rather than discovered later (hard-won law 1):
    # this row does NOT move the books, and since 2026-08-16 that is the RULING
    # and not an open question. The screen prints this sentence, which is why it
    # is a sentence and not a flag.
    result["posting"] = {
        "posted": False,
        "reason": POSTING_RULED_NONE,
        # ⚠ AMENDED 2026-09-02 (CR-060 C1 / T6). The first half is unchanged and
        # still true; the second half used to say the books never move for a
        # purchase, and now names what moves them. A screen printing the old
        # sentence beside a "Paid on" field would be the defect OQ-200's own
        # closure warned about, one ruling later.
        "detail": (
            "Capturing a supplier invoice posts NOTHING to the books. That is the ruling "
            "(OQ-200, PO 2026-08-16), not a gap: posting on receipt would credit an accounts "
            "payable this product can never drain, because payment runs are forbidden "
            "(BR-LED-028), leaving $37,200.00 a year standing for invoices the utility "
            "settled by cheque. A capture is a filing and reconciliation record — it appears "
            "on the cost register, in the bought-vs-billed reconciliation and in the "
            "accounting export's register-derived section, and in no trial balance. THE BOOKS "
            "MOVE WHEN YOU RECORD THAT IT WAS PAID: entering 'Paid on' posts one balanced "
            "entry, DR the cost account / CR cash, and creates no payable at all (PO ruling "
            "2026-09-02)."
        ),
        # The two states R8 names, on the capture result as well as on the
        # register, because a clerk who has just captured an invoice is exactly
        # the person about to ask "so is this in the books or not?".
        "settlement": settlement_state(row),
    }
    return result


# ═══════════════════════════════════════════════════════════════════════════
# EDIT — while the period is OPEN (BR-LED-034), and AFTER it closes with a
# reason (OQ-203, PO-RULED 2026-08-16). US-LED-019.
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-003")
def edit_supplier_invoice(
    actor: Any, invoice_id: Any, *, correction_reason: Any = None, **changes: Any
) -> dict[str, Any]:
    """LE-13's first bullet — CI-3's amount 310.00 → **312.40** while July is OPEN.

    The register footer moves to **51,904.90** and the VOLUME figures do not move
    at all, so water still reads **9.00%**. Audit `supplier_invoice.updated`
    with before/after (BR-LED-036).

    **After the invoice's own period has CLOSED the edit is still lawful** — PO
    2026-08-16 closing OQ-203, verbatim *"Yes it can be corrected"* — and
    `correction_reason` becomes REQUIRED. The result then carries
    `after_close`, which names every export batch covering that window: those
    batches no longer match the register and the difference has to be resolved
    at the accounting system's end, because the export is idempotent and cannot
    be re-run (BR-LED-004).
    """
    row = _get_or_refuse(invoice_id)
    if row.status == models.SUPPLIER_INVOICE_VOIDED:
        raise CostCaptureError(
            f"supplier invoice {row.reference or row.pk} is VOIDED and cannot be edited. "
            "BR-LED-035 makes a correction a void plus a FRESH CAPTURE — new rows, never an "
            "in-place edit of a row whose whole purpose is now to record that it was withdrawn.",
            br_ref="BR-LED-035",
        )
    after_close: dict[str, Any] | None = None
    if close.is_period_closed(row.period_start, row.period_end):
        reason = _require_after_close_reason(correction_reason, "edit")
        after_close = _after_close_note(row, "edit", reason)

    unknown = sorted(set(changes) - set(EDITABLE_FIELDS))
    if unknown:
        if SETTLEMENT_FIELD in unknown:
            # CR-060 C1 / T6 — a named refusal rather than a place in a list of
            # unknown fields, because a clerk (or a lane) reaching for
            # `edit(paid_on=…)` is reaching for the right feature by the wrong
            # door. Recording a settlement POSTS money and is its own audited
            # act with its own required moment.
            raise CostCaptureError(
                "paid_on is not edited through this form. Recording that a supplier invoice "
                "was settled POSTS one balanced entry to the books (DR the cost account / CR "
                "cash, PO ruling 2026-09-02) and needs the moment the clerk acted, so it is "
                "its own audited action exactly as a void is: call record_settlement. Every "
                "other captured fact on this invoice is edited here.",
                br_ref="BR-LED-034 · CR-060 C1",
            )
        raise CostCaptureError(
            f"{unknown} cannot be edited. BR-LED-034 makes the CAPTURED FACTS editable while "
            f"the period is open ({list(EDITABLE_FIELDS)}); status, the void trail and the "
            "capturing actor are not facts a clerk re-types — a void is its own audited action "
            "with its own required reason (BR-LED-035).",
            br_ref="BR-LED-034",
        )
    if not changes:
        raise CostCaptureError("an edit with no changes writes an audit row saying nothing.")

    # CR-060 C1 / T6 — the four facts a POSTED settlement entry copied. Changing
    # one of them here would leave the register saying 312.40 and the books
    # saying 310.00, with nothing red anywhere. OQ-1350: MINTED, not answered.
    settled_fields = tuple(f for f in SETTLEMENT_COPIES if f in changes)
    if settled_fields:
        _refuse_if_settled(row, action="correction", fields=settled_fields)

    before = _audit_snapshot(row)
    #: Captured BEFORE any field is written, so the after-close branch below can
    #: tell a re-dating (OQ-227) from an amount correction.
    before_invoice_date = row.invoice_date
    service = changes.get("service", row.service)
    if "service" in changes:
        _refuse_unknown_category(service)
    if "supplier_name" in changes:
        supplier = str(changes["supplier_name"] or "").strip()
        if not supplier:
            raise CostCaptureError(
                "a captured supplier invoice must name its supplier (BR-LED-029).",
                br_ref="BR-LED-029",
            )
        row.supplier_name = supplier
    if "invoice_date" in changes:
        new_date = changes["invoice_date"]
        if not isinstance(new_date, date) or isinstance(new_date, datetime):
            raise CostCaptureError("invoice_date must be a date supplied by the caller.")
        row.invoice_date = new_date
    if "amount" in changes:
        row.amount = _clean_amount(changes["amount"])
    if "currency" in changes:
        row.currency = _clean_currency(changes["currency"])
    if "volume" in changes or "volume_unit" in changes:
        quantity, unit = _clean_volume(
            changes.get("volume", row.volume), changes.get("volume_unit", row.volume_unit)
        )
        row.volume, row.volume_unit = quantity, unit
    if "service" in changes:
        row.service = service
    if "ledger_account_id" in changes:
        row.ledger_account = _resolve_account(service, changes["ledger_account_id"], actor)
    elif "service" in changes and "ledger_account_id" not in changes:
        # The service moved and the account did not. The account is NOT
        # re-defaulted: BR-LED-038 makes the seeded pointer a default a tenant
        # may override, and silently re-pointing a purchase a clerk had
        # classified by hand would undo their choice without saying so. The
        # mismatch is reported on the result instead.
        pass
    if "premises_id" in changes:
        # CR-060 C3 / task T4 — the same validator as capture, so a building
        # cannot arrive by the back door of an edit. Clearing it to blank IS
        # lawful (the null is a real state); another tenant's building is not.
        row.premises_id = _clean_premises(changes["premises_id"])
    if "reference" in changes:
        row.reference = (str(changes["reference"]).strip() or None) if changes["reference"] else None
    if "memo" in changes:
        row.memo = (str(changes["memo"]).strip() or None) if changes["memo"] else None

    if after_close is None:
        # BR-LED-034 while the period is OPEN: the PERIOD follows the date, and
        # a date moved into a closed month auto-forwards exactly as it does at
        # capture. `resolve_entry_date` again — one implementation of the rule,
        # borrowed twice, never re-written.
        landed_on, forward_note = close.resolve_entry_date(row.invoice_date)
        row.period_start, row.period_end = close.period_window(landed_on)
    else:
        # ⚠ **AN AFTER-CLOSE CORRECTION DOES NOT RE-HOME THE PURCHASE**, and
        # this branch exists because the OQ-203 ruling created the case rather
        # than because anyone designed it. Until 2026-08-16 the after-close path
        # raised before reaching this line, so the auto-forward above had only
        # ever seen open periods.
        #
        # What it would have done, and why that is wrong: `resolve_entry_date`
        # answers *"where does an event dated then land NOW?"*, and for a July
        # invoice with July closed the answer is AUGUST. Applied to a
        # correction, that silently MOVES a purchase the utility made in July
        # into August — July's register loses $310.00, August's gains it, and
        # both months' bought-vs-billed figures move. Correcting an amount is
        # not relocating a purchase, and the PO's own warning requirement
        # assumes the row stays where the exported batch found it: a warning
        # naming the batch that no longer matches is meaningless if the row has
        # left that batch's window altogether.
        #
        # So the period is what it was. The auto-forward rule is untouched for
        # the case it was written for — a NEW capture dated into a closed month
        # (BR-LED-034, LE-9) — which is the branch above and at capture.
        forward_note = None
        if "invoice_date" in changes and row.invoice_date != before_invoice_date:
            # ⚠ **OQ-227 IS CLOSED (PO, 2026-08-16) AND THIS REFUSAL IS NOW LAW
            # RATHER THAN A STUB.** It raised `NotImplementedError("OQ-227")`
            # while the question was open — the honest shape for a rule nobody
            # had signed. The PO ruled, verbatim on the option as put to them:
            # *"Stay in July (what ships now) — a correction is a correction.
            # July's register keeps its $310.00; both months' totals are
            # unchanged. Re-dating is refused by name as a move, not a
            # correction. - this is correct"*.
            #
            # So the behaviour does not change by one line; its STATUS does,
            # and leaving the NotImplementedError would tell every later reader
            # that a decision is still pending on a question the PO has closed
            # (G8 catches exactly that, and did). The principle the ruling
            # states generalises beyond supplier invoices and is worth carrying
            # here: **correcting WHAT a record says is a correction; changing
            # WHEN it happened is a MOVE, and a move needs its own deliberate
            # act with its own audit trail.** One edit form was quietly
            # conflating two different operations.
            raise CostCaptureError(
                "the invoice date of a purchase in a CLOSED period cannot be changed here. "
                f"{row.reference or 'This invoice'} is dated {before_invoice_date} and its "
                f"period is closed; moving it to {row.invoice_date} would take its amount out "
                "of one month's reconciliation and put it into another's, which is a MOVE and "
                "not a correction (PO ruling 2026-08-16 closing OQ-227: *a correction is a "
                "correction*). Every other field on this invoice may still be corrected, and "
                "the period stays where it was.",
                br_ref="BR-LED-035 · OQ-227 (PO 2026-08-16)",
            )

    problems = list(_amount_problems(row.amount))
    if row.ledger_account.code in chart.PENDING_FINANCE_RE_SIGN_COST:
        problems.append(UNSIGNED_ACCOUNT_NOTE)

    if after_close is not None and after_close.get("problem"):
        problems.append(after_close["problem"])

    with transaction.atomic():
        row.save()
        after = _audit_snapshot(row)
        if forward_note is not None:
            after["period_auto_forwarded"] = forward_note
        if after_close is not None:
            # OQ-203's condition, written into the append-only record and not
            # only returned to a screen that may be closed and forgotten. This
            # audit row is the ONLY artifact that can explain the difference to
            # whoever later reconciles the ERP's copy against this register.
            after["after_close_correction"] = after_close
        core_audit.money_action(
            actor, AUDIT_UPDATED, "supplier_invoice", str(row.pk), before=before, after=after
        )

    result = supplier_invoice_row(row)
    result["problems"] = tuple(problems)
    result["period_auto_forwarded"] = forward_note
    result["after_close"] = after_close
    return result


# ═══════════════════════════════════════════════════════════════════════════
# VOID — never delete (US-LED-019, BR-LED-035)
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-003")
def void_supplier_invoice(
    actor: Any, invoice_id: Any, *, reason: str, voided_at: datetime
) -> dict[str, Any]:
    """LE-13's second bullet — CI-4 voided, *"duplicate of RS-2607-0175"*.

    **The row stays visible in the register with its reason** (BR-LED-035): a
    register that hides its corrections cannot be reconciled against a supplier
    statement. And it leaves every aggregate from that moment — the July footer
    moves **51,902.50 → 51,747.50**, water's bought volume **1,000,000 →
    950,000 gal** and its cost **3,100.00 → 2,945.00**, so the unaccounted-for
    figure becomes `(950,000 − 910,000) ÷ 950,000 = **4.21%**`. **A void MOVES
    the loss figure, and that is correct** — those 50,000 gallons were never
    bought.

    `voided_at` is an INPUT (BR-TEN-043): nothing in a money path reads a clock,
    so a retried void stamps one moment rather than two.
    """
    row = _get_or_refuse(invoice_id)
    cleaned = str(reason or "").strip()
    if not cleaned:
        raise CostCaptureError(
            "a void needs a REASON, and the requirement is the point of the feature. The row "
            "stays visible in the register precisely so a clerk reconciling against a supplier "
            "statement can see WHY a line was withdrawn — LE-13's own example is *\"duplicate of "
            'RS-2607-0175"*. A reasonless void is a row that raises a question it cannot answer '
            "(BR-LED-035).",
            br_ref="BR-LED-035",
        )
    if not isinstance(voided_at, datetime):
        raise CostCaptureError(
            "voided_at must be a datetime supplied by the caller (BR-TEN-043): the moment a "
            "capture was withdrawn is a business fact, and a service that read the clock would "
            "stamp a different one on a retry."
        )
    if row.status == models.SUPPLIER_INVOICE_VOIDED:
        raise CostCaptureError(
            f"supplier invoice {row.reference or row.pk} is already voided (since "
            f"{row.voided_at}, reason {row.void_reason!r}). Voiding it twice would overwrite the "
            "reason of the FIRST void, which is the record the register exists to keep.",
            br_ref="BR-LED-035",
        )
    # CR-060 C1 / T6 — a void drops the row out of every aggregate from that
    # moment (the July footer moves 51,902.50 -> 51,747.50). Once the purchase
    # has SETTLED its cost is also in the trial balance, which a void does not
    # touch: the register would lose the money and the books would keep it.
    # OQ-1350: MINTED, not answered — unposting is a reversal, and whether a
    # void should reverse is not ruled.
    _refuse_if_settled(row, action="void")
    # OQ-203, PO-RULED 2026-08-16 (*"Yes it can be corrected"*): a void after
    # close is lawful. The void's own reason IS the correction reason — a second
    # box asking the same question twice on one form is how a clerk learns to
    # type "x" in one of them — so `cleaned` is reused rather than re-collected.
    after_close = (
        _after_close_note(row, "void", cleaned)
        if close.is_period_closed(row.period_start, row.period_end)
        else None
    )

    before = _audit_snapshot(row)
    with transaction.atomic():
        row.status = models.SUPPLIER_INVOICE_VOIDED
        row.void_reason = cleaned
        row.voided_at = voided_at
        row.voided_by_user_id = getattr(actor, "id", None) or getattr(actor, "pk", None)
        row.save()
        after = _audit_snapshot(row)
        if after_close is not None:
            after["after_close_correction"] = after_close
        core_audit.money_action(
            actor,
            AUDIT_VOIDED,
            "supplier_invoice",
            str(row.pk),
            before=before,
            after=after,
        )
    result = supplier_invoice_row(row)
    result["after_close"] = after_close
    result["problems"] = (
        (after_close["problem"],) if after_close and after_close.get("problem") else ()
    )
    return result


# ═══════════════════════════════════════════════════════════════════════════
# SETTLEMENT — CR-060 C1 / task T6. **THE BOOKS MOVE WHEN A CLERK RECORDS
# THAT THE INVOICE WAS PAID.** PO ruling 2026-09-02.
# ═══════════════════════════════════════════════════════════════════════════
#: The open question this lane MINTED rather than answered (CLAUDE.md prime
#: directive). Named once so the stub, its refusal text and the test that pins
#: it all cite one string.
SETTLED_CHANGE_UNRULED = "OQ-1350"


def settlement_posting_key(invoice_id: Any) -> str:
    """The replay guard's string for one invoice's settlement (hard rule 6).

    Composed through `posting.posting_key`, never by hand, so this caller keys
    the way all seventeen source events key. Pure — same invoice, same string,
    always — which is what lets `record_settlement` ask *"is this already in the
    books?"* before doing any work and still be backstopped by
    `uq_journal_entries_posting_key` if it loses a race.
    """
    return posting.posting_key(
        source_type=SETTLEMENT_SOURCE_TYPE, source_id=invoice_id, event=SETTLEMENT_EVENT
    )


def settlement_entry(invoice_id: Any) -> Any:
    """The journal entry this invoice's settlement posted, or None.

    A READ of the books, which is lawful anywhere: CLAUDE.md rule 5 makes
    `apps/ledger/posting.py` the sole WRITER of journal lines and says nothing
    about reading them (`close.py` and `reporting.py` read them too). Nothing in
    this module ever constructs, updates or deletes a `JournalEntry`.

    Tenant-scoped by construction — `_tenant_id()` refuses with no
    `app.tenant_id` set, so this cannot answer about somebody else's books.
    """
    return models.JournalEntry.objects.filter(
        tenant_id=_tenant_id(), posting_key=settlement_posting_key(invoice_id)
    ).first()


def _settlement_cash_account() -> str:
    """The tenant's CASH account, BY DESIGNATION — or a refusal naming it.

    Never the number 1000. `apps/ledger/chart.py` states the law in the PO's own
    words — *"the code reads the DESIGNATION and never the number"* — and a
    utility may renumber cash to anything it likes on the GL mapping page.

    `cash` is one of the twelve designations and is seeded from B5 line 74 ❄️,
    so a tenant reaching this refusal has deactivated or un-designated it on
    purpose. It is one edit on the GL mapping page and it blocks exactly one
    thing until somebody makes it.
    """
    account_id = selectors.gl_account_id_for_designation(chart.CASH)
    if not account_id:
        raise CostCaptureError(
            "no live ledger account carries the 'cash' designation, so a settled supplier "
            "invoice has nowhere to credit. Recording a settlement posts DR the cost account "
            "/ CR cash (CR-060 C1, PO 2026-09-02) and nothing here substitutes another "
            "account for it: crediting a payable would create the liability BR-LED-028 "
            "forbids this product from ever draining, and crediting anything else would be a "
            "guess written into an entry that can never be edited (hard rule 4). A System "
            "Admin designates a cash account on the GL mapping page.",
            br_ref="BR-LED-037",
        )
    return account_id


def post_settlement_to_journal(invoice: Any, *, posted_at: datetime, actor: Any = None) -> Any:
    """**DR the cost account / CR cash — one balanced entry, through the one
    posting service.** Returns the `posting.PostingResult`, or **None when the
    invoice carries no `paid_on`.**

    ⚠ **THE UNSET CASE IS THE WHOLE DESIGN AND IT IS THE FIRST LINE.** C1's own
    proof list: *"an unset `paid_on` posts nothing"*. An invoice that has arrived
    and has not been paid is a filing record and the books do not know about it.
    That is also why this column could land on a live database without moving one
    signed figure — on a database where nothing is settled, this function returns
    `None` every time it is called.

    **HARD RULE 5 IS NOT NEGOTIATED WITH.** This builds a `PostingRequest` and
    hands it to `posting.post()`. It writes no `JournalEntry` and no
    `JournalLine` itself, opens no write window, and could not: `ledger/0004`
    refuses an INSERT into either table unless the session GUC
    `app.ledger_posting` is on, and `posting.py` is the only thing that turns it
    on.

    **THE FOUR THINGS THE ENTRY CARRIES, AND WHY EACH IS WHAT IT IS.**

    * **DR — the invoice's OWN `ledger_account`.** Not re-resolved from the
      service code: the account was chosen at capture (or corrected by hand
      since, BR-LED-038), and re-deriving it here would be a second
      implementation of one mapping rule — CR-060 §13's third *"what not to
      touch"*, in as many words: *"two implementations of one mapping rule would
      eventually disagree, and the books would hold the wrong one."*
    * **CR — the `cash` DESIGNATION**, resolved through `selectors`, never the
      number. **No accounts payable is created at any point**, which is exactly
      why the objection the PO raised on 2026-08-16 does not apply to this path.
    * **The BOOK DATE is `paid_on`, run through `close.resolve_entry_date`.**
      C1's fourth proof: *"settlement into a closed period books forward"*. A
      utility pays its July water bill in August, and July usually closed on the
      5th — so this is the ORDINARY case and not an edge one. The rule is
      BORROWED, never re-implemented (BR-TEN-038 / BR-LED-006, LE-9).
    * **`premises_id` rides on the DEBIT line only.** BR-LED-001 wants the
      dimensions *where they apply*: the cost of water bought FOR 88 Magnolia Row
      belongs to that building, and the cash leaving the utility's own bank
      account belongs to no building at all. `apps/payments/ledger_seam.py` takes
      the same posture at both of its cash lines and says why.

    **WHAT IT DELIBERATELY DOES NOT STAMP: `service_id`.** `JournalLine.service`
    is an FK to a tenancy Service, and `SupplierInvoice.service` is a TEXT column
    holding a service code **or one of sixteen cost categories** (CR-060 T5) —
    fourteen of which are not services and never will be. A dimension that could
    only be filled for two rows in five is a column a report would read as
    *"tenant-wide"* for the rest, which is a worse answer than a stated absence
    (the DEF-075 posture). The cost ACCOUNT already says which service it was:
    5110 is purchased water.

    **`posted_at` IS AN INPUT** (BR-TEN-043, gate G6): nothing in a money path
    reads a clock, so a retried settlement stamps one moment rather than two.
    """
    if invoice.paid_on is None:
        return None

    landed_on, forward_note = close.resolve_entry_date(invoice.paid_on)
    cash_account_id = _settlement_cash_account()
    dimensions = {"source_type": SETTLEMENT_SOURCE_TYPE, "source_id": invoice.pk}
    request = posting.PostingRequest(
        posting_key=settlement_posting_key(invoice.pk),
        entry_date=landed_on,
        posted_at=posted_at,
        currency=str(invoice.currency),
        source_type=SETTLEMENT_SOURCE_TYPE,
        source_id=invoice.pk,
        memo=f"Supplier invoice {invoice.reference or invoice.pk} settled {invoice.paid_on}",
        lines=(
            posting.PostingLine(
                ledger_account_id=invoice.ledger_account_id,
                side=models.SIDE_DEBIT,
                amount=invoice.amount,
                premises_id=invoice.premises_id,
                **dimensions,
            ),
            posting.PostingLine(
                ledger_account_id=cash_account_id,
                side=models.SIDE_CREDIT,
                amount=invoice.amount,
                **dimensions,
            ),
        ),
        audit_context={
            "supplier_invoice_id": str(invoice.pk),
            "paid_on": invoice.paid_on.isoformat(),
            "amount": str(invoice.amount),
            "br_ref": "BR-LED-028 (AMENDED 2026-09-02) - CR-060 C1",
            "period_auto_forwarded": forward_note,
        },
    )
    return posting.post(request, actor=actor)


def _refuse_if_settled(row: Any, *, action: str, fields: tuple[str, ...] = ()) -> None:
    """**OQ-1350 — MINTED, NOT ANSWERED.** Raises `NotImplementedError` when the
    act would change something a POSTED settlement entry already copied.

    ⚠ **WHY THIS IS A STUB AND NOT A DECISION.** CR-060 C1 rules what a
    settlement DOES; it says nothing about what happens when a settled purchase
    is then corrected or voided, and neither did the PO on 2026-09-02. There are
    at least three defensible answers — reverse the settlement through
    `posting.reverse_entry` and re-post; post a delta entry; refuse the change
    outright — and they differ in what a month-end reviewer sees. Picking one
    here would be this lane answering a question nobody asked it (CLAUDE.md
    prime directive), and refusing outright is not the neutral option it looks
    like: BR-LED-034 makes a captured invoice EDITABLE, so a blanket refusal
    would REVERSE a signed rule.

    **WHAT IT COSTS TODAY: NOTHING**, and that is why the stub is honest rather
    than lazy. The PO ruled on 2026-09-01 that there is no production data, and
    no row anywhere carries a `paid_on` until a clerk types one — so this branch
    is unreachable on every database that exists. It becomes reachable the first
    time somebody settles a purchase and then corrects it, which is exactly when
    a person is available to answer the question.

    **WHY IT IS NARROW.** Only the four facts the settlement entry COPIED are
    guarded — the amount, the currency, the cost account and the building — and
    on those the books and the register would silently disagree. Everything else
    on a settled invoice (the supplier's name, the reference, the memo, the
    invoice date, the volume and its unit) is still corrected exactly as
    BR-LED-034 says, because none of them is in the entry.

    **AND WHAT IT PREVENTS IS A SILENT DIVERGENCE, NOT AN ERROR.** Without it,
    editing a settled invoice's amount from 310.00 to 312.40 leaves the register
    saying 312.40 and the books saying 310.00, with nothing red anywhere — and
    CR-060 T6d, the tie-out row that would surface it, is not built.
    """
    if row.paid_on is None or settlement_entry(row.pk) is None:
        return
    named = ", ".join(fields) if fields else action
    raise NotImplementedError(
        f"{SETTLED_CHANGE_UNRULED}: supplier invoice {row.reference or row.pk} was settled on "
        f"{row.paid_on} and its cost is IN THE BOOKS, so a {action} touching {named} would "
        "move a figure the trial balance already carries. What a settlement should do when "
        "the purchase behind it is corrected or voided - reverse and re-post, post a delta, "
        "or refuse - is NOT ruled by CR-060 C1 and is not this lane's to choose. Every other "
        "field on this invoice may still be corrected (BR-LED-034)."
    )


#: The four facts the settlement entry COPIES. An edit to any of them, once the
#: settlement has posted, is what `_refuse_if_settled` guards. Declared as data
#: rather than inline so the guard, the API and the test read one list.
SETTLEMENT_COPIES: tuple[str, ...] = ("amount", "currency", "ledger_account_id", "premises_id")


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-003")
def record_settlement(
    actor: Any,
    invoice_id: Any,
    *,
    paid_on: date | None,
    settled_at: datetime,
) -> dict[str, Any]:
    """**C1's core change — the clerk records that this invoice was paid, and
    the cost of service finally reaches the books.**

    PO ruling 2026-09-02, verbatim: *"why cant to add the check that whether this
    is paid or unpaid and allow clark to udpaet it - that way we can reconcicle -
    again system of record we dont have to match we can take input from Clark and
    close it"*.

    **THE CLERK'S INPUT IS THE AUTHORITY.** Nothing is matched against a bank
    feed, a statement line or a deposit batch, and nothing needs to be: the PO's
    sentence is a design constraint, not an aspiration deferred until matching
    exists. A clerk who has the bank statement open types the date they see.

    **WHAT EACH CASE DOES, and there are only four.**

    * **`paid_on` set, nothing posted yet** — the column is written and
      `DR cost / CR cash` posts, in ONE transaction. LE-11's CI-1 settled on
      2026-08-04 posts **DR 5110 purchased water 1,240.00 / CR 1000 cash
      1,240.00**, and the trial balance moves from **598.69 = 598.69** to
      **1,838.69 = 1,838.69**. Settling all nine of July's purchases takes it to
      **52,351.19 = 52,351.19** (⚠ CR-060 and the 2026-09-02 decision-log row both project **52,501.19**, which is 598.69 + 51,902.50 and is **150.00 HIGH**: a trial balance nets each account onto ONE side, LE-1 leaves 150.00 of debit in 1000 Cash, and paying suppliers credits cash so that account leaves the debit column altogether. MEASURED 2026-09-02 and corrected in the decision log; nothing signed moved — 598.69 is the signed figure and 52,501.19 was a projection, never a signature. `tests/test_cr060_t6_settlement_posting.py` asserts both numbers and the 150.00 between them). Moving LE-1's signed 598.69 needs the HUMAN-GUIDE §6
      re-sign, which is owed at the FIRST settlement and not at the landing of
      this code.
    * **`paid_on` set to the SAME date twice** — a **replay no-op**. C1's third
      proof. The posting key makes it one by construction (hard rule 6), so a
      double-clicked Save posts once and the result says `replayed: True`.
    * **`paid_on` cleared, or moved to a different date, once the settlement has
      posted** — **REFUSED**, by name. C1 says clearing is refused once posted;
      moving it is the identical hazard and is refused for the identical reason,
      recorded as this lane's judgment rather than smuggled in: the entry is
      already in the books at the old date, hard rule 4 leaves no path to change
      it, and the replay guard would make the new date a silent no-op — the
      register would say one thing and the trial balance another.
    * **`paid_on` cleared while nothing has posted** — **lawful**, and it is the
      ordinary correction of a mis-typed row. Nothing to unwind.

    **NO `correction_reason`, EVEN WHEN THE INVOICE'S PERIOD HAS CLOSED**, and
    that is deliberate rather than overlooked. `_require_after_close_reason`
    exists because an after-close EDIT changes a figure a month-end was signed
    off over. Recording a settlement changes no captured fact: it is new
    information arriving, and *"July closed on the 5th and we paid the July water
    bill on the 10th"* is the NORMAL case, not an exception. The entry books
    forward into the open period (BR-TEN-038) and its own audit row says so.

    **THE INVOICE'S PERIOD DOES NOT MOVE.** `period_start` / `period_end` are
    where the PURCHASE belongs and they are untouched; only the settlement
    ENTRY's book date is resolved against the calendar. Moving the purchase would
    take its amount out of one month's bought-vs-billed and put it in another's,
    which is the distinction OQ-227 already settled for a re-dating: *a
    correction is a correction; a move is a move.*
    """
    row = _get_or_refuse(invoice_id)
    if not isinstance(settled_at, datetime):
        raise CostCaptureError(
            "settled_at must be a datetime supplied by the caller (BR-TEN-043): the moment a "
            "clerk recorded the settlement is a business fact, and a service that read the "
            "clock would stamp a different one on a retry."
        )
    if paid_on is not None and (not isinstance(paid_on, date) or isinstance(paid_on, datetime)):
        raise CostCaptureError(
            "paid_on must be a DATE, not a timestamp. It is the day the utility's bank moved "
            "the money - the granularity a bank statement has - and it is the BOOK date of "
            "the entry it posts (BR-TEN-043: the caller names the business event's day).",
            br_ref="BR-LED-029",
        )
    if row.status == models.SUPPLIER_INVOICE_VOIDED:
        raise CostCaptureError(
            f"supplier invoice {row.reference or row.pk} is VOIDED and cannot be settled. A "
            "void records that the purchase was withdrawn - a duplicate, a wrong supplier - "
            "so paying it is not a thing that happened (BR-LED-035). If it WAS paid, the void "
            "was the mistake: capture it afresh, which is what BR-LED-035 means by 'a "
            "correction is a void plus a fresh capture'.",
            br_ref="BR-LED-035",
        )

    posted = settlement_entry(row.pk)
    if posted is not None and paid_on != row.paid_on:
        what = "cleared" if paid_on is None else f"moved to {paid_on}"
        raise CostCaptureError(
            f"supplier invoice {row.reference or row.pk} was settled on {row.paid_on} and that "
            f"settlement is IN THE BOOKS. Its paid-on date cannot be {what}: the entry is "
            "posted and no UPDATE or DELETE reaches a posted journal entry (CLAUDE.md hard "
            "rule 4), so the register would say one thing and the trial balance another. "
            "CR-060 C1 refuses the clearing by name and the move is the same hazard. A "
            "settlement recorded in error is corrected by REVERSING the entry, which is a "
            f"deliberate act with its own audit trail and is not built yet "
            f"({SETTLED_CHANGE_UNRULED}).",
            br_ref="BR-LED-034 · CR-060 C1",
        )

    before = _audit_snapshot(row)
    problems: list[str] = list(_amount_problems(row.amount))
    if row.ledger_account.code in chart.PENDING_FINANCE_RE_SIGN_COST:
        # US-LED-017 TC-5 - REPORTED, never refused. Fourteen of the sixteen
        # cost categories CR-060 T5 introduced seed `signed=False`, so refusing
        # would make most of the vocabulary unsettleable over a signature the
        # clerk cannot give. The row says so and a human decides.
        problems.append(UNSIGNED_ACCOUNT_NOTE)

    with transaction.atomic():
        row.paid_on = paid_on
        row.save(update_fields=["paid_on", "updated_at"])
        # ONE transaction around the column and the posting, so a refusal from
        # the ledger leaves NO settled-looking row behind. Law 14: the failure
        # this shape protects against is a PostgreSQL one - an aborted
        # transaction - and the suite's default SQLite has no such state, which
        # is why this path is proved on real PostgreSQL and not only here.
        try:
            result = post_settlement_to_journal(row, posted_at=settled_at, actor=actor)
        except posting.PostingError as refusal:
            # The ledger's own sentence, passed through verbatim rather than
            # re-worded: it names the amount, the account or the rule, and it is
            # the only detail a clerk can act on. Re-raised as a
            # `CostCaptureError` so the API classifies one exception type from
            # this module (`PostingError` has no HTTP surface by design — see
            # its docstring) and so the surrounding `atomic()` unwinds the
            # paid_on write with it.
            raise CostCaptureError(
                f"the ledger refused this settlement, so nothing was recorded and "
                f"{row.reference or row.pk} is still unpaid. {refusal}",
                br_ref=SETTLEMENT_LEDGER_REFUSAL_REF,
            ) from refusal
        after = _audit_snapshot(row)
        after["settlement"] = {
            "paid_on": paid_on.isoformat() if paid_on else None,
            "journal_entry_id": str(result.entry_id) if result is not None else None,
            "posted": bool(result is not None and result.created),
            "amount": _audit_str(row.amount),
            "currency": row.currency,
        }
        core_audit.money_action(
            actor, AUDIT_SETTLED, "supplier_invoice", str(row.pk), before=before, after=after
        )

    out = supplier_invoice_row(row)
    out["problems"] = tuple(problems)
    out["settlement"] = settlement_state(row, result)
    return out


def settlement_state(row: Any, result: Any = None) -> dict[str, Any]:
    """The two states R8 names, served as data plus the sentence that explains
    them — so a screen prints the ledger's words and cannot drift from them.

    CR-060 §8b, R8, verbatim: *"Recorded — held here, not in the books"* and
    *"In the books — posted when you enter paid on: DR cost / CR cash, one
    balanced entry, no payables balance ever created."*

    `journal_entry_id` is served because a tie-out and a drill-back need it, and
    it is an id: **B14 rule 31 means no screen prints it** — the state and the
    sentence are what a clerk reads.
    """
    entry_id = str(result.entry_id) if result is not None else None
    if entry_id is None and row.paid_on is not None:
        posted = settlement_entry(row.pk)
        entry_id = str(posted.pk) if posted is not None else None
    return {
        "paid_on": row.paid_on.isoformat() if row.paid_on else None,
        "in_the_books": entry_id is not None,
        "journal_entry_id": entry_id,
        "replayed": bool(result is not None and not result.created),
        "ruling": SETTLEMENT_RULING,
    }


def settlement_states(rows: Any) -> dict[str, dict[str, Any]]:
    """`{invoice id: settlement block}` for a whole page, in ONE query.

    **DEF-3440.** `supplier_invoice_row`'s own comment has said since
    2026-09-02 that *"the screen reads this and `settlement.in_the_books`, never
    a date arithmetic of its own"* — and `register()` served `paid_on` and no
    such block at all, so the only screen that followed the instruction would
    have read `undefined`, which is falsy, and drawn **every settled purchase as
    unsettled**: the money in the trial balance and the register saying it is
    not. Hard-won law 1, in the file that names the guarantee.

    ⚠ **WHY THIS EXISTS RATHER THAN `settlement_state(row)` IN THE LIST LOOP.**
    That function calls `settlement_entry(row.pk)`, which is one read of
    `journal_entries` per invoice — and this register is UNPAGINATED by
    design (`register`'s own docstring reports the whole filtered set as the
    contract, not a page). A month of a real utility's purchases is dozens of
    rows, so the tidy call would be dozens of extra queries that nothing would
    ever measure. Here the whole page's posting keys go out in one
    `posting_key__in`, and `tests/test_cr060_t6e_register_settlement.py` asserts
    that settling three of nine costs the SAME number of queries as settling
    none, so a later "simplification" back to the per-row call goes RED rather
    than going quietly slow.

    Tenant-scoped by construction, exactly as `settlement_entry` is: the filter
    carries `_tenant_id()`, so a posting key — which is derived from an invoice
    id and therefore guessable in shape — can never answer about another
    tenant's books.
    """
    listed = tuple(rows)
    keys = {settlement_posting_key(row.pk): str(row.pk) for row in listed if row.paid_on}
    posted: dict[str, str] = {}
    if keys:
        for entry in models.JournalEntry.objects.filter(
            tenant_id=_tenant_id(), posting_key__in=list(keys)
        ).only("id", "posting_key"):
            posted[keys[entry.posting_key]] = str(entry.pk)
    out: dict[str, dict[str, Any]] = {}
    for row in listed:
        entry_id = posted.get(str(row.pk))
        out[str(row.pk)] = {
            "paid_on": row.paid_on.isoformat() if row.paid_on else None,
            "in_the_books": entry_id is not None,
            "journal_entry_id": entry_id,
            # A LIST never replays anything — `replayed` answers "did the save
            # you just pressed post, or was it already posted?", which is a
            # property of one write and not of a row. Served False rather than
            # omitted so the block has ONE shape wherever a screen meets it.
            "replayed": False,
            "ruling": SETTLEMENT_RULING,
        }
    return out


def _get_or_refuse(invoice_id: Any) -> Any:
    """One row of THIS tenant, or a refusal.

    Tenant-scoped by construction (`_rows()`), which is the app-layer half of
    J25 step 12: *"Brazos Bend's CI-1..CI-9 are unreachable from Lone Star Ridge
    BY ID"*. A cross-tenant id therefore looks exactly like a missing one, which
    is the correct answer — confirming that a row exists somewhere is itself a
    leak.
    """
    row = _rows().filter(pk=invoice_id).first()
    if row is None:
        raise CostCaptureError(
            f"no captured supplier invoice {invoice_id!r} belongs to this tenant.",
            br_ref="BR-TEN-003",
        )
    return row


#: The column's own scale. Audit values are quantized to it so a BEFORE read
#: back from the database (`Decimal('310.000000')`) and an AFTER still in memory
#: (`Decimal('312.40')`) are the same shape — otherwise a diff of one edited
#: field reads as a change of scale as well as of value, and a reviewer cannot
#: tell which part was the edit.
_AUDIT_SCALE = Decimal("0.000001")


def _audit_str(value: Decimal | None) -> str | None:
    return None if value is None else str(value.quantize(_AUDIT_SCALE))


def _audit_snapshot(row: Any) -> dict[str, Any]:
    """The before/after payload (BR-AUD-003). Money and volumes as STRINGS — a
    float in an audit payload is the same defect rule 2 forbids in a column, one
    layer out. Quantized to the column's scale, never ROUNDED to display."""
    return {
        "invoice_date": row.invoice_date.isoformat(),
        "service": row.service,
        "supplier_name": row.supplier_name,
        "amount": _audit_str(row.amount),
        "currency": row.currency,
        "volume": _audit_str(row.volume),
        "volume_unit": row.volume_unit,
        "ledger_account_id": str(row.ledger_account_id),
        # CR-060 C3 / task T4 — in the trail because re-keying it moves a
        # figure between two rows of the per-building recovery report, and
        # "which building did this cost go to" is a question a clerk will
        # eventually have to answer to an auditor.
        "premises_id": str(row.premises_id) if row.premises_id else None,
        "period": [row.period_start.isoformat(), row.period_end.isoformat()],
        "reference": row.reference,
        "memo": row.memo,
        # CR-060 C1 / task T6 — in the trail because setting it POSTS, and hard
        # rule 7 wants the money action recorded with what changed. A settled
        # invoice whose paid-on date appeared with no before/after would be a
        # journal entry nobody could tie to the act that caused it.
        "paid_on": row.paid_on.isoformat() if row.paid_on else None,
        "status": row.status,
        "void_reason": row.void_reason,
        "voided_at": row.voided_at.isoformat() if row.voided_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE REGISTER (US-LED-019) — S73's list, search, filters and footer
# ═══════════════════════════════════════════════════════════════════════════
def supplier_invoice_row(row: Any) -> dict[str, Any]:
    """One S73 register row, in the capability matrix's own column order.

    Money and volume come out as `Decimal` and are NOT rounded here: OQ-186
    rules that the API serves four decimals and the SCREEN shows two, and
    rounding at the read would make this a second rounding site (BR-LED-025 —
    two rounding sites is how two figures start disagreeing).

    `gl_account_unsigned` is on every row because the marker has no column
    (field map D-10) and US-LED-017 TC-5 forbids any surface presenting a
    proposed code as finance-signed.
    """
    account = row.ledger_account
    return {
        "id": str(row.pk),
        "invoice_date": row.invoice_date,
        "supplier_name": row.supplier_name,
        "service": row.service,
        "amount": row.amount,
        "currency": row.currency,
        "volume": row.volume,
        "volume_unit": row.volume_unit,
        "gl_account_id": str(row.ledger_account_id),
        "gl_account_code": account.code,
        "gl_account_name": account.name,
        "gl_account_unsigned": account.code in chart.PENDING_FINANCE_RE_SIGN_COST,
        # CR-060 C3 / task T4. `None` is a LAWFUL value, not a gap: a
        # tenant-wide cost has no building by nature. The register's own read
        # adds `premises_label` beside it in one batched lookup — B14 rule 31
        # means an id is never what a screen prints.
        "premises_id": str(row.premises_id) if row.premises_id else None,
        "period": [row.period_start.isoformat(), row.period_end.isoformat()],
        "status": row.status,
        "reference": row.reference,
        "memo": row.memo,
        # CR-060 C1 / task T6. `None` is the ordinary state and means UNPAID —
        # *"Recorded — held here, not in the books"* in R8's own vocabulary.
        # The screen reads this and `settlement.in_the_books`, never a date
        # arithmetic of its own.
        "paid_on": row.paid_on,
        "captured_by_user_id": (
            str(row.captured_by_user_id) if row.captured_by_user_id else None
        ),
        "captured_at": row.created_at,
        "void_reason": row.void_reason,
        "voided_at": row.voided_at,
        "voided_by_user_id": str(row.voided_by_user_id) if row.voided_by_user_id else None,
    }


def register(
    *,
    period_start: date | None = None,
    period_end: date | None = None,
    service: str | None = None,
    status: str | None = None,
    volume_captured: bool | None = None,
    gl_account_id: Any = None,
    q: str | None = None,
    sort: str = DEFAULT_SORT,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
    """S73's register — every captured cost, with its footer.

    **TC-1:** Brazos Bend's July renders nine rows and a footer of
    **$51,902.50 USD** (`1,240.00 + 775.00 + 310.00 + 155.00 + 620.00 +
    28,222.00 + 6,235.00 + 1,845.50 + 12,500.00`). After CI-4 is voided the
    footer reads **$51,747.50** and CI-4 is **still in the list**.

    **`volume_captured=False` is the filter that earns its place** (TC-3). It
    returns exactly the set that decides whether an unaccounted-for percentage
    can be produced at all (BR-LED-031), so a clerk finds and fixes the gap in
    one click instead of reading a suppressed percentage and wondering. For
    July it returns HPV-4471 and KMW-2026-118 — legitimately volume-free O&M and
    infrastructure — and, in the degraded fixture, RS-2607-0208.

    **VOIDED ROWS ARE LISTED AND ARE NOT IN THE FOOTER**, and both halves are
    BR-LED-035. A register that hides its corrections cannot be reconciled
    against a supplier statement; a footer that includes withdrawn money is
    wrong.

    **THERE IS NO BULK-ACTION BAR**, and `bulk_actions` is an empty tuple on
    purpose rather than an omission — see the module docstring and the S73
    capability matrix, whose bulk-actions cell is empty with the same reason
    written in it.

    ⚠ **IS-2/IS-3/IS-4's browser halves are NOT here**: 300 ms debounce, URL
    persistence and the dynamic column set are frontend behaviours. What is here
    is the half that must be server-side — the filtering, the search, the
    footer, the ORDER and now the PAGE — and `MIN_SEARCH_CHARS` so a single
    keystroke cannot scan the table.

    ⚠ **THIS FUNCTION WAS UNPAGINATED UNTIL 2026-09-25 (`DEF-LED-6710`), AND
    THE ARGUMENT FOR THAT WAS THE ONE `CR-138` `P4` ALREADY WITHDREW ELSEWHERE.**
    It read: *"a small utility captures a few dozen purchases a month, the
    footer is a whole-set figure that a page cannot give."* The first clause is
    the OLD 3,000-connection ceiling talking — the ICP tops out at **40,000
    accounts** (T5), and `NFR-3` makes server pagination universal and
    load-bearing rather than tidy, precisely so no code path assumes a small
    tenant. The second clause was simply FALSE, and it is the same false premise
    `/outstandings` was retired on: **the footer is a SQL aggregate over the
    whole FILTERED set whether or not a page is cut underneath it.** It is
    computed below from the queryset, not from the rows served, so it foots to
    the filter and never to the page.

    **What a page changes and what it does not.** `rows` is one page. `count`,
    `live_count`, `voided_count`, `total_amount`, `currency` and
    `mixed_currency` are all WHOLE-SET and always were. `page` carries the
    number, the size, the total and the page count, so a pager can describe the
    set rather than itself.

    **`page` is CLAMPED, never an error** (`BR-SHL-011`): a request beyond the
    last page serves the last page, because a blank table with a *previous*
    link is a worse answer than the rows a clerk asked to see.
    """
    rows = _rows().select_related("ledger_account")

    if period_start is not None:
        rows = rows.filter(period_start__gte=period_start)
    if period_end is not None:
        rows = rows.filter(period_end__lte=period_end)
    if services := filter_values(service):  # OQ-306 — ANY of the picked services
        rows = rows.filter(service__in=services)
    if status is not None:
        if status not in models.SUPPLIER_INVOICE_STATUSES:
            raise CostCaptureError(
                f"{status!r} is not one of {models.SUPPLIER_INVOICE_STATUSES}. There is no "
                "'approved', 'scheduled' or 'paid' status, BY RULE (BR-LED-028).",
                br_ref="BR-LED-028",
            )
        rows = rows.filter(status=status)
    if volume_captured is not None:
        rows = rows.filter(volume__isnull=not volume_captured)
    if gl_account_id is not None:
        rows = rows.filter(ledger_account_id=gl_account_id)

    term = str(q or "").strip()
    if term:
        if len(term) < MIN_SEARCH_CHARS:
            raise CostCaptureError(
                f"a register search needs at least {MIN_SEARCH_CHARS} characters (IS-3): a "
                "one-character term scans every row of the table to return most of them."
            )
        # The S73 capability row: *"supplier name, invoice reference, memo"*.
        # The supplier is FREE TEXT with no vendor master (BR-LED-028), so this
        # search IS how a clerk finds "everything from the City of Rosenberg" —
        # including both spellings, which is why it is a contains match and not
        # an equality one.
        from django.db.models import Q

        rows = rows.filter(
            Q(supplier_name__icontains=term)
            | Q(reference__icontains=term)
            | Q(memo__icontains=term)
        )

    rows = rows.order_by(*_order_by(sort))

    # ── THE FOOTER IS THE FILTERED SET, THE ROWS ARE A PAGE ──────────────────
    # `DEF-LED-6710`. Both figures come off the QUERYSET, before any slice, so
    # cutting a page underneath them cannot move them. This is the correction
    # `/outstandings` already made: a whole-set aggregate does not become a
    # per-page one because a page exists.
    live_rows = rows.filter(status=models.SUPPLIER_INVOICE_CAPTURED)
    total_count = rows.count()
    live_count = live_rows.count()
    total = live_rows.aggregate(models_sum=Sum("amount"))["models_sum"] or Decimal("0")
    currencies = set(live_rows.values_list("currency", flat=True).distinct())

    # ── THE PAGE, CLAMPED (BR-SHL-011) ───────────────────────────────────────
    size = min(max(int(page_size or DEFAULT_PAGE_SIZE), 1), MAX_PAGE_SIZE)
    pages = max(1, math.ceil(total_count / size)) if total_count else 1
    number = min(max(int(page or 1), 1), pages)
    start = (number - 1) * size
    listed = tuple(rows[start : start + size])
    # CR-060 C3 / task T4 — the building's NAME, resolved ONCE for the whole
    # page rather than per row. B14 rule 31 forbids a database id being the
    # visible value of a field, so a register that served only `premises_id`
    # would leave the screen with nothing lawful to print.
    premises_labels = dimension_seam.premises_labels(
        {row.premises_id for row in listed if row.premises_id}
    )
    # CR-060 C1 / task T6(e) — DEF-3440. The two states R8 names, resolved for
    # the WHOLE page in one query rather than one per row (see
    # `settlement_states`). Without this the screen has no lawful way to tell a
    # purchase that is in the books from one that is merely on file.
    settlements = settlement_states(listed)
    # `P5.11` — whether a purchase carries the supplier's own invoice, for the
    # WHOLE PAGE in ONE query. A per-row `for_source()` would be an N+1 against
    # the document store, which is the shape `settlement_states` above already
    # exists to avoid.
    attached = documents_for_page(listed)
    served = []
    for row in listed:
        out = supplier_invoice_row(row)
        out["premises_label"] = (
            premises_labels.get(str(row.premises_id)) if row.premises_id else None
        )
        out["settlement"] = settlements[str(row.pk)]
        out["documents"] = attached.get(str(row.pk), ())
        served.append(out)
    return {
        "rows": tuple(served),
        # ⚠ WHOLE-SET, NEVER `len(listed)` — `listed` is ONE PAGE since
        # `DEF-LED-6710`, and a count taken off it makes every figure on the
        # screen describe the page instead of the filter.
        "count": total_count,
        "live_count": live_count,
        "voided_count": total_count - live_count,
        # The pager's whole contract (NFR-3). `total` is the FILTERED set.
        "page": {
            "number": number,
            "size": size,
            "total": total_count,
            "pages": pages,
        },
        # Σ over the filtered, NON-VOIDED set (US-LED-019 §5's footer row).
        "total_amount": total,
        # One currency or the tenant is in trouble — BR-TEN-042 locks it and the
        # capture refuses a mismatch, so this is a belt beside a brace. It is
        # REPORTED rather than assumed because DEF-081 is what a silently mixed
        # total costs.
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "mixed_currency": len(currencies) > 1,
        "sort": sort,
        "filters": {
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "service": service,
            "status": status,
            "volume_captured": volume_captured,
            "gl_account_id": str(gl_account_id) if gl_account_id else None,
            "q": term or None,
        },
        # BR-LED-028 — empty ON PURPOSE. A bulk action over captured payables is
        # a payment run or an approval queue, and both are forbidden.
        #
        # ⚠ **`bulk_actions_reason` STOOD HERE UNTIL 2026-09-25 AND IS DELETED,
        # NOT SHORTENED (`DEF-LED-6642`).** It read *"BR-LED-028: no approval
        # workflow and no payment run exists in this product, so there is no
        # bulk action a register of captured payables could offer. The empty
        # cell is the rule, not an unbuilt feature."* — and the screen printed
        # it verbatim under the Captured-purchases table, so a clerk read a
        # business-rule id and 38 words of our reasoning.
        #
        # **B14 rule 33 puts RATIONALE — why a control is absent — at ZERO
        # WORDS ON SCREEN**, and rule 32 forbids an internal code in
        # clerk-facing copy outright. Rationale is REMOVED rather than
        # rewritten: thirty-eight words cut to twelve would still be the same
        # class of sentence. The rule is not lost — it is stated here, in
        # `refuse_processing_action`, in `FORBIDDEN_ACTIONS` and in
        # `BR-LED-028` itself, which is where a reason belongs.
        #
        # **The empty tuple IS the statement.** A register that offers no bulk
        # action offers none; the screen shows no bulk bar and says nothing
        # about it, which is what rule 33's zero means in practice.
        "bulk_actions": (),
    }


def _order_by(sort: str) -> tuple[str, ...]:
    """`-date` → `("-invoice_date", "-created_at")`. A stable tiebreak always.

    Without the tiebreak two invoices dated the same day (July has three dated
    2026-07-31) come back in whatever order the database felt like, and a
    register that reorders itself between two identical requests is one a clerk
    stops trusting.
    """
    key = str(sort or DEFAULT_SORT)
    descending = key.startswith("-")
    name = key.lstrip("-")
    field = SORTABLE.get(name)
    if field is None:
        raise CostCaptureError(
            f"{name!r} is not a sortable column. The S73 capability matrix names "
            f"{sorted(SORTABLE)}."
        )
    prefix = "-" if descending else ""
    return (f"{prefix}{field}", "-created_at")


# ═══════════════════════════════════════════════════════════════════════════
# P5.11 — THE SUPPLIER'S OWN INVOICE, ATTACHED TO THE PURCHASE IT SETTLES
# ═══════════════════════════════════════════════════════════════════════════

#: The question this door used to wait on. ⚠ **`OQ-LED-12628` IS CLOSED —
#: PO ruling 2026-09-25, verbatim *"Seven years, same as tax receipts"*
#: (`BR-LED-799`).** The NAME is now wrong and the STRING is deliberately not
#: moved here: the refusal, the test and the screen all cite this one constant,
#: and renaming it is part of lighting the door (`P5.11`, `DEF-LED-6708`),
#: where the raise goes away in the same commit. A key whose name says one
#: thing while its sentence says another is this repo's most-filed rot
#: (hard rule 4's `amendment_history_is_not_a_permanent_record`), so it is
#: named here rather than left to be noticed.
DOCUMENT_RETENTION_UNRULED = "OQ-LED-12628"


def attach_supplier_invoice_document(
    actor: Any = None,
    *,
    supplier_invoice_id: Any,
    filename: str,
    content_type: str,
    content: bytes,
) -> dict[str, Any]:
    """Store ONE supplier document against a captured purchase — `P5.11`.

    ⚠ **THIS RAISED UNTIL 2026-09-25 AND NOW STORES.** `OQ-LED-12628` is
    CLOSED — PO ruling of that date, verbatim *"Seven years, same as tax
    receipts"* (`BR-LED-799`) — so the boundary the stub protected is gone. The
    store keeps what it takes for seven years, write-once, under S3 Object Lock
    `COMPLIANCE`, which is exactly the schedule that was ruled.
    (⚠ the object LOCK is suspended from 2026-10-02, `CR-160-BRC10`; the row stays write-once)

    ⚠ **THE RULING COVERS THE PERIOD AND NOTHING ELSE.** File-size limits,
    accepted types and behaviour at expiry were NOT shown to the Product Owner.
    So none of them is invented here: the cap and the allowlist are READ FROM
    THE EXISTING UPLOAD PATH (`customers.account_documents`) rather than
    re-declared, because two copies of a limit are two limits.

    ⚠ **NO SECOND STORE, AND NO COLUMN ON `supplier_invoices`.** `tenancy/0051`
    already made `supplier_invoice` a storable KIND and a storable SOURCE, and a
    document is found by WHAT IT BELONGS TO — `stored_documents.source_type` +
    `source_id`. A `document_id` column would be a second place one fact lives,
    and `supplier_invoices` is append-only, so attaching later would need an
    UPDATE the triggers refuse.

    ⚠ **ONE ARTEFACT PER SHAPE, AND IT IS THE SCHEMA'S RULE RATHER THAN THIS
    FUNCTION'S — VERIFIED AT SOURCE, NOT ASSUMED.** `uq_stored_documents_filed`
    is `(tenant, source_type, source_id, content_type)` with a NULL channel, so
    the database refuses a SECOND `application/pdf` against one purchase. That
    constraint's own reasoning is about RENDERINGS of one document, and it is
    not widened here: the blueprint draws *"Attach the invoice"*, singular, and
    a delivery note or a credit hanging off the same purchase would need its own
    attachment row the way a job's photographs do
    (`SOURCE_WORK_ORDER_ATTACHMENT`) — a migration, and not this defect.
    **So the second PDF is REFUSED BY NAME rather than by an IntegrityError**,
    which is also what keeps CLAUDE.md hard-won law 14 out of this path: the
    check is a query before the write, never an `except IntegrityError` that
    would poison the transaction on PostgreSQL and pass on the SQLite suite.

    ⚠ **A VOIDED PURCHASE TAKES NO NEW DOCUMENT.** Hard rule 4: a void is the
    disposition and the row is closed. Its existing documents stay readable,
    because the argument a void has to settle is exactly the one the PDF holds.
    """
    # ⚠ **`BR-SHL-031`'s TWO GUARDS, IMPORTED FROM THE ONE PLACE THAT DECLARES
    # THEM rather than re-typed here** — the precedent `finance_api.
    # _receipt_from` set for `P4.3`'s receipt, and the reason is the same: a
    # second copy of two constants is how one of them moves and the other does
    # not. Deferred, like that one, so `ledger` does not import `customers` at
    # module load.
    #
    # ⚠ **THEY ARE ENFORCED HERE BECAUSE `document_store.store()` DOES NOT
    # ENFORCE THEM.** Read at source rather than trusted (hard-won law 1):
    # `store()` refuses an empty payload, a missing content type and an unknown
    # kind or source, and it measures no bytes and checks no media type.
    from apps.customers.account_documents import (  # noqa: PLC0415
        ALLOWED_CONTENT_TYPES,
        ALLOWED_EXTENSIONS,
        MAX_UPLOAD_BYTES,
    )

    row = _get_or_refuse(supplier_invoice_id)
    if row.status != models.SUPPLIER_INVOICE_CAPTURED:
        raise CostCaptureError(
            "a voided purchase takes no new document. The documents already on it stay "
            "readable — a void is a disposition, not an erasure (BR-LED-035).",
            br_ref="BR-LED-035",
        )

    name = str(filename or "").strip()
    if not name:
        raise CostCaptureError("a document needs a file name.")

    # ⚠ `image/jpeg; charset=binary` is a legal header. Compare the MEDIA TYPE,
    # never the whole header, or a browser that adds a parameter gets a refusal
    # for a file that is on the list.
    media_type = str(content_type or "").split(";")[0].strip().lower()
    if media_type not in ALLOWED_CONTENT_TYPES:
        raise CostCaptureError(
            f"{media_type or 'unknown'} is not a kind of file this product stores. It takes "
            f"{', '.join(ALLOWED_EXTENSIONS)}.",
            br_ref="BR-SHL-031",
        )
    payload = bytes(content or b"")
    if not payload:
        raise CostCaptureError("the file is empty.", br_ref="BR-SHL-031")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise CostCaptureError(
            f"the file is larger than "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            br_ref="BR-SHL-031",
        )

    # The display name mirrors the storage key so an unpacked export reads like
    # the bucket — the shape `account_documents` already settled. The SUPPLIER
    # and the REFERENCE are what a person looking for this file would search,
    # and only this module holds them (`document_store` refuses to invent one).
    moment = timezone.now()
    safe = name.replace("/", "-").replace("\\", "-").lstrip(".")
    marker = (row.reference or str(row.pk)).strip().replace("/", "-")
    display_name = f"supplier-invoices/{moment:%Y}/{moment:%m}/{marker}-{safe}"

    already = document_models.StoredDocument.objects.filter(
        source_type=document_models.SOURCE_SUPPLIER_INVOICE,
        source_id=str(row.pk),
        content_type=media_type,
    ).exists()
    if already:
        raise CostCaptureError(
            f"this purchase already has a {media_type} document, and a stored document is "
            "write-once. Void the purchase and capture it again, or attach the paperwork "
            "in a different format.",
            br_ref="BR-SHL-031",
        )

    ref = document_store.store(
        kind=document_models.KIND_SUPPLIER_INVOICE,
        source_type=document_models.SOURCE_SUPPLIER_INVOICE,
        source_id=row.pk,
        content_type=media_type,
        display_name=display_name,
        payload=payload,
        actor_user_id=getattr(actor, "id", None),
        process="ledger.cost_capture.attach_supplier_invoice_document",
    )

    # CLAUDE.md hard rule 7 — capturing what a utility bought is a money path,
    # and attaching the evidence for it is part of that path.
    core_audit.money_action(
        actor,
        AUDIT_DOCUMENT_ATTACHED,
        "supplier_invoice",
        str(row.pk),
        after={
            "document_id": str(ref.id),
            "display_name": display_name,
            "content_type": media_type,
            "size_bytes": len(payload),
        },
    )
    return supplier_invoice_documents(row.pk)


def documents_for_page(rows: Any) -> dict[str, tuple[dict[str, Any], ...]]:
    """`{purchase id: its documents}` for a whole page, in ONE query.

    ⚠ **THE EMPTY TUPLE IS A REAL ANSWER.** A purchase with nothing attached is
    the ORDINARY case — every row captured before 2026-09-25 is one — so the
    caller gets `()` rather than a missing key, and the screen shows no
    paperclip rather than a stated absence shouting on every row (B14 rule 32).
    """
    ids = [str(row.pk) for row in rows]
    if not ids:
        return {}
    found: dict[str, list[dict[str, Any]]] = {}
    for doc in document_models.StoredDocument.objects.filter(
        source_type=document_models.SOURCE_SUPPLIER_INVOICE,
        source_id__in=ids,
    ).order_by("-stored_at"):
        found.setdefault(str(doc.source_id), []).append(_document_row(doc))
    return {key: tuple(value) for key, value in found.items()}


def _document_row(doc: Any) -> dict[str, Any]:
    """One stored document as a screen sees it — metadata, never bytes.

    B14 rule 31 — the id is the KEY a download is asked for by and is never the
    visible value of a field; the NAME is what a clerk reads, and it is the part
    after the dated prefix the storage key mirrors.
    """
    return {
        "id": str(doc.pk),
        "name": str(doc.display_name or "").rsplit("/", 1)[-1],
        "content_type": doc.content_type,
        "size_bytes": doc.byte_length,
        "stored_at": doc.stored_at.isoformat() if doc.stored_at else None,
    }


def supplier_invoice_documents(supplier_invoice_id: Any) -> dict[str, Any]:
    """Every document attached to one purchase — metadata only, never bytes.

    ⚠ **A LIST AND NOT A LOOKUP, DELIBERATELY** — and the list is short by
    schema rather than by choice. `uq_stored_documents_filed` allows one artefact
    per CONTENT TYPE on a source, so a purchase can hold a PDF and a scan and no
    more. `document_store.for_source()` answers *the* document and would have to
    be told which; a list needs no such argument, and an empty list is the honest
    answer for a purchase with nothing attached.
    """
    rows = document_models.StoredDocument.objects.filter(
        source_type=document_models.SOURCE_SUPPLIER_INVOICE,
        source_id=str(supplier_invoice_id),
    ).order_by("-stored_at")
    return {"documents": tuple(_document_row(doc) for doc in rows)}



# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-018@d744841 (sha1[:7], newline-joined in order; US-LED-019 ships in this file too — the authorities this file was written from, in order: 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-028..036 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md US-LED-018/019 · 04-docs/05-modules/09-ledger/03-field-map.md §"Cost-of-service capture" · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-11/LE-13 · 08-qa/01-e2e/journeys/J25-cost-of-service-month.md · 12-governance/01-open-questions.md OQ-200/201/203)
# generated: 2026-08-15 by the ledger AP-capture lane · AMENDED 2026-09-02 by the CR-060 T6/T6a lane (SETTLEMENT: `record_settlement` + `post_settlement_to_journal` + `settlement_state` + `_refuse_if_settled`, `paid_on` on the row, in the audit snapshot and refused by name in the edit form; the module docstring's posting-boundary section rewritten to carry BOTH rulings; the capture result's posting sentence amended. TWO STALE CLAIMS IN THIS TRAILER CORRECTED AT THE SAME TIME, and they were stale before this lane arrived: `post_capture_to_journal` has not raised `NotImplementedError("OQ-200")` since 2026-08-16 — it is a ruled no-op — and `_refuse_after_close` does not exist under that name and does not raise `NotImplementedError("OQ-203")`; the question closed the same day. A trailer describing stubs that were replaced by rulings is hard-won law 1 in the lifecycle block itself)
# checklist: A✔ B✔ C✔ D✔(S73's endpoints exist — GET/POST /finance/cost-of-service, PATCH …/{id} which now takes paid_on + settled_at, POST …/{id}/void) E=deferred(the S73 "Paid on" field and R8's two state sentences are new catalogue strings and the locale files are another lane's — keys and English text reported to the caller, the CR-060 T4(e) posture) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row OPENED 2026-09-02 for the settlement change)
# gates: PROVED RED BEFORE GREEN — every guard in this file was driven by
#         breaking the thing it guards. The four that bite hardest: the
#         volume-without-unit refusal removed → a 400,000 with NULL unit was
#         accepted (`Failed: DID NOT RAISE CostCaptureError`); the void's
#         footer exclusion removed → `assert Decimal('51902.50') ==
#         Decimal('51747.50')`; `close.resolve_entry_date` replaced by the
#         requested date → `assert [date(2026,7,1), date(2026,7,31)] ==
#         [date(2026,8,1), date(2026,8,31)]`; the OQ-203 stub replaced by an
#         edit → the closed month moved. See tests/test_us_led_018_capture.py
#         and tests/test_us_led_019_register.py
# exceptions: (1) ⚠ **CORRECTED 2026-09-02 — THE POSTING BOUNDARY IS NOT A
#         STUB AND HAS NOT BEEN SINCE 2026-08-16.** This read *"post_capture_to_
#         journal raises NotImplementedError('OQ-200')"*; OQ-200 CLOSED that day
#         and the function became a RULED no-op. **A CAPTURE STILL POSTS
#         NOTHING. A SETTLEMENT POSTS** — `record_settlement` posts DR the cost
#         account / CR cash when a clerk records `paid_on` (CR-060 C1, PO ruling
#         2026-09-02). Posting July's $51,902.50 moves LE-1/GT-51 from
#         598.69 = 598.69 to 52,351.19 = 52,351.19 (CR-060 projects 52,501.19,
#         which is 150.00 high — see the module docstring), which moves a
#         finance-signed
#         worked example and takes HUMAN-GUIDE §6 — owed at the FIRST
#         settlement, not at this code's landing, because nothing posts while
#         no row carries a `paid_on` · (1b) **WHAT A SETTLED INVOICE'S LATER
#         CORRECTION OR VOID SHOULD DO IS A STUB** — `_refuse_if_settled` raises
#         NotImplementedError("OQ-1350") for the four facts the entry copied
#         (amount, currency, cost account, building) and for a void. Reverse and
#         re-post, post a delta, or refuse are all defensible and none is ruled ·
#         (2) ⚠ **CORRECTED 2026-09-02 — THE AFTER-CLOSE EDIT/VOID IS NOT A
#         STUB EITHER.** This read *"`_refuse_after_close` raises
#         NotImplementedError('OQ-203')"*; there is no such function and OQ-203
#         CLOSED on 2026-08-16 (*"Yes it can be corrected"*).
#         `_require_after_close_reason` makes the REASON the condition and
#         `_after_close_note` names the exported batch that no longer matches ·
#         (3) A THREE-DECIMAL AMOUNT IS STORED EXACTLY AND REPORTED, NOT
#         REFUSED — US-LED-018 §7 rules that the amount is *"stored exactly as
#         keyed at six decimals and is never rounded by the ledger"*, and
#         BR-LED-025's >2dp refusal is a POSTING-boundary rule whose boundary is
#         stubbed under OQ-200. The row comes back carrying
#         `amount_carries_more_than_two_decimals` so it is flagged rather than
#         silent. ⚠ **AND THAT DAY HAS ARRIVED, IN A DIFFERENT FORM THAN THIS
#         LINE PREDICTED (2026-09-02):** such a capture is now UNSETTLEABLE —
#         `posting.post` refuses it under BR-LED-025 (*"Refuse and make the
#         caller round"*), naming the amount. The warning that was already on
#         the row is the warning a clerk needed. REPORTED · (4) `volume_unit` IS FREE TEXT and the
#         reconciliation compares it as an EXACT STRING: the per-service
#         purchase-unit vocabulary and whether a signed conversion factor may be
#         applied are OQ-201, OPEN. No enum, no normalisation beyond stripping
#         whitespace (`MMBtu` and `kWh` carry meaning in their capitals), no
#         conversion · (5) THE ROLE GATE IS A READING — BR-LED-003's
#         System-Admin/Billing-Clerk substitution was ratified for the REVERSAL
#         (OQ-175) and capture was not separately raised. Carried, flagged, not
#         presented as ratified — the US-LED-014/015 posture · (6) ⚠ **CORRECTED
#         2026-09-25 — `register()` IS PAGED** (`DEF-LED-6710`, `NFR-3`). This
#         read *"NO PAGINATION on `register()`: the footer is a whole-set figure
#         a page cannot give"*; the footer is a SQL aggregate over the FILTERED
#         set and a page underneath it moves nothing, which is the same premise
#         `CR-138` `P4` withdrew for `/outstandings`. (OQ-204 is the S74
#         DOWNLOAD pipeline and is untouched by this.) REPORTED · (7) editing the SERVICE does not re-default the
#         GL account: BR-LED-038 makes the pointer a tenant's to override and
#         silently re-pointing a hand-classified purchase would undo their
#         choice without saying so
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

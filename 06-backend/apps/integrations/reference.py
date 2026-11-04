# ── Trace ──────────────────────────────────────────────
# Story:    CR-110-BRC04 phase 2 wave 1 — `GET /api/{utility}/partner/v1/
#           reference`, the fifth partner endpoint. PO 2026-09-16, verbatim:
#           *"you ahve to extend the defination of codes so that partner can
#           resolve all codes at there end otherwise they will ahve an issues"*
# Rules:    BR-INT-037 (data, never a branch on a provider) · BR-INT-054 (we
#           publish OUR vocabulary; translating it into theirs is Runbooks') ·
#           BR-TEN-003 (the tenant is the path; `company_id` is verified and
#           never used to select) · CLAUDE.md hard rule 1 (no tenant argument
#           on a tenant read) · B14 rule 31 (no database id is a visible value)
# Tests:    06-backend/tests/test_cr110_phase2_partner_reference.py
# Impacts:  apps/integrations/partner_api.py (the one caller) ·
#           apps/billing/models.LINE_KINDS (minted for this) ·
#           apps/integrations/mappings.our_choices (reused, not re-read)
# ───────────────────────────────────────────────────────
"""EVERY CODE WE CAN PUT ON A PARTNER PAYLOAD, WITH ITS MEANING.

A partner pulls this once, caches it, and never meets a value it cannot
resolve. That is the whole job, and the PO named the failure it prevents:
without it a finance system meets `storm_water` or `backbill` on a bill and has
to guess, or stop.

⚠ **EVERY LIST IS GENERATED AND NOT ONE OF THEM IS TYPED HERE.** That is not
tidiness — it is the only thing that makes a partner's parser survive us. A
twelfth utility service, a seventh bill type, a tenant's new tender or a new
account status must appear on this endpoint **with no change to this file and
no change to the endpoint**, because the day they do not is the day a partner's
integration silently stops resolving a code that is already on our bills.

    kind            apps.billing.models.LINE_KINDS          closed vocabulary
    service         tenancy `services` table, active        eleven today
    billType        apps.billing.models.BILL_TYPES          closed vocabulary
    invoiceStatus   apps.billing.models.INVOICE_STATUSES    closed vocabulary
    tender          the tenant's own `payment_methods`      their list
    accountStatus   the tenant's own `account_statuses`     their list
    transactionType apps.ledger.models.JE_TYPES             closed vocabulary
    paymentType     apps.payments.models.PAYMENT_TYPES      closed vocabulary
    projectType     apps.payments.models.PAYMENT_PURPOSES   closed vocabulary
    paymentPayType  apps.payments.models.PAYMENT_STATUSES   closed vocabulary

⚠ **THE LAST THREE ARRIVED WITH WAVE 4 (`CR-110-BRC04` phase 2), AND THEY ARE
NAMED FOR THE FIELD THEY RESOLVE.** The payment payload carries four coded
fields — `type`, `projectType`, `tenderType`, `paymentPayType` — and a partner
holding a code looks it up by the name of the field it was on. `tenderType`
resolves through the older key `tender`, which is left exactly as it is: nothing
in this product is renamed to make a listing tidy.

**Three of the seven are the TENANT'S OWN ROWS** — service is the platform
catalogue, tender and account status are lookups a clerk edits on Settings — so
two utilities legitimately get different answers from the same endpoint, and
that is why it is a tenant read behind the same door as the other four rather
than a static document.

WHERE THE LABELS COME FROM, AND WHY TWO KINDS
----------------------------------------------
A row that IS a row carries its own word: a service's `name`, a payment
method's `name`, an account status's `name`. Nothing is written twice, and a
clerk who renames *Bank transfer* to *ACH* changes what the partner reads.

A CLOSED vocabulary is a tuple of bare strings and has no name column, so the
four below carry an explicit word each. **That is the one place a new code can
arrive with nothing to say about it**, and it is exactly the shape
`DEF-INT-5500` cost us one screen along — a generated list growing a member
with no word written for it, invisible to every check because the list is
generated on purpose.

⚠ **SO THE RUNTIME NEVER REFUSES AND THE TEST ALWAYS DOES.** A code with no
word is served with one derived from the code itself, because a partner's
nightly pull must not fail over our bookkeeping; and
`test_cr110_phase2_partner_reference.py` goes RED the moment a vocabulary holds
a code this file has no word for, naming it. A refusal here would take a
working integration off the air to report a missing sentence.

⚠ **AND THE FALSE PASS IS NAMED AND REFUSED.** A lane silencing that test by
writing `"backbill": "backbill"` would turn it green and publish a label that
tells a partner nothing. The test asserts no word is its own code.

WHAT IS NOT HERE
-----------------
Their words for our things. `BR-INT-054` and `CR-069` §20.4 put that in
Runbooks, and the PO's ruling that struck the clerk mapping screen says why in
one sentence: *"this will not be required in case of they read cases - we just
need to actiavte connectors and issue a key thats all"*. **For a READ the
partner maps at THEIR end, from this endpoint.** Ours is published, never
translated — which is the whole reason this file exists.
"""

from __future__ import annotations

from typing import Any

#: The seven keys of the payload, in the order the PO's own specification
#: lists them. A tuple so a test can assert the set without retyping it, and so
#: an eighth vocabulary cannot be added without this line moving.
REFERENCE_KEYS = (
    "kind",
    "service",
    "billType",
    "invoiceStatus",
    "tender",
    "accountStatus",
    "transactionType",
    "paymentType",
    "projectType",
    "paymentPayType",
)

# ═══════════════════════════════════════════════════════════════════════════
# The words for the four CLOSED vocabularies
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ A WORD PER CODE, AND A TEST THAT FAILS WHEN ONE IS MISSING. See the module
# docstring: these four are tuples of bare strings, so unlike a service or a
# tender there is no `name` column to read. Every word below is written for a
# PARTNER'S ACCOUNTANT rather than for a clerk — *"Corrected by a later bill"*
# says what to do with the row, where *"Corrected"* only names it.
#
# ⚠ **THREE OF THESE WERE WRITTEN AS THE CODE'S OWN WORD AND THE TEST CAUGHT
# THEM**, which is the whole reason `test_no_label_is_its_own_code` exists and
# is worth recording rather than quietly fixing: `tax` → *"Tax"*, `rebill` →
# *"Rebill"* and `issued` → *"Issued"* each passed the *has a word* check and
# told a partner's accountant nothing the code had not already said. They read
# *"A tax we collect"*, *"Replaces an earlier bill"* and *"Issued and owing"*
# now. A check that only asks whether a value is PRESENT is the shape law 7
# calls a false pass, and this one was written to refuse it on its author.

#: `apps.billing.models.LINE_KINDS` — what one line of a bill IS.
LINE_KIND_LABELS = {
    "usage": "What was used",
    "base": "Base charge",
    "fee": "A one-off charge",
    "tax": "A tax we collect",
    "adjustment": "A correction to this bill",
    "minimum": "The tariff's minimum",
}

#: `apps.billing.models.BILL_TYPES` — what KIND of bill this document is.
BILL_TYPE_LABELS = {
    "cycle": "A normal period bill",
    "first": "The first bill on a new account",
    "final": "The closing bill",
    "rebill": "Replaces an earlier bill",
    "backbill": "A charge for an earlier period",
    "penalty": "A late charge",
    "fee": "Charges only, no period",
}

#: `apps.billing.models.INVOICE_STATUSES`.
#:
#: ⚠ **`draft` IS NAMED HERE AND IS NEVER SERVED**, and that is deliberate
#: rather than an oversight: the reference publishes the whole vocabulary of
#: the column, and `seams/billing.COLLECTABLE_STATUSES` is what decides which
#: of them leave the building. Publishing five and sending four is honest;
#: publishing four would tell a partner our column has four values.
INVOICE_STATUS_LABELS = {
    "draft": "Not issued — never sent to you",
    "issued": "Issued and owing",
    "paid": "Paid in full",
    "void": "Cancelled — reverse it",
    "corrected": "Corrected by a later bill",
}

#: `apps.payments.models.PAYMENT_TYPES` — the payment payload's `type`. What
#: the ROW is: money that came in, a credit the utility granted, or a correction.
PAYMENT_TYPE_LABELS = {
    "payment": "Money the customer paid",
    "credit": "A credit the utility granted",
    "adjustment": "A correction to the account",
}

#: `apps.payments.models.PAYMENT_PURPOSES` — the payment payload's
#: `projectType`. What the money was FOR, which is the question a partner's
#: project or fund dimension is asking.
PAYMENT_PURPOSE_LABELS = {
    "bill": "Paid against a bill",
    "deposit": "A security deposit held",
    "plan_down": "The first payment of a plan",
    "prepay": "Paid before it was billed",
}

#: `apps.payments.models.PAYMENT_STATUSES` — the payment payload's
#: `paymentPayType`. Where the money STANDS.
#:
#: ⚠ **ALL SIX ARE PUBLISHED AND ONLY SOME EVER LEAVE**, exactly as `draft` is
#: published under `invoiceStatus` and never served: this endpoint describes the
#: whole vocabulary of the column and `seams/payments.COLLECTABLE_STATUSES`
#: decides which of them reach a partner. Publishing six and sending fewer is
#: honest; publishing only what we send would tell a partner our column has
#: fewer values than it does.
#:
#: ⚠ **`cancelled` ARRIVED WITH `payments/0035` (`CR-137-BRC07` `P3.5`) AND ITS
#: SENTENCE ARRIVED IN THE SAME COMMIT, WHICH IS THE WHOLE POINT OF THIS MAP.**
#: `PAYMENT_STATUSES` grew by one and `test_every_closed_code_has_a_label`
#: would have gone red naming it — the missing sentence is somebody's problem
#: the same day rather than a partner's accountant's problem next quarter. It
#: is NOT in `COLLECTABLE_STATUSES`, so no partner is ever handed a cancelled
#: payment as a receipt; it is published because the column can hold it.
#:
#: ⚠ **`posted` AND `cleared` WERE RE-WORDED ON 2026-10-21 (`CR-186-BRC10`)**,
#: because their meaning moved: every payment is now `posted` when it is taken
#: and applied to the account, and `cleared` only when the utility reconciles
#: its deposit batch with the bank statement (PO, decision log 2026-10-21).
#: *"Settled with the bank"* read as *the money arrived*, which is what
#: `cleared` meant before; *"Recorded against the account"* undersold a status
#: that now moves the balance. The CODES did not move — a partner keys on them.
PAYMENT_STATUS_LABELS = {
    "processing": "Taken, not settled yet",
    "cleared": "Reconciled with the bank statement",
    "failed": "Never settled — reverse it",
    "reversed": "Taken back afterwards",
    "posted": "Taken and applied to the account",
    "cancelled": "Taken by mistake, undone",
}

#: `apps.ledger.models.JE_TYPES` — what kind of journal entry a row belongs to.
TRANSACTION_TYPE_LABELS = {
    "standard": "An ordinary entry",
    "accrual": "An accrual, reversed next period",
    "reversing": "The reversal of an earlier entry",
}


def derived_label(code: str) -> str:
    """The word for a code nobody wrote one for — `storm_water` → *Storm water*.

    ⚠ **THIS IS A FALLBACK AND NEVER AN ANSWER.** It exists so a partner's
    nightly pull cannot fail because we minted a code and forgot a sentence;
    the test is what makes the missing sentence somebody's problem the same
    day. A lane that finds this function being *used* has found a defect, not a
    feature — the module docstring says which test names it.
    """
    return str(code).replace("_", " ").strip().capitalize() or str(code)


def _closed(codes: Any, labels: dict[str, str]) -> list[dict[str, str]]:
    """One closed vocabulary as `[{code, label}]`, in its declared order.

    The order is the vocabulary's own and is not sorted: `INVOICE_STATUSES`
    runs draft → issued → paid → void → corrected, which is a bill's life, and
    re-sorting it alphabetically would throw that away for nothing.
    """
    return [{"code": str(one), "label": labels.get(str(one)) or derived_label(one)} for one in codes]


# ═══════════════════════════════════════════════════════════════════════════
# The four closed vocabularies — read from their owners, never copied
# ═══════════════════════════════════════════════════════════════════════════


def _billing() -> Any:
    """Imported inside the call so the module graph stays a DAG — integrations
    loads at `AppConfig.ready()` and billing must not have to."""
    from apps.billing import models as billing_models

    return billing_models


def _ledger() -> Any:
    from apps.ledger import models as ledger_models

    return ledger_models


def _payments() -> Any:
    from apps.payments import models as payments_models

    return payments_models


def kinds() -> list[dict[str, str]]:
    """Every `invoice_lines.kind` this product can emit."""
    return _closed(_billing().LINE_KINDS, LINE_KIND_LABELS)


def bill_types() -> list[dict[str, str]]:
    """Every `invoices.bill_type`."""
    return _closed(_billing().BILL_TYPES, BILL_TYPE_LABELS)


def invoice_statuses() -> list[dict[str, str]]:
    """Every `invoices.status` — see `INVOICE_STATUS_LABELS` on why five."""
    return _closed(_billing().INVOICE_STATUSES, INVOICE_STATUS_LABELS)


def transaction_types() -> list[dict[str, str]]:
    """Every `journal_entries.type`."""
    return _closed(_ledger().JE_TYPES, TRANSACTION_TYPE_LABELS)


def payment_types() -> list[dict[str, str]]:
    """Every `payments.type` — the payment payload's `type`."""
    return _closed(_payments().PAYMENT_TYPES, PAYMENT_TYPE_LABELS)


def payment_purposes() -> list[dict[str, str]]:
    """Every `payments.purpose` — the payment payload's `projectType`."""
    return _closed(_payments().PAYMENT_PURPOSES, PAYMENT_PURPOSE_LABELS)


def payment_statuses() -> list[dict[str, str]]:
    """Every `payments.status` — the payment payload's `paymentPayType`."""
    return _closed(_payments().PAYMENT_STATUSES, PAYMENT_STATUS_LABELS)


# ═══════════════════════════════════════════════════════════════════════════
# The three that are ROWS — the tenant's own lists
# ═══════════════════════════════════════════════════════════════════════════


def _from_choices(tenant_id: Any, entity_type: str) -> list[dict[str, str]]:
    """A lookup list through `mappings.our_choices`, which already owns the
    question *what values of ours could a partner's word mean*.

    ⚠ **REUSED RATHER THAN RE-READ, AND THAT IS THE POINT.** `our_choices`
    already filters `active=True` and orders the rows; a second query here
    would be a second answer to one question, free to disagree the first time
    either moved. It returns `{value, label, id}`; **the id is dropped**, because
    a partner keyed on our uuid is coupled to our storage for ever (the same
    reasoning `seams/payments.as_record` gives for serving `payment_no`) and
    because B14 rule 31's argument travels past screens.
    """
    from apps.integrations import mappings

    return [
        {"code": str(one["value"]), "label": str(one["label"] or one["value"])}
        for one in mappings.our_choices(tenant_id, entity_type)
    ]


def services(tenant_id: Any) -> list[dict[str, str]]:
    """The ELEVEN utility services, from the platform catalogue.

    ⚠ **THIS IS THE LIST THE WHOLE ENDPOINT IS ABOUT.** `fire` was appended at
    position 11 on 2026-09-02 and nothing was renumbered; a twelfth will arrive
    the same way, as a row. Read from `services` so the day it does, a partner
    that pulled this endpoint that morning already knows the word.
    """
    return _from_choices(tenant_id, "service")


def tenders(tenant_id: Any) -> list[dict[str, str]]:
    """The utility's OWN payment methods (`payment_methods`, active only).

    Two utilities answer differently and that is correct: a tenant adds
    *Bill-pay portal* on Settings and uses it the same afternoon
    (`US-PAY-001` TC-3), and the partner reading this endpoint tomorrow
    resolves it.
    """
    return _from_choices(tenant_id, "tender")


def account_statuses(tenant_id: Any) -> list[dict[str, str]]:
    """The utility's OWN account statuses (`account_statuses`, active only).

    ⚠ **A LOOKUP AND NOT AN ENUM, WHICH IS WHY IT IS HERE AT ALL.**
    `BR-CUS-055` made this tenant-extensible precisely so a utility can add
    *Legal hold*; a partner given a fixed list of five would meet the sixth on
    a customer payload and have nothing to do with it.

    ⚠ **THE BEHAVIOUR CLASS DOES NOT TRAVEL.** `billable`,
    `billable_base_only`, `non_billable` and `terminal` are how OUR billing
    keys off a tenant's label; they are not a code a partner meets on a
    payload, and publishing them would invite a finance system to make billing
    decisions from them.
    """
    from apps.customers import models as customers_models

    rows = (
        customers_models.AccountStatus.objects.filter(tenant_id=tenant_id, active=True)
        .order_by("name", "code")
        .values_list("code", "name")
    )
    return [{"code": str(code), "label": str(name or code)} for code, name in rows]


# ═══════════════════════════════════════════════════════════════════════════
# The payload
# ═══════════════════════════════════════════════════════════════════════════


def payload(tenant_id: Any) -> dict[str, list[dict[str, str]]]:
    """The whole reference document for ONE utility.

    ⚠ **`tenant_id` IS PASSED IN RATHER THAN READ HERE, AND IT IS THE CALLER'S
    OWN TENANT.** `partner_api` takes it from the authenticated caller's
    connection — key → connection → tenant — never from the `company_id` the
    request carried, which is VERIFIED and never used to select (`BR-TEN-003`:
    *"the ONLY input consulted is the request path; tenant_id in a
    header/param/body is never read"*). Whoever can send one utility's id can
    send another's.

    ⚠ **THE KEYS ARE BUILT FROM `REFERENCE_KEYS`, SO AN EIGHTH VOCABULARY
    CANNOT BE ADDED WITHOUT THAT TUPLE MOVING** — and the test asserts the
    payload's key set against it, which is how the published shape and the
    declared shape cannot drift.
    """
    built = {
        "kind": kinds(),
        "service": services(tenant_id),
        "billType": bill_types(),
        "invoiceStatus": invoice_statuses(),
        "tender": tenders(tenant_id),
        "accountStatus": account_statuses(tenant_id),
        "transactionType": transaction_types(),
        "paymentType": payment_types(),
        "projectType": payment_purposes(),
        "paymentPayType": payment_statuses(),
    }
    return {key: built[key] for key in REFERENCE_KEYS}


__all__ = [
    "BILL_TYPE_LABELS",
    "INVOICE_STATUS_LABELS",
    "LINE_KIND_LABELS",
    "PAYMENT_PURPOSE_LABELS",
    "PAYMENT_STATUS_LABELS",
    "PAYMENT_TYPE_LABELS",
    "REFERENCE_KEYS",
    "TRANSACTION_TYPE_LABELS",
    "account_statuses",
    "bill_types",
    "derived_label",
    "invoice_statuses",
    "kinds",
    "payload",
    "payment_purposes",
    "payment_statuses",
    "payment_types",
    "services",
    "tenders",
    "transaction_types",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-110-BRC04 phase 2 wave 1 (PO rulings of 2026-09-16)
# generated: 2026-09-16 by the CR-110-BRC04 phase 2 lane A build lane
# checklist: A✔ B=n/a(no screen — this is a partner document) C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_cr110_phase2_partner_reference.py
# exceptions: reads four neighbours by name rather than through four one-function
#   seam files — `mappings.py` in this module already does exactly this for the
#   same lookups, and three sibling lanes hold `seams/customers.py`,
#   `seams/billing.py` and `seams/ledger.py` open this hour (law 11)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

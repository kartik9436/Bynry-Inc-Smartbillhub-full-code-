# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-029 (stage 6 of seven)   Screens: S31 · S30
#           AMENDED 2026-08-11 (budget-billing lane): stage 6 now stamps
#           US-BIL-019's budget block onto `bill_payload` — the three
#           WE-8 columns and the amount the PO's ruling of 2026-08-11
#           makes DUE. US-BIL-019 is deliberately NOT added to the Story
#           line: G10 reads a Trace-header US-ID as "this file ships that
#           story's TCs" and the story's test cases live beside
#           apps/billing/budget.py, which is where the work is (the same
#           reasoning late_fee.py and models.py both record).
# Rules:    BR-BIL-037 (one input contract, one output contract) · BR-BIL-039
#           (stages 1–5 are pure; ONLY STAGE 6 WRITES) · BR-BIL-004 (a draft is
#           freely discardable; immutability starts at ISSUE) · BR-BIL-063 (the
#           number is ALLOCATED HERE, at draft creation — PO 2026-08-11) ·
#           BR-BIL-023 (drafts are discardable free) · BR-CUS-040 (a reprint renders the issued
#           document) · BR-BIL-010 (the GL stamp is keyed on the line's SERVICE
#           and, for tax, its AUTHORITY — both written here) · BR-BIL-069 (a tax
#           line names its authority — PO 2026-08-11, OQ-116) · CLAUDE.md rule 2
#           (money + currency) · rule 3 (units)
# Tests:    06-backend/tests/test_us_bil_029_assemble.py ·
#           06-backend/tests/test_br_bil_069_tax_authority_gl.py
# Impacts:  apps/billing/models.Invoice / InvoiceLine · the issue path
#           (US-BIL-005) which freezes what this wrote · core.numbering (the
#           tenant series this now allocates from) · apps/billing/tenancy_seam
#           (the catalog read that turns a service CODE into its id)
# ───────────────────────────────────────────────────────
"""Stage 6 — turn priced lines into a DRAFT bill. The first stage that writes.

Stages 1–5 are pure and produce numbers. This one is where those numbers
become a row a customer will eventually see, which is why BR-BIL-039 gives it
the write and gives it alone: one place to look when asking "what did the run
actually persist?", and five stages that can be replayed at will because they
persisted nothing.

WHAT IT PRODUCES AND WHAT IT DOES NOT

It produces a **draft**. Not a bill — a draft. The difference is the whole of
BR-BIL-004: a draft is freely editable and can be discarded without trace.
Nothing here is immutable, and nothing here has been sent to anyone. Issue is a
separate act (US-BIL-005) that sets the due date, stamps the GL account and the
template, and freezes it.

The draft DOES carry its number (BR-BIL-063, PO ruling 2026-08-11). That is a
reversal: this file previously left it NULL, on the reasoning that a number a
customer never sees is a number wasted. The PO weighed that against simplicity
and chose the number — *"if not use thats okay we will lose it; its okay; dont
over complicate."* Because a retry REPLACES the draft (below), each retry
spends more numbers, and the series is documented as gap-tolerant.

A consequence worth seeing before it surprises someone: the number is rendered
from the SERVICE date, not from today, so a June bill drafted in July numbers
as June's. That is BR-TEN-043's event-time law, and it is also what keeps a
re-run of a historical period reproducible.

That separation is what makes the PO's phase 3 possible — *"once billing is
complete show immediately bills that are break and why; allow user to retry
immediately by fixing the issue"*. A retry re-runs stages 2–6 and REPLACES the
draft. If stage 6 issued, a retry would mean voiding a real bill and issuing a
second one, and a customer would receive both.

THE SNAPSHOT (PO ruling 2026-08-11: *"you have to keep lock data for that bill
and save the instance"*). The payload is assembled HERE, at draft time, from
what the gather step captured — not at issue, and never by re-reading live
rows. Assembling it at issue would re-join whatever the customer record says
by then, which is exactly the failure the ruling exists to prevent: Sarah
marries between the run and the release, and the bill goes out in her new name
for a period billed under her old one. The draft carries what was TRUE WHEN IT
WAS PRICED.

IDEMPOTENCY. Re-running stage 6 for an account already drafted in this run
REPLACES that draft rather than adding a second one. A run interrupted halfway
and restarted must not produce two drafts per account — and because a draft is
discardable by rule, replacing is legitimate where replacing an issued bill
never would be.

IDENTITY: WHAT PRODUCED EACH LINE (added 2026-08-11 — BR-BIL-069, and the
reason the product could not issue a bill at all)
------------------------------------------------------------------------------
Every line this stage writes now records WHAT PRODUCED IT: `service_id` on
usage and base lines, `tax_id` on tax lines. Both are cheap facts and both were
missing, and the consequence was the entire product:

* **`service_id` was never written.** The column and its reviewed cross-module
  FK have existed since `0001`; nothing filled them. BR-BIL-010 resolves a
  usage or base line's revenue account FROM THE SERVICE, so every line of every
  real bill was unstampable and `issue` refused — correctly, and with a message
  about GL mapping that named a symptom rather than this cause. The issue lane
  found it, proved it (`test_us_bil_005_issue.py` ran the real stage 6, watched
  the bill refuse, set this one field by hand and watched the same bill issue
  cleanly) and could only REPORT it, because this file belonged to another
  lane. Hard-won law 2 in its quietest form: built, not wired, all tests green.
  It is also why the PO's per-service revenue requirement of 2026-08-11 was
  uncomputable from `invoice_lines`.
* **`tax_id` did not exist**, and that is the PO's ruling of 2026-08-11 closing
  OQ-116: *"For each atheority have separate account and tagging."* A $8.30 tax
  charge is usually three — State of Texas $6.29, Harris County $1.01, City of
  Katy $1.00 — and until the line named its tax, none of the three could find
  the authority's own 2200-series liability account.

Both are written HERE, at draft time, rather than at issue, and the distinction
matters: they are facts about **what was priced**, so they belong with the
snapshot. Issue does not record them — it RESOLVES them into a GL account and
freezes that (BR-BIL-010).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from apps.billing import models
from apps.billing import budget_service
from apps.billing import custom_snapshot as custom_snapshot_module
from apps.billing import customers_seam
from apps.billing import tenancy_seam
from apps.billing.contracts import MeasuredUsage
from apps.billing.exceptions import BillingRuleError
from core import numbering as core_numbering

#: The line kinds rating emits (rating_seam.RatedLine.kind). Billing stores
#: them verbatim: renaming across the seam would make a bill's own lines
#: disagree with the engine that priced them.
#: `discount` joined 2026-08-22 (DEF-502): R6's reduction is its OWN line with
#: a NEGATIVE amount and the discount's customer-facing name (BR-RAT-068 — the
#: bill shows the full tariff amount AND the reduction, so subsidy granted is
#: reportable). `invoice_lines.amount` carries no non-negative constraint, so
#: the row stores as-is. ⚠ ISSUE of a bill carrying one still REFUSES at
#: `issue._gl_account_for` — kind `discount` has no GL rule because the
#: designation a reduction posts to is unsigned (OQ-152's neighbourhood; filed
#: 2026-08-22) — so a discounted bill is a DRAFT the preview shows and a named
#: break at issue, never a mispost.
LINE_KINDS = ("usage", "base", "tax", "fee", "minimum_adjustment", "deposit", "discount")

#: The kinds whose GL account is resolved FROM THE SERVICE (BR-BIL-010: the
#: service → revenue map, with the optional usage/base split). A line of one of
#: these kinds that names no service cannot be stamped and refuses the whole
#: bill at issue, so stage 6 refuses to WRITE one — see `_service_id_for`.
SERVICE_BEARING_KINDS = ("usage", "base")


#: The payload's own money scale, as TEXT. A `Decimal` written into jsonb reads
#: back a FLOAT, which CLAUDE.md rule 2 forbids outright, so every figure below
#: is a string at the column's six places. This is a FORMAT and not a rounding
#: event (rule 2: round only at finalization or display) — the identical
#: decision `apps/billing/issue._money_text` and `release._money_text` take, for
#: the identical reason. DISPLAY is 2dp and happens in the browser.
SIX_PLACES = Decimal("0.000001")


def _payload_money(value: Any) -> str | None:
    """A money figure at the payload's six-place scale, as text. None stays None."""
    if value is None:
        return None
    return str(_decimal(value).quantize(SIX_PLACES))


def _payload_line(line: Any) -> dict:
    """ONE priced line, frozen into the stamped instance.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  DEF-969 — THE MONEY-INTEGRITY ALARM WAS RED ON EVERY BILL EVER      ║
    ║  ISSUED, AND THE MONEY WAS RIGHT EVERY TIME                          ║
    ╚══════════════════════════════════════════════════════════════════════╝
    BR-BIL-032 says the stamped instance ties out to its rows and that *"drift
    can never be silent"*. `pipeline.tie_out_document` implements it by
    comparing two totals AND two line counts — and until this commit
    `_snapshot_payload` stamped **no line set at all**. `_payload_lines` looked
    for `lines` / `invoice_lines` / `charge_lines` / `services[].lines`, found
    none of them, and correctly returned `[]`. So every bill compared 0 payload
    lines against N row lines and the panel told a clerk *"No — these do not
    match. Do not treat this bill as settled until someone has looked at it."*

    Measured on the live deployment at v2.61.1, on all 47 bills:
    *"Saved bill: 64.570000 USD over **0** line(s). Charge lines: 64.570000 USD
    over **6** line(s)."* — the totals EQUAL, the counts 0 and 6.

    **THE COST WAS THE ALARM.** This is the one check that catches a customer
    holding one number while the trial balance holds another, each internally
    consistent; a clerk who meets it on 47 of 47 bills learns to scroll past it.
    `apps/billing/issue.py`'s own exception list had been saying so in as many
    words — *"stage 6 stamps no total and no line set in the payload, so there
    is nothing to compare it TO"* — for a fortnight.

    **WHY THE REDUNDANCY IS STILL REAL.** The payload and the rows are written
    from the SAME `priced.lines` in the same function, a few lines apart, so
    they agree at birth by construction. What BR-BIL-032 guards is everything
    AFTERWARDS: a row added, a row lost, a payload forged or hand-edited, a
    migration that rewrites one side. That is the drift the rule exists for, and
    it is the drift that has no symptom until somebody disputes a bill.

    **WHAT IS FROZEN HERE IS WHAT A REPRINT MUST PRINT** (BR-BIL-030 — this
    payload is the document, forever): what was charged, how much of it, at what
    unit price, in what unit, and whether it was in the tax base. Every money
    figure is TEXT at six places (see `_payload_money`); the GL stamp is NOT
    here, because it is resolved at ISSUE and this runs at draft.
    """
    quantity = getattr(line, "quantity", None)
    return {
        "kind": getattr(line, "kind", None),
        "description": getattr(line, "description", ""),
        # A quantity NEVER travels without its unit (CLAUDE.md rule 3) — and the
        # invoice-line loop below REFUSES to write one that does, so a payload
        # line and its row cannot disagree about that either.
        "quantity": None if quantity is None else str(_decimal(quantity).quantize(SIX_PLACES)),
        "unit": getattr(line, "unit", None),
        "unit_price": _payload_money(getattr(line, "unit_price", None)),
        "amount": _payload_money(getattr(line, "amount", 0)),
        "taxable": bool(getattr(line, "taxable", False)),
        "service": getattr(line, "service", None) or None,
        # 2026-09-30 — the meter a line was priced for, where its service
        # carries two (two meters = two lines). A reprint must still say which
        # line is which meter. None everywhere else.
        "asset_id": getattr(line, "asset_id", None) or None,
    }


def _snapshot_payload(
    usage: MeasuredUsage,
    priced: Any,
    service_date: date,
    *,
    service_catalog: dict[str, tuple[str | None, str | None]] | None = None,
    addressee: dict[str, Any] | None = None,
    masthead: dict[str, Any] | None = None,
) -> dict:
    """What the document will print, frozen at pricing time.

    Deliberately built from the SUBSCRIPTION and the gathered snapshot rather
    than from live rows: this is the whole content of the PO's ruling. What
    goes in is what a reprint years later must show.

    `service_catalog` is `{code: (service_id, display name)}` for the ACTIVE
    platform catalogue, read ONCE by the caller (which already reads half of it
    to fill `invoice_lines.service_id`) and passed in so this function issues no
    query of its own. `DEF-2852` — see the `id`/`name` keys below. `None` is the
    same as an empty catalogue and stamps neither key with a value.

    `addressee` and `masthead` are `DEF-BIL-8283` — see `_stamp_addressee`.
    Read by the caller for the same reason the catalogue is.
    """
    catalog = service_catalog or {}
    subscription = usage.subscription
    payload = dict(subscription.snapshot)  # copy — never alias the input
    _stamp_addressee(payload, addressee or {}, masthead or {})
    payload.update(
        {
            # ── DEF-969 · THE LINE SET AND THE TOTAL (BR-BIL-032) ────────────
            # See `_payload_line`. `total` is stamped here as well and it is the
            # SECOND half of the same defect: `tie_out_document` reads
            # `payload["total"]` first and falls back to `payload["total_due"]`,
            # and until now only `total_due` existed — written at issue by
            # `issue._stamp_balance_forward` as *arrears + this period*. On an
            # account with a zero opening balance the two are equal and the
            # fallback looked harmless; on an account carrying arrears it
            # compared `previous_balance + current` against `invoices.total`
            # (current charges alone) and reported a FAILED TIE-OUT with a delta
            # exactly equal to the customer's arrears. `DEF-1064`.
            # `invoice.total` on the row beside this is set from the same
            # `priced.total`, so the two are one figure written twice.
            "total": _payload_money(getattr(priced, "total", 0)),
            "lines": [_payload_line(line) for line in getattr(priced, "lines", ())],
            "account_no": subscription.account_no,
            "service_date": service_date.isoformat(),
            "currency": subscription.currency,
            "plan": {
                "id": subscription.rate_plan_id,
                "name": subscription.rate_plan_name,
                "version": subscription.rate_plan_version,
            },
            "period": {
                "cycle_days": subscription.period.cycle_days,
                "service_days": subscription.period.service_days,
            },
            "tax_exempt": subscription.tax_exempt,
            # Which services were measured and which were not, so the document
            # can say "water: not read this period" instead of silently
            # omitting a service the customer pays for.
            "services": [
                {
                    "code": service.service_code,
                    # ── DEF-2852 · THE NAME THE CUSTOMER READS, FROZEN HERE ──
                    # The bill headed its charge blocks `Service 01a046d3-090d-
                    # 7eca-a4ac-87723f3a9e3f` where it should have said *Water*
                    # — a database id on the most public surface the product
                    # has, against B14 rule 31 (PO 2026-08-30: *"no Databse ID
                    # on screen - that is a rule"*).
                    #
                    # `documents._groups` groups by `invoice_lines.service_id`
                    # and had NOTHING that could turn that id into a word: this
                    # list carried the code and no id, so the two could not be
                    # matched up. `id` is what makes the match possible and
                    # `name` is what makes it readable.
                    #
                    # ⚠ **STAMPED, NOT JOINED, AND THAT IS THE WHOLE DESIGN.**
                    # The obvious repair is to look the name up while rendering.
                    # BR-BIL-030 forbids exactly that — a service renamed after
                    # issue would re-title a bill already sent — and
                    # `test_us_bil_022_documents.py::…tc2` pins the render to
                    # two queries, so a renderer reaching for the catalogue
                    # fails on the count as well as on the rule. Freezing it
                    # here is the same decision `read_id` below is frozen on.
                    #
                    # BOTH are `None` for a service the platform catalogue does
                    # not name — never invented, and never the id in the name's
                    # place, because *no name* is a better bill than a UUID.
                    "id": catalog.get(service.service_code, (None, None))[0],
                    "name": catalog.get(service.service_code, (None, None))[1],
                    "measured": service.consumption is not None,
                    "estimated": service.estimated,
                    "absent_reason": service.absent_reason,
                    # ── DEF-098 ────────────────────────────────────────────
                    # WHICH READ PRICED THIS SERVICE. Frozen here with the rest
                    # of the payload, and this is the ONLY place it can be
                    # frozen: `issue_invoice(invoice, …)` receives the Invoice
                    # and nothing else, so by issue time the readings are gone
                    # and the identity would be unrecoverable. Persisting it
                    # with the snapshot is what lets issue apply BR-MET-053's
                    # BILLED lock through `apps.metering.services
                    # .mark_read_billed` — the lock that makes a later
                    # correction take the J6 linkage path instead of a plain
                    # supersede.
                    #
                    # It also earns its place in a document snapshot on its own
                    # terms: BR-BIL-030 freezes what a bill priced, and WHICH
                    # METER READING produced the quantity is part of that. A
                    # reprint years later can name the read it charged for.
                    #
                    # `None` for a service with no read (no meter, no read,
                    # base-only) — never a placeholder.
                    "read_id": service.read_id,
                    # 🔒 DEF-BIL-9075 — EVERY reading the quantity was summed
                    # from (a period read partway through charges for each),
                    # frozen so issue locks them all. Empty → `read_id` alone.
                    "chain_read_ids": list(getattr(service, "chain_read_ids", ()) or ()),
                    # ── DEF-BIL-8280 (PO direction 2026-09-30) ──────────────
                    # A CLERK'S estimate (a Check decision) has no read behind
                    # it. The quantity is frozen here so that at ISSUE billing
                    # can hand it to Meter Reads' own service as an ESTIMATED
                    # reading (`metering_seam.record_billed_estimates`), which
                    # metering's true-up then subtracts from the next real
                    # read — otherwise the next bill charges it again. Absent
                    # on every other service, so no existing payload changes.
                    **(
                        {
                            "estimate": {
                                "amount": str(service.consumption.amount),
                                "unit": service.consumption.unit,
                            }
                        }
                        if service.estimated
                        and service.read_id is None
                        and service.consumption is not None
                        else {}
                    ),
                    # 2026-09-30 — one entry PER METER where a metered
                    # service carries two: each `MeasuredService` is one
                    # meter's config, and this names which. None elsewhere.
                    "asset_id": (
                        getattr(service, "asset_id", None)
                        or getattr(service.tariff, "asset_id", None)
                    ),
                    # 🔒 DEF-BIL-8244 — a meter swapped inside the period:
                    # each meter's own prior, current and usage, old meter
                    # first, summing to this service's quantity. Its read
                    # ids are locked at issue beside `read_id`. Absent on
                    # every other service, so no existing payload changes.
                    **(
                        {"meter_parts": [dict(part) for part in service.meter_parts]}
                        if getattr(service, "meter_parts", ())
                        else {}
                    ),
                }
                for service in usage.services
            ],
        }
    )
    return payload


#: `DEF-BIL-8283` — the keys a bill's customer is named and addressed by. The
#: gathered snapshot's value WINS where it holds one (a cycle bill's gather
#: stamps the first three from the same sources, and a run's own snapshot is
#: what the clerk reviewed); stage 6 fills only what nobody stamped.
ADDRESSEE_FILL_KEYS: tuple[str, ...] = ("customer_name", "service_address", "unit_label")
#: Stamped on every bill from the addressee answer: no earlier stage knows them.
ADDRESSEE_STAMP_KEYS: tuple[str, ...] = ("mailing_address", "mailing_address_source")
#: The utility's own identity — `documents._masthead`'s three keys. Stamped at
#: DRAFT so a draft's preview says who sends it; `issue._stamp_bill_header`
#: stamps them again at issue from the same read, and the ISSUE value is the
#: one frozen (a trading name changed while a draft sat is the new name).
MASTHEAD_STAMP_KEYS: tuple[str, ...] = ("utility_name", "utility_address", "utility_contact")


def _stamp_addressee(payload: dict, addressee: dict, masthead: dict) -> None:
    """`DEF-BIL-8283` — WHO THE BILL IS FOR, WHERE IT GOES, AND WHO SENT IT.

    🔒 HUMAN-REVIEW-PENDING (the payload is the bill, forever — BR-BIL-030).

    The PO's one-time fee bill BL-2609-000081 printed no customer name, no
    service address and no mailing address: `documents._meta` reads those keys
    from the frozen payload, and the one-time kinds build their bill with an
    EMPTY gather snapshot (`fee_bill._fee_usage` · `snapshot={}`), so nothing
    ever stamped them. A cycle bill carried two of the three from gather and
    the mailing address on NONE. Stage 6 is the one path every bill kind
    shares, so this is where the answer is frozen for all of them.

    **NOTHING IS INVENTED.** A key the answer does not hold is stamped `None`
    and the document names the absence with its rule — never a partial string
    that reads as complete, never the word None.
    """
    for key in ADDRESSEE_FILL_KEYS:
        current = payload.get(key)
        if not (isinstance(current, str) and current.strip()):
            payload[key] = addressee.get(key) or None
    for key in ADDRESSEE_STAMP_KEYS:
        payload[key] = addressee.get(key) or None
    # `DEF-BIL-9787` — the account's PO (*"PO or reference on bills"*, recorded
    # at move-in on `accounts.po_number`), frozen here with the name so a PO
    # changed later never reprints an issued bill (BR-BIL-030, hard rule 4).
    # Stamped ONLY when the account names one: most accounts have none, and an
    # absent PO is not a gap to name — the document simply prints no PO line,
    # and every other bill's payload stays byte-identical.
    po_number = addressee.get("po_number")
    if isinstance(po_number, str) and po_number.strip():
        payload["po_number"] = po_number.strip()
    for key in MASTHEAD_STAMP_KEYS:
        value = masthead.get(key)
        payload[key] = value.strip() or None if isinstance(value, str) else None
    # CR-172-BRC10 — WHICH logo: the stored PNG's id, or None (BR-TEN-017,
    # BR-BIL-030 "branding reference"). Stamped at draft so the draft's preview
    # shows it; `issue._stamp_bill_header` stamps it again at issue.
    logo = masthead.get("utility_logo")
    payload["utility_logo"] = dict(logo) if isinstance(logo, dict) and logo.get("document_id") else None


def assemble_document(
    *,
    usage: MeasuredUsage,
    priced: Any,
    tenant_id: Any,
    account_id: Any,
    bill_run: models.BillRun | None,
    period_start: date,
    period_end: date,
    service_date: date,
    bill_type: str = "cycle",
    line_windows: Any = None,
) -> models.Invoice | None:
    """Priced lines -> a DRAFT `invoices` row and its `invoice_lines`, or `None`.

    `priced` is a `rating_seam.RatedBill` — read structurally, not imported as
    a type, for the same reason rating reads billing's inputs structurally: the
    two modules must not depend on each other's classes.

    ── `BR-BIL-1024` — NO LINES, NO DOCUMENT, AND THIS IS WHERE IT IS DECIDED ──
    PO ruling 2026-08-31 (`CR-056` ruling 1), verbatim: *"Decided at the END of
    the run, after pricing, never at the start — because only then do you know
    whether there was anything to charge. A `$0.00` bill is not the harmless
    option: a customer who receives one telephones to ask what it means, and
    several hundred a month is real postage and a real support load for a
    document that says nothing."*

    **This function IS the end of the run for one account** — the last stage, and
    the only one that writes the row — so it is where the ruling lands. An
    account that priced no lines gets `None` and no `invoices` row is created.

    ⚠ **NO LINES IS NOT NO MONEY, AND THE DIFFERENCE IS THE WHOLE RULE.** The
    test is `len(lines) == 0`, never `total == 0`. A bill carrying a `$0.00` line
    IS a document and is issued: `OQ-670` (PO 2026-08-27, *"(b) Bill $0.00"*)
    put that line on the document deliberately, over the lane's own
    recommendation to refuse, and a suppression keyed on the TOTAL would delete
    the very bill that ruling exists to produce — silently, for 48 trash
    accounts.

    ⚠ **THE RE-RUN STILL CLEARS ITS OWN DRAFT FIRST.** `BR-BIL-023`'s deletion
    happens BEFORE the emptiness is judged, so an account that had lines last
    pass and has none this pass ends with no document rather than with a stale
    one. Only DRAFTS are ever deleted; an issued bill is refused by the database
    itself (hard rule 4).

    **Nothing that has ever been billed reaches the new branch.** Every account
    this product bills produces at least one line, so no ❄️ B4/B5 figure and no
    golden case can hit it — `1408 Elm Street` still bills `$41.20 + $28.40 =
    $69.60`.
    """
    if priced is None:
        raise BillingRuleError(
            f"account {usage.subscription.account_no}: nothing was priced, so "
            "there is no bill to assemble. An account that could not be priced "
            "belongs in the run's exception list, not in a draft."
        )

    currency = getattr(priced, "currency", None) or usage.subscription.currency
    if currency != usage.subscription.currency:
        # A bill in one currency for an account in another is not a rounding
        # question — it is two different amounts of money. CLAUDE.md rule 2.
        raise BillingRuleError(
            f"account {usage.subscription.account_no}: priced in {currency!r} "
            f"but the account's currency is {usage.subscription.currency!r}. "
            "Money never changes currency between stages (CLAUDE.md rule 2)."
        )

    # BR-BIL-023 — a draft is discardable free, so a re-run REPLACES rather
    # than accumulating. Only drafts: an issued bill is refused by the database
    # itself, which is the guarantee this relies on rather than re-checks.
    existing = models.Invoice.objects.filter(
        tenant_id=tenant_id,
        account_id=account_id,
        bill_run=bill_run,
        status=models.INVOICE_DRAFT,
    )
    models.InvoiceLine.objects.filter(invoice__in=existing).delete()
    existing.delete()

    # ── `BR-BIL-1024` · NO LINES, NO DOCUMENT ───────────────────────────────
    # Judged AFTER the draft above is cleared and BEFORE anything is created:
    # a re-run that now prices nothing must leave no document at all, not the
    # one it wrote last pass. `getattr` and not `priced.lines` for the reason
    # every other read of `priced` in this function uses one — the result is
    # read structurally, never as an imported type.
    if not tuple(getattr(priced, "lines", ()) or ()):
        return None

    # ── THE PLATFORM SERVICE CATALOGUE, READ ONCE FOR THIS BILL ─────────────
    # `service_ids` fills `invoice_lines.service_id` below, exactly as it always
    # has. `service_names` is `DEF-2852`: the WORD each id stands for, frozen
    # into the payload beside the code so the document can head a charge block
    # *Water* rather than the id. One read, hoisted above the create so the
    # payload and the lines are stamped from the SAME answer — two reads could
    # disagree, and the whole point of the id is that it matches the lines.
    service_ids = tenancy_seam.service_ids_by_code()
    service_names = tenancy_seam.service_names_by_code()
    service_catalog = {
        code: (service_id, service_names.get(code)) for code, service_id in service_ids.items()
    }

    invoice = models.Invoice.objects.create(
        tenant_id=tenant_id,
        account_id=account_id,
        bill_run=bill_run,
        # BR-BIL-063 (PO ruling 2026-08-11): the number is allocated HERE, when
        # the draft is created — *"Give a running number always even for Draft;
        # if not use thats okay we will lose it; its okay; dont over complicate,
        # keep it simple."* An earlier cut left this NULL and cited BR-BIL-022,
        # which says only where a number comes from and what it looks like; the
        # "at issue only" timing was never in a numbered rule.
        #
        # The cost was put to the PO and accepted: a re-run REPLACES its draft
        # (BR-BIL-023), so each re-run allocates fresh numbers and the old ones
        # are gone — three re-runs of a 500-account run spend 1,500 numbers on
        # 500 bills. The series is documented as gap-tolerant (BR-TEN-035: "gaps
        # from rolled-back transactions are fine; a number is never reused").
        #
        # `service_date` and not today: BR-TEN-043, the caller names the
        # business event's date, and the format's {YYMM} tokens render from it.
        # A June bill drafted in July numbers as June's — which is also what
        # makes a re-run reproducible.
        invoice_no=core_numbering.next_number(core_numbering.BILL, service_date),
        bill_type=bill_type,
        service_date=service_date,
        period_start=period_start,
        period_end=period_end,
        # BR-BIL-024: the due date is derived AT ISSUE from the bill date and
        # the cycle's due-days. A draft has no due date because it has no issue
        # date, and inventing one here would put a date on a document that may
        # never exist.
        due_date=None,
        status=models.INVOICE_DRAFT,
        subtotal=_decimal(getattr(priced, "taxable_subtotal", 0)),
        tax_total=_decimal(getattr(priced, "tax_total", 0)),
        total=_decimal(getattr(priced, "total", 0)),
        currency=currency,
        bill_payload=_snapshot_payload(
            usage,
            priced,
            service_date,
            service_catalog=service_catalog,
            # DEF-BIL-8283 — read through the owning modules' seams (B1): the
            # customer and both addresses from customers (the service address
            # WALKED to the premises, hard rule 8), the utility from tenancy.
            addressee=customers_seam.bill_addressee(account_id),
            masthead={
                **tenancy_seam.bill_masthead(),
                "utility_logo": tenancy_seam.bill_logo(),  # CR-172-BRC10
            },
        ),
        # US-BIL-028 / B2 r17.3 — the tenant's OWN fields, frozen here with the
        # rest of the payload for the same reason and at the same moment. Read
        # only through `apps/billing/custom_snapshot.py`, the single module
        # DB-17 allows to touch tenant-defined data in a money path; it returns
        # `dict[str, str]`, so nothing downstream can compute with it
        # (BR-TEN-048). Nothing READS this until R3 (US-NOT-016) and it is
        # stamped anyway: B12 r7.2 — *"Stamp early, render later"* — because an
        # invoice issued without it can never render a custom field except by a
        # live join, which rewrites an issued document without an UPDATE.
        custom_snapshot=custom_snapshot_module.stamp_for_account(account_id),
    )

    lines = []
    # `DEF-BIL-8561` (2026-09-30) — a catch-up or penalty says which MONTH each
    # line bills (`backbill.PricedBackBill.line_windows`, aligned with
    # `priced.lines`); every other caller passes nothing and every line keeps
    # the bill's own window, byte for byte as before. A None entry (a fee, a
    # discount, a tax) bills the whole window.
    windows = tuple(line_windows or ())
    for position, line in enumerate(getattr(priced, "lines", ())):
        kind = getattr(line, "kind", None)
        window = windows[position] if position < len(windows) else None
        if kind not in LINE_KINDS:
            raise BillingRuleError(
                f"account {usage.subscription.account_no}: priced line of "
                f"unknown kind {kind!r}. Billing stores rating's kinds verbatim "
                f"({LINE_KINDS}); an unknown one means the seam changed and the "
                "bill would misreport what it charged."
            )
        quantity = getattr(line, "quantity", None)
        unit = getattr(line, "unit", None)
        if quantity is not None and not unit:
            # CLAUDE.md rule 3. A quantity on a bill line with no unit is a
            # number the customer cannot check.
            raise BillingRuleError(
                f"account {usage.subscription.account_no}: a {kind} line carries "
                "a quantity with no unit (CLAUDE.md rule 3)."
            )
        lines.append(
            models.InvoiceLine(
                tenant_id=tenant_id,
                invoice=invoice,
                account_id=account_id,
                kind=kind,
                description=getattr(line, "description", ""),
                quantity=quantity,
                unit=unit,
                unit_price=getattr(line, "unit_price", None),
                amount=_decimal(getattr(line, "amount", 0)),
                taxable=bool(getattr(line, "taxable", False)),
                period_start=window[0] if window else period_start,
                period_end=window[1] if window else period_end,
                # WHAT PRODUCED THE LINE — see `_service_id_for` and the
                # module docstring's "IDENTITY" section. Written HERE, at draft
                # time, and not at issue: these are facts about what was priced,
                # and issue only RESOLVES them into a GL account.
                service_id=_service_id_for(line, kind, service_ids, usage),
                tax_id=getattr(line, "tax_id", None),
                # WHICH TARIFF VERSION PRICED THIS LINE — DEF-276, fixed
                # 2026-08-19. It comes from the engine's own priced line, which
                # carried it down from the `TariffConfig` the run resolved by
                # BR-RAT-007; it is NOT looked up here from the tariff and the
                # service date. A second lookup would agree with the engine
                # almost always and disagree exactly when it matters, and a
                # provenance column that can disagree with the price it
                # describes is not provenance at all.
                #
                # None on tax and fee lines by construction: a tax names its
                # authority (`tax_id`, BR-BIL-069) and a fee names its charge
                # code, and neither was priced from a rate schedule.
                tariff_version_id=getattr(line, "tariff_version_id", None),
                # ⚠ **WHICH CHARGE CODE A FEE LINE CAME FROM** — DEF-714,
                # 2026-08-25, and this column had NO WRITER ANYWHERE until
                # then. `invoice_lines.charge_id` existed from the first
                # migration, BR-BIL-010 keys a fee's GL account on it, and
                # issue refused every fee line for want of it — so a tenant
                # that configured any recurring or auto-apply charge code
                # (BR-RAT-117, PO 2026-08-22 *"ruccuring and Autom apply land
                # on bill"*) could issue NO bill at all. The draft assembled
                # perfectly and died at issue.
                #
                # Written HERE with `service_id` and `tax_id` for the reason
                # the comment above gives: these are facts about what was
                # PRICED, and issue only RESOLVES them into a GL account.
                # None on every non-fee line and on a fee that named no code —
                # never inferred from the description (option D of OQ-116,
                # declined by the PO).
                charge_id=getattr(line, "charge_id", None),
                # 2026-09-30 (DB1) — the meter or asset this line was priced
                # for, stamped by the engine from `TariffConfig.asset_id`.
                # NULL on every line whose service carries one meter.
                asset_id=getattr(line, "asset_id", None) or None,
                # 🔒 DEF-2430 / DEF-BIL-5341 — which PROGRAMME a discount line
                # was granted under, as the engine stamped it. Issue hands it
                # to rating so the grant is recorded against the enrolment and
                # a yearly cap or budget counts down. NULL on every other line.
                discount_code=getattr(line, "discount_code", None) or None,
                # BR-BIL-010: the GL account is stamped AT ISSUE from the
                # mapping, and frozen. Not here — a draft that carried a GL
                # stamp would have recorded a mapping that may change before
                # the bill is ever issued.
                gl_account_id=None,
                pricing_trace=_line_trace(line, kind, usage.subscription),
            )
        )
    models.InvoiceLine.objects.bulk_create(lines)

    # ── BUDGET BILLING (US-BIL-019; PO ruling 2026-08-11 "Level is due") ─────
    # The bill above is FULL ACTUALS and stays that way — every line, every GL
    # stamp, the tax, and `invoice.total`. BR-BIL-011 recognises revenue and tax
    # on the actuals every month and the level is a COLLECTION SCHEDULE, never a
    # price, so nothing here touches a line or a total.
    #
    # What it adds is a SECOND fact about the same bill: the three columns WE-8
    # requires on every budget bill (actual · level · variance movement), the
    # running balance, and — the ruling — the amount the customer actually owes.
    #
    # ASKED, NOT PASSED IN. `record_bill` returns None for an account that is
    # not enrolled, so there is no optional argument for a caller to forget:
    # hard-won law 2 says a prop nothing passes is dead code, and a budget block
    # that only appears when someone remembers to ask for it is exactly that.
    # It runs inside stage 6's write, which is where the payload is frozen.
    facts = budget_service.record_bill(
        account_id=account_id,
        actual=invoice.total,
        on_date=service_date,
        invoice=invoice,
        bill_type=bill_type,
    )
    if facts is not None:
        payload = dict(invoice.bill_payload or {})
        payload["budget"] = facts.as_payload()
        invoice.bill_payload = payload
        invoice.save(update_fields=["bill_payload", "updated_at"])
    return invoice


#: The line kinds a service's pricing chain is written onto (2026-10-01).
TRACED_KINDS = ("usage", "base", "minimum_adjustment")


def _line_trace(line: Any, kind: str, subscription: Any) -> dict | None:
    """The chain this line was priced from, as VALUES — or None.

    PO ruling 2026-10-01, verbatim: *"i want tracbility -> billing -> account
    -> unit -> plan -> rate schedule -> base charge -> size and amount"*. The
    service half (base code, rate schedule version, customer type, sizes with
    count / base each / base total / price each) was collected at gather
    (`AccountBillingData.pricing_trace`); the account, unit and plan half is
    the subscription's, read HERE so a plan version the ruled path restated is
    the one recorded. Worked: 2 × CART-96, BASE-T $3.00, cart $15.00 → the
    $36.00 trash line carries `sizes: [{size: CART-96, count: 2, base_each:
    3.0000, base_total: 6.0000, price_each: 15.0000}]`.

    None on a tax or fee line and on a line whose service gathered no trace
    (a fixture-built subscription), so nothing written before this changes.
    """
    if kind not in TRACED_KINDS:
        return None
    service = getattr(line, "service", None)
    traces = getattr(subscription, "pricing_trace", None) or {}
    entry = traces.get(service) if service else None
    if not entry:
        return None
    snapshot = getattr(subscription, "snapshot", None) or {}
    plan_id = getattr(subscription, "rate_plan_id", None)
    period = getattr(subscription, "period", None)
    version_id = entry.get("rate_schedule_version_id") or getattr(line, "tariff_version_id", None)
    return {
        "account_no": getattr(subscription, "account_no", None),
        "unit_id": snapshot.get("unit_id"),
        "unit_label": snapshot.get("unit_label"),
        "plan_id": str(plan_id) if plan_id else None,
        "plan_name": getattr(subscription, "rate_plan_name", None),
        "plan_version": getattr(subscription, "rate_plan_version", None),
        "rate_schedule_version_id": str(version_id) if version_id else None,
        "customer_type": entry.get("customer_type"),
        "base_code": entry.get("base_code"),
        "base_by_size": bool(entry.get("base_by_size")),
        "service_days": getattr(period, "service_days", None),
        "cycle_days": getattr(period, "cycle_days", None),
        "sizes": [dict(row) for row in entry.get("sizes") or ()],
    }


def _service_id_for(line: Any, kind: str, service_ids: dict[str, str], usage: MeasuredUsage) -> Any:
    """The catalog id of the service this line charged for, or None.

    THE CODE COMES FROM THE PRICED LINE AND FROM NOWHERE ELSE. Rating stamps it
    on every usage and base line it emits (`pricing/stages/price_usage.py`), so
    the answer is the engine's own statement of what it was pricing. It is NOT
    inferred from the description and NOT inferred from the unit: water and
    sewer are both metered in kgal, so a unit-based guess would post one
    service's revenue to the other's account — silently, permanently, since the
    stamp freezes with the bill.

    A tax or fee line names no service and gets None: tax is a BILL-level charge
    (PO ruling 2026-08-11 — *"Tax rates are for bill not for service"*) and a
    fee is a fact about the ACCOUNT. Neither absence is a gap.

    TWO REFUSALS, both about a usage or base line, because such a line WILL be
    refused at issue by BR-BIL-010 and a draft that cannot ever become a bill is
    worse than no draft — it burns an invoice number and hides the real cause
    behind a message about GL mapping:

      * the line names no service at all — the engine did not stamp one, which
        means the seam and the engine disagree about this contract;
      * the code is not in the tenant's platform catalog — a service the
        platform has retired, or a typo in a tariff.
    """
    code = getattr(line, "service", None)
    if kind == "minimum_adjustment":
        # ── DEF-BIL-8150 (PO 2026-09-30, "SIX ANSWERS" (4)) ──────────────────
        # A PER-SERVICE minimum top-up (BR-RAT-028 mode A) names its service,
        # and — with two meters on the service — its meter (`asset_id`, below),
        # so the bill prints meter B at `$6.00 + $4.00 = $10.00` instead of
        # `$6.00` beside a `$4.00` that belongs to no meter. The plan floor
        # (mode B) names no service and stays NULL. NEVER A REFUSAL: this
        # line's GL account is the `minimum_bill_adjustment` DESIGNATION
        # (`issue._gl_account_for`), not the service's revenue map, so a
        # missing stamp costs attribution and never the bill. ⚠ The Summary's
        # per-service buckets (`selectors`) still read `usage`/`base` only, so
        # this moves no figure under any heading on screen.
        return service_ids.get(code) if code else None
    if kind not in SERVICE_BEARING_KINDS:
        return None
    if not code:
        raise BillingRuleError(
            f"account {usage.subscription.account_no}: a {kind} line "
            f"({getattr(line, 'description', '')!r}) does not say which service it charged "
            "for. BR-BIL-010 resolves that line's revenue account FROM THE SERVICE, so a "
            "bill written this way could never be issued, and per-service revenue could "
            "never be reported from it. The service travels on the priced line "
            "(rating_seam.RatedLine.service); nothing here guesses one from the wording "
            "or the unit — water and sewer are both metered in kgal."
        )
    service_id = service_ids.get(code)
    if service_id is None:
        raise BillingRuleError(
            f"account {usage.subscription.account_no}: a {kind} line was priced for service "
            f"{code!r}, which is not in the active platform catalog (BR-TEN-025). The line "
            "cannot name a service that does not exist, so it could never resolve a revenue "
            "account — reported here, where the account is still un-billed, rather than at "
            "issue where the draft has already spent a number."
        )
    return service_id


def _decimal(value: Any) -> Decimal:
    """Money as Decimal, never float (CLAUDE.md rule 2, and G6 greps for it)."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-029@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane) · AMENDED 2026-08-11 by
#         Eng-Lead (OQ-116 tax-authority GL lane: the lines now carry WHAT
#         PRODUCED THEM — `service_id` on usage/base, `tax_id` on tax)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — a stage) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · tests/test_us_bil_029_assemble.py ·
#         tests/test_br_bil_069_tax_authority_gl.py (the end-to-end case: a
#         bill with usage + base + THREE tax lines issues with every line
#         stamped, each tax line to its own authority's 2200 account)
# exceptions: CORRECTED 2026-08-11 — this list previously ended at "no GL
#         stamp" and said nothing about `service`, which this stage did not
#         write. That silence was the defect: the column existed, the FK
#         existed, nothing filled it, and every real bill refused at issue for
#         a reason no reader of this file could see (hard-won law 2). It is
#         written now, from the priced line's own `service` and never inferred
#         from a description or a unit · a usage/base line that names no
#         service, or names one outside the active catalog, REFUSES here rather
#         than becoming a draft that can never be issued — a break the run
#         reports per account, not an exception that stops the pass ·
#         ⚠ CORRECTED 2026-08-25 (lane FEELINE, DEF-714/DEF-201). This clause
#         read *"`charge_id` on FEE lines is still NULL and is still a real
#         gap"*, and it was a bigger gap than it sounds: BR-RAT-117 (PO
#         2026-08-22) put a fee line on the ORDINARY bill of every tenant with a
#         recurring or auto-apply charge code, so from that day those tenants
#         could issue NO bill at all. **It is written now**, from the priced
#         line's own `charge_id`, which travels on `rating_seam.RatedLine` and
#         through every pricing stage; `issue._gl_account_for` resolves the
#         code's own account (`rating.charges.gl_account_id`) and re-checks it
#         is live. THE REMAINING HALF IS STILL TRUE AND IS NOW ITS OWN ROW: a
#         late fee built in `decisions.py` from a `BillRunDecision` carries no
#         charge reference, so it still arrives None and is still REFUSED by
#         name — DEF-719, and nothing here substitutes a revenue account for a
#         fee · writes a DRAFT and nothing else BEYOND
#         ITS NUMBER AND THE LINE IDENTITIES — no due date
#         (BR-BIL-024, derived at issue), no GL stamp (BR-BIL-010, stamped at
#         issue and frozen). Each of those would be a fact recorded about a
#         document that may never exist. CORRECTED 2026-08-11: this line said
#         "no invoice number (BR-BIL-022, minted at issue)" and the code beneath
#         it has allocated the number since BR-BIL-063 (PO ruling 2026-08-11 —
#         *"give a running number always even for Draft; if not use thats okay we
#         will lose it"*). The stale claim was the one thing a reader would have
#         trusted without checking · the
#         SNAPSHOT is assembled HERE rather than at issue, deliberately: at
#         issue it would re-join whatever the customer record says by then, and
#         a name changed between the run and the release would print on a bill
#         for a period billed under the old one · re-running REPLACES an
#         existing draft for the same (run, account) — legitimate only because
#         BR-BIL-023 makes a draft discardable free; the database itself
#         refuses the same treatment of an issued bill · `priced` is read
#         STRUCTURALLY (getattr) rather than by importing rating's type, the
#         same posture rating takes toward billing's inputs
#         · AMENDED 2026-08-11 (budget-billing lane): the budget block is
#         ASKED FOR here rather than passed in as an optional argument.
#         `budget_service.record_bill` returns None for an account that is
#         not enrolled, so there is no prop a caller can forget to pass —
#         hard-won law 2 and gate G13 are about exactly that shape. The
#         bill itself is untouched: full actuals, every line, every GL
#         stamp, `invoice.total` unchanged, because BR-BIL-011 recognises
#         revenue and tax on the ACTUALS and the level is a collection
#         schedule, never a price
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

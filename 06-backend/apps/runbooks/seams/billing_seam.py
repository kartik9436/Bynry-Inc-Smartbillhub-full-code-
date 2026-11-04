# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-039 (read through a seam this module owns, by name, in
#           process, under the tenant context) · CLAUDE.md hard rule 1 ·
#           hard rule 4 (issued invoices are append-only)
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 (this seam's row in the cross-module interface
#           register, added in the same commit as this file)
# ───────────────────────────────────────────────────────
"""operations → billing — bills, bill runs, break lists. READ ONLY.

The pre-bill sweep, the break-list variant of the account check and every
*Can we bill?* verdict read here.

⚠ **THE BILL RUN ITSELF IS BILLING'S, NOT THIS MODULE'S.** A runbook says what
would stop a bill run and, at most, hands billing a scope; it never issues an
invoice and **consumes no bill number**. That is why phase 2's rollback is
clean: 25 coverage cells produce correct arithmetic and no bill number is spent
(`CR-075` §2). It is also hard rule 4 read forward — an issued invoice is
append-only, so a module that could re-run one would be writing a correction
nobody asked for.

⚠ **ONE PORT IS BILLING'S** — `apply_fee`, and it sits **behind the second
approval** because it is money-bearing (`BR-RBS-018`). It is a declaration with
no writer bound until phase 4's dry half.

⚠ **THIS FILE DECLARES THE PAIR AND HOLDS NO CALLABLE YET, ON PURPOSE.** Wave A
builds the module and its boundary; wave C brings the first Check and the reads
it actually needs. A selector written here now would be a function nothing calls
(hard-won law 2), and naming one in prose that `billing` does not expose would
fail `G20` — the guard that caught `DEF-075`. What this module will need and
`billing` does not offer today is inventoried in
`17-runbooks/13-selector-inventory.md`, and **`billing` adds each of them** —
never this file reaching past the seam.
"""

from apps.runbooks.boundary import SeamDeclaration

SEAM = SeamDeclaration(
    module="billing",
    pair="operations → billing",
    crosses="bills, bill runs, break lists",
)


# ── CR-075 wave C · the reads runbook 1 makes (US-RBS-001) ────────────────


def has_published_bill_template() -> bool:
    """Does this tenant hold a PUBLISHED bill layout to print a bill on?

    Read through `billing`'s own `templates_service` — the same door `tenancy`'s
    provisioning seam uses to seed one — because `bill_templates` is billing's
    table and its readers live there rather than in `selectors`.

    ⚠ **A TEMPLATE THAT EXISTS AND IS NOT PUBLISHED PRINTS NOTHING**, so the
    fallback template alone is not the answer; the published version is. The two
    reads are one question and are made together for that reason.
    """
    from apps.billing import templates_service

    template = templates_service.tenant_fallback_template()
    if template is None:
        return False
    return templates_service.published_version(template) is not None


# ── CR-075 wave F · the reads runbook 23 makes (US-RBS-004) ───────────────
#
# ⚠ **WHY THE TEST BILL'S PRICING CALL IS FILED UNDER *billing* AND NOT UNDER
# *rating*, WHICH IS WHAT THE EXECUTION PLAN'S `F2` ASKS FOR.**
# `10-execution-plan.md` `F2` reads *"step 2 calls the rating engine's own path.
# A seam to rating, in the register"*, and it was written before this module's
# code existed. In the code, the chain from an ACCOUNT to a PRICED LINE is
# billing's and nothing else's: `billing.runs.price_account` resolves the
# subscription, measures consumption, applies four typed refusals and only then
# calls `billing.rating_seam.price_bill`, which is the door into
# `apps.rating.engine`. Filing that call in `rating_seam.py` — a file whose
# `SeamDeclaration` says `operations → rating` — would be a sentence about the
# boundary that is not true of the code behind it, which is hard-won law 1
# exactly. So **the pricing call is HERE**, the rating seam carries the tariff
# reads that EXPLAIN a line (step 3), and the divergence is written down rather
# than smoothed over. Both seams are already rows in the register (B2 Addendum
# r25), so nothing about *"in the register"* changes.


def price_account_as_the_run_would(
    *,
    account_id,
    period_start,
    period_end,
    service_date=None,
):
    """Price ONE account exactly as a bill run does, and **write nothing**.

    Runbook 23's steps 1 and 2 in one call, because they are one call in the
    product: `billing.single.prepare_single_bill` is phase 1 — *"Writes nothing
    — the same promise `prepare_run` makes"* — and `billing.runs.price_account`
    is stages 1 → 5, the pure half of `calculate_account`.

    ⚠ **THIS IS THE RUN'S OWN CODE AND NOT A COPY OF IT, WHICH IS THE WHOLE OF
    `US-RBS-004`.** `calculate_account` is now literally `price_account(data)`
    followed by stage 6, so the test bill and the bill run **cannot** compute
    different lines: there is one implementation and the only difference is
    whether stage 6 runs. `TC-RBS-004.3` asserts the identity to **four
    decimals** anyway — a check that can now only fail if somebody reintroduces
    a second path, which is exactly what it is there for.

    ⚠ **NO BILL NUMBER IS CONSUMED.** Stage 6 is where a draft is written and
    where `core.numbering` spends a number (`BR-BIL-063`), and it is not called.
    Nothing on this path writes `invoices`, `invoice_lines`, `bill_runs` or a
    journal line.

    Returns `{"priced": …, "refusal": …}` with exactly one of the two set.
    `refusal` carries the engine's OWN reason code and the service the engine
    itself named; the clerk's sentence is composed by the runbook, because the
    engine's messages quote rule ids and B14 rule 32 keeps a rule id off a
    screen.
    """
    from apps.billing import runs as billing_runs
    from apps.billing import single as billing_single
    from apps.billing.exceptions import BillingRuleError
    from apps.billing.gather import GatherProblem

    on = service_date or period_end
    try:
        prepared = billing_single.prepare_single_bill(
            account_id=account_id,
            period_start=period_start,
            period_end=period_end,
            service_date=on,
        )
    except (GatherProblem, BillingRuleError) as problem:
        return {"priced": None, "refusal": _refusal(problem)}

    # Phase 1 answers in FOUR lists and each means a different thing. `blocked`
    # and `decisions` are the run's own words for *this account cannot be priced
    # yet* and *a human must choose*; `silent` is `BR-BIL-1025` — an account with
    # genuinely nothing to bill, which is a correct state and not a fault, and
    # the runbook says so in different words for that reason.
    if not prepared.ready:
        problem = (list(prepared.blocked) + list(prepared.decisions) + list(prepared.silent) + [None])[0]
        return {
            "priced": None,
            "refusal": {
                "reason": getattr(problem, "reason", "account_not_ready"),
                "service_code": getattr(problem, "service_code", None),
                "detail": getattr(problem, "detail", ""),
                "silent": bool(prepared.silent) and not prepared.blocked and not prepared.decisions,
            },
        }

    data = prepared.ready[0]
    try:
        priced_account = billing_runs.price_account(data)
    except (GatherProblem, BillingRuleError) as problem:
        return {"priced": None, "refusal": _refusal(problem)}

    return {
        "priced": {
            "account_no": data.account_no,
            "currency": priced_account.priced.currency,
            "total": priced_account.priced.total,
            "taxable_subtotal": priced_account.priced.taxable_subtotal,
            "tax_total": priced_account.priced.tax_total,
            "fee_total": priced_account.priced.fee_total,
            "split": priced_account.split,
            "period_start": data.period_start,
            "period_end": data.period_end,
            "service_date": on,
            # ⚠ **WHICH SERVICES WERE PRICED FROM AN ESTIMATE — THE GATHER'S OWN
            # FACT, CARRIED, NEVER RE-DERIVED** (`CR-075` wave G, `US-RBS-005`).
            # `ServiceReading.estimated` is set by `BR-MET-029` upstream and its
            # own comment says why it travels: *"It changes what the bill says, so
            # it travels with it."* The coverage grid's middle outcome —
            # **estimated** — is this list being non-empty, and a version of that
            # runbook which asked metering a second question would be answering
            # *was there an estimate* differently from the bill that used one.
            #
            # ⚠ **A BILL WITH AN ESTIMATE IS NOT A REFUSAL AND NOT A FAULT.** It
            # priced, completely, and the grid draws it amber rather than red
            # because the number is real and the read behind it is a judgment. A
            # runbook that folded this into `refused` would tell a utility its
            # estate does not bill when it does.
            "estimated_services": sorted(
                {
                    reading.service_code
                    for reading in data.readings
                    if reading.estimated and reading.service_code
                }
            ),
            # ⚠ **PLAIN DATA, NEVER `RatedLine` OBJECTS.** A seam hands a runbook
            # facts rather than another module's dataclass — the same reason
            # `rating_seam.plan_coverage` resolves the `Tariff` row here instead
            # of passing it out. `amount` and `unit_price` stay `Decimal`:
            # rounding is a DISPLAY act (hard rule 2) and this is not display.
            "lines": [
                {
                    "kind": line.kind,
                    "description": line.description,
                    "amount": line.amount,
                    "taxable": line.taxable,
                    "quantity": line.quantity,
                    "unit": line.unit,
                    "unit_price": line.unit_price,
                    "service": line.service,
                    "tax_id": line.tax_id,
                    "tariff_version_id": line.tariff_version_id,
                    "charge_id": line.charge_id,
                }
                for line in priced_account.priced.lines
            ],
        },
        "refusal": None,
    }


def _refusal(problem) -> dict[str, object]:
    """The engine's own verdict, reduced to the two facts a sentence needs.

    `reason` is one of billing's `GATHER_*` / `CALC_*` codes and `service_code`
    is the service the engine itself named — neither is inferred here. `detail`
    is the engine's full sentence and is carried so a reader of the run can see
    it; **it never reaches a screen**, because those sentences quote rule ids
    (`BR-BIL-015`, `BR-RAT-090`) and B14 rule 32 keeps a rule id out of
    clerk-facing copy.
    """
    return {
        "reason": getattr(problem, "reason", "pricing_refused"),
        "service_code": getattr(problem, "service_code", None),
        "detail": str(problem),
        "silent": False,
    }


def last_issued_bill(account_id, *, before=None) -> dict[str, object] | None:
    """The account's most recent ISSUED bill and its lines — runbook 23 step 4.

    `None` when the account has never been issued one, which is an ordinary
    state for a new connection and is drawn as a stated absence rather than as a
    fault.

    ⚠ **ISSUED, NEVER A DRAFT.** A draft is freely replaced and discarded
    (`BR-BIL-004`), so comparing against one would compare this run against an
    earlier run of something like it. What a clerk means by *the last bill* is
    the document the customer received.

    ⚠ **`invoice_lines` HAS NO SEQUENCE COLUMN**, so the order is `created_at`
    then `id` — the order `bulk_create` wrote them in, which is the order the
    engine emitted them. Stated because a reader will look for a `seq` and there
    is none to find.
    """
    from apps.billing import models as billing_models

    bills = billing_models.Invoice.objects.filter(account_id=account_id).exclude(
        status=billing_models.INVOICE_DRAFT
    )
    if before is not None:
        bills = bills.filter(period_end__lt=before)
    invoice = bills.order_by("-period_end", "-issued_at", "-id").first()
    if invoice is None:
        return None
    lines = billing_models.InvoiceLine.objects.filter(invoice_id=invoice.pk).order_by(
        "created_at", "id"
    )
    return {
        "period_start": invoice.period_start,
        "period_end": invoice.period_end,
        "currency": invoice.currency,
        "total": invoice.total,
        "lines": [
            {
                "kind": line.kind,
                "description": line.description,
                "amount": line.amount,
            }
            for line in lines
        ],
    }


# ── CR-075 wave S · the reads runbooks 4, 6 and 16 make ───────────────────
#
# ⚠ **THESE READ `billing`'s MODELS RATHER THAN A SELECTOR, AND THE PRECEDENT IS
# `last_issued_bill` DIRECTLY ABOVE.** `billing.selectors.invoice_detail` builds
# a SCREEN payload — labels, summaries, deliveries, integrity blocks — and a
# runbook comparing two bills needs the LINES with their quantities and their
# tariff versions, which that payload flattens for display. Reading the two
# tables here keeps the comparison on the stored figures rather than on a
# rendered copy of them, and `G115` permits a foreign import in a seam file
# precisely so the seam can be the one place it happens.


def issued_bills_for_account(account_id, *, limit: int = 14) -> list[dict[str, object]]:
    """The account's ISSUED bills, newest first, **with every line**.

    `RB-104` compares two of them line by line; `RB-106` asks when the account
    last billed. One read answers both.

    ⚠ **ISSUED, NEVER A DRAFT** — a draft is freely replaced and discarded
    (`BR-BIL-004`), so a comparison against one compares this run against an
    earlier run of something like it. What a customer means by *my last bill* is
    the document they received.

    ⚠ **`tariff_version_id` TRAVELS AND IT IS THE ONLY HONEST ANSWER TO *did the
    rate change*.** `invoice_lines.tariff_version_id` is stamped AT ISSUE and
    frozen (`BR-BIL-010`'s posture), so two bills carrying different versions
    for one service is a rate change that actually reached the customer —
    whereas comparing today's in-force version against both would report a
    change on every bill raised before the last edit.

    ⚠ **NO ROUNDING HAPPENS HERE.** Money crosses as its stored four-decimal
    string and the renderer displays two (hard rule 2). A `Decimal` would cross
    a seam as another module's type; a float would breach the rule outright.

    ⚠ **`invoice_lines` HAS NO SEQUENCE COLUMN**, so lines come back in
    `created_at, id` order — the order `bulk_create` wrote them, which is the
    order the engine emitted them. Stated because a reader will look for a `seq`
    and there is none to find.
    """
    from apps.billing import models as billing_models

    invoices = list(
        billing_models.Invoice.objects.filter(account_id=account_id)
        .exclude(status=billing_models.INVOICE_DRAFT)
        .order_by("-period_end", "-issued_at", "-id")[: max(int(limit), 1)]
    )
    if not invoices:
        return []
    lines = billing_models.InvoiceLine.objects.filter(
        invoice_id__in=[one.pk for one in invoices]
    ).select_related("service").order_by("created_at", "id")
    by_invoice: dict[str, list[dict[str, object]]] = {}
    for line in lines:
        by_invoice.setdefault(str(line.invoice_id), []).append(
            {
                "kind": line.kind,
                "description": line.description,
                "amount": str(line.amount),
                "quantity": None if line.quantity is None else str(line.quantity),
                "unit": line.unit,
                "unit_price": None if line.unit_price is None else str(line.unit_price),
                "service": line.service.code if line.service_id else None,
                "taxable": bool(line.taxable),
                "tariff_version_id": (
                    str(line.tariff_version_id) if line.tariff_version_id else None
                ),
            }
        )
    return [
        {
            # ⚠ THE NUMBER A CUSTOMER READS OFF THEIR BILL, NEVER THE ROW'S ID
            # (B14 rule 31). `bill_id` is a handle the setup screen needs to
            # name WHICH bill was picked; nothing draws it.
            "bill_id": str(one.pk),
            "invoice_no": one.invoice_no,
            "status": one.status,
            "period_start": one.period_start.isoformat() if one.period_start else None,
            "period_end": one.period_end.isoformat() if one.period_end else None,
            "issued_on": one.issued_at.date().isoformat() if one.issued_at else None,
            "due_on": one.due_date.isoformat() if one.due_date else None,
            "currency": one.currency,
            "subtotal": str(one.subtotal),
            "tax_total": str(one.tax_total),
            "total": str(one.total),
            "bill_run_id": str(one.bill_run_id) if one.bill_run_id else None,
            "lines": by_invoice.get(str(one.pk), []),
        }
        for one in invoices
    ]


# ── CR-075 wave K · the reads runbook 9 makes (US-RBS-009) ─────────────────


def unfinished_runs(period_start, period_end) -> tuple[dict, ...]:
    """Bill runs of this window that are neither issued nor cancelled.

    `apps.billing.selectors.unfinished_runs` — and its sibling
    `unissued_run_count` is the read **the ledger's own close checklist has
    named by exact signature since `US-LED-006` and never got**. Until
    2026-09-07 nothing published it, so `close_checklist`'s *"every run
    finished"* item reported UNKNOWN on every tenant for ever, and an unknown
    item counts as incomplete — no utility could reach a green close. Runbook 9
    step 1 is the reader that finally needed it.

    ⚠ **`failed` COUNTS AS UNFINISHED, AND THAT IS BILLING'S RULING RATHER THAN
    THIS RUNBOOK'S.** `SETTLED_RUN_STATUSES` is `completed` and `cancelled` and
    nothing else: a failed run stopped part-way and somebody has to decide
    whether to re-run it or cancel it. A month closed over one is a month whose
    bills nobody can account for. The set lives beside the column it filters,
    which is what stops a second definition of *finished* growing here.

    ⚠ **THE WINDOW IS THE RUN'S PERIOD AND NOT ITS CREATION DATE.** A run
    created on 2 September for the August cycle belongs to August's close.
    Dating it by `created_at` would let a clerk close August while August's own
    bills were still half-issued, which is the one thing this step exists to
    stop.
    """
    from apps.billing import selectors as billing_selectors

    return tuple(dict(row) for row in billing_selectors.unfinished_runs(period_start, period_end))


def last_issued_bill_dates(account_ids) -> dict[str, object]:
    """When each account was last ISSUED a bill — ONE query for the whole set.

    `apps.billing.selectors.last_issued_invoice_dates`, the bulk form billing
    already publishes for the accounts list. Runbook 27 asks it of every closing
    account at once; the single-account read beside it would be one query per
    move-out, and the backwards half of that runbook's window has no bound at
    all — *any closed account with no final bill, however old*.

    ⚠ **ISSUED, NEVER A DRAFT** (`INVOICE_LOCKED_STATUSES`). A draft is freely
    replaced and discarded (`BR-BIL-004`), so counting one as the final bill
    would close an account against a document the customer never received.

    ⚠ **AN ACCOUNT WITH NO ISSUED BILL IS ABSENT FROM THE MAPPING**, not present
    with `None` — the owning selector's own posture, so a caller's `in` test and
    its `.get()` agree.
    """
    from apps.billing import selectors as billing_selectors

    return dict(billing_selectors.last_issued_invoice_dates(list(account_ids or [])))


# ── CR-075 wave S · the reads runbooks 6 and 16 make ──────────────────────

def bill_runs(*, limit: int = 25) -> list[dict[str, object]]:
    """The bill runs a person can pick, newest first — `RB-106`'s scope row.

    `apps.billing.selectors.bill_runs_list`, which is the same history SET-07D
    draws, so the run a clerk picked on the billing screen and the run this
    runbook explains cannot be two different lists.
    """
    from apps.billing import selectors as billing_selectors

    return [dict(one) for one in billing_selectors.bill_runs_list(limit=limit)]


def bill_run_outcome(run_id) -> dict[str, object] | None:
    """WHAT ONE RUN DID TO EVERY ACCOUNT IN IT — or `None` when there is no run.

    `RB-106` asks *"a bill run finished and this account produced nothing — what
    stopped it?"*, and the answer the run itself recorded is in three places:
    the **breaks** it raised (`billing.selectors.run_breaks_dict`, keyed by the
    pipeline's own stage), the **exclusions** somebody made deliberately, and
    the **invoices** it actually issued. One read, because a runbook that asked
    three times could show a break for an account whose bill landed between two
    of the questions.

    ⚠ **A BREAK CARRIES THE STAGE, AND THE STAGE IS WHAT MAKES THIS RUNBOOK
    HONEST.** `runs.STAGE_BY_REASON` maps every refusal onto
    `resolve-subscription`, `measure-consumption` or `price-usage` — the
    pipeline's own names (`BR-BIL-037`) — so the step a runbook says stopped an
    account is the step that actually did, rather than an inference from the
    words of a message.

    ⚠ **`include_resolved=True`, DELIBERATELY.** The default list is the clerk's
    outstanding work; this runbook is asked *why did this account not bill on
    that run*, which is a question about history. A break somebody has since
    resolved still explains the run, and hiding it would answer *"nothing
    stopped it"* over an account that plainly did not bill.

    ⚠ **NO MONEY CROSSES HERE.** The invoiced set is a set of account ids: what
    a bill came to is `RB-104`'s question, and a seam that carried a total would
    invite this runbook to start explaining amounts it never checked.
    """
    from apps.billing import models as billing_models
    from apps.billing import selectors as billing_selectors
    from core import errors

    if run_id in (None, ""):
        return None
    try:
        run = billing_selectors.run_or_404(run_id)
    except (errors.NotFoundError, ValueError, TypeError):
        return None

    breaks = billing_selectors.run_breaks_dict(run, include_resolved=True)
    exclusions = billing_models.BillRunExclusion.objects.filter(bill_run=run).values(
        "account_id", "reason_code", "detail", "resolved_by_run_id"
    )
    billed = billing_models.Invoice.objects.filter(bill_run=run).values_list(
        "account_id", flat=True
    )
    return {
        "run_id": str(run.pk),
        "run_no": run.run_no,
        "status": run.status,
        "bill_type": run.bill_type,
        "cycle_id": str(run.cycle_id) if run.cycle_id else None,
        "period_start": run.period_start.isoformat() if run.period_start else None,
        "period_end": run.period_end.isoformat() if run.period_end else None,
        "breaks": list(breaks.get("breaks") or []),
        "breaks_by_stage": dict(breaks.get("breaks_by_stage") or {}),
        "exclusions": [
            {
                "account_id": str(one["account_id"]),
                "reason_code": one["reason_code"],
                "detail": one["detail"],
                "resolved_by_a_later_run": bool(one["resolved_by_run_id"]),
            }
            for one in exclusions
        ],
        "billed_account_ids": [str(one) for one in billed],
    }


# ── CR-075 runbook 33 · the budget programme (US-RBS-044) ─────────────────
#
# Added with `definitions/budget_relevel.py` in the same commit. Both calls
# below resolve selectors `billing` already publishes —
# `apps.billing.selectors.budget_programme_overview` and
# `apps.billing.selectors.budget_history_for` — and nothing here re-implements
# a rule that lives on the far side (`BR-RBS-039`, `G20`).


def budget_programme() -> dict[str, object]:
    """Every account on the budget programme, with the tenant's own S69 rules.

    `RB-133` step 1. Two things in one read, deliberately: a runbook that asked
    for the levels and the drift band separately could be handed levels computed
    under one setting and a band from another, and then report a change nobody's
    settings asked for.

    ⚠ **THE SETTINGS ARE THE TENANT'S AND ARE READ, NEVER DEFAULTED** —
    `RBR-03`, policy lives in Settings and is never duplicated on a card. This
    runbook's *Drift*, *Cadence* and *Averaging window* rows are drawn dashed
    and read-only for that reason, and the numbers behind them come from here.

    ⚠ **`level` AND `level_override` BOTH TRAVEL.** What the customer PAYS is
    `effective_level`; what a re-level MOVES is `level`. On an account carrying
    an override those are two different numbers and a report that showed one of
    them would tell a clerk a customer's payment is changing when it is not.
    """
    from apps.billing import selectors as billing_selectors

    answer = billing_selectors.budget_programme_overview()
    return {
        "settings": dict(answer.get("settings") or {}),
        "accounts": [dict(one) for one in (answer.get("accounts") or [])],
    }


def budget_trailing_actuals(account_id, *, months: int = 12) -> dict[str, object]:
    """The trailing ISSUED actuals a level is the average of, newest first.

    `RB-133` step 2, and it is `apps.billing.selectors.budget_history_for` —
    the SAME read `budget_service.relevel` uses, so the level this runbook shows
    a clerk and the level billing would compute cannot differ. Re-implementing
    the twelve-month window here would be a second answer to a signed figure
    (❄️ `GT-24`: $2,904 over twelve months → a level of **$242**).

    ⚠ **`months_of_history` COUNTS DISTINCT BILLED PERIODS, NOT BILLS.** Two
    bills in one month — a cycle bill and a back-bill — are one month of
    history, and an account with fewer months than the tenant's averaging window
    has no supportable level at all. The runbook says so rather than averaging
    what it has.

    ⚠ **A DRAFT IS NOT AN ACTUAL.** Only issued and paid bills are in the set,
    which is billing's own rule and the reason a level is never computed from
    numbers that can still change.
    """
    from apps.billing import selectors as billing_selectors

    return dict(billing_selectors.budget_history_for(account_id, months=months))


# ── CR-075 wave S · the read runbook 16 makes (US-RBS-028) ────────────────


def issued_bills_for_run(run_id, *, service_code: str | None = None) -> dict[str, object]:
    """EVERY ISSUED BILL OF ONE CYCLE, with the lines of one service.

    `RB-116` step 2 — *"Load the cycle as it was billed · Every account's usage,
    days and plan"* — and its scope sentence, *"Re-prices 1,410 bills exactly as
    issued."*

    ⚠ **ISSUED, NEVER A DRAFT** (`BR-BIL-004`, and `issued_bills_for_account`
    above states it for the same reason). A preview shown to a board must be a
    preview against bills customers actually received; a draft is freely
    replaced, so re-pricing one would compare a proposal against a document that
    never existed.

    ⚠ **THE DAY COUNT TRAVELS AND IT IS THE BILL'S OWN.** `period_start` and
    `period_end` are on the row, so the engine is handed the cycle each bill was
    actually priced over rather than a nominal month — a re-price against the
    wrong day count misprices every proration and every time-of-use window in
    the ladder, and it does it silently.

    ⚠ **ONE QUERY FOR THE LINES OF THE WHOLE CYCLE** (`NFR-3`). A per-bill read
    is correct at 3,000 accounts and 13× short at 40,000, which is
    `DEF-PAY-4221`'s shape; a rate-change preview is asked of the biggest cycle
    a utility has.

    ⚠ **`service_code` NARROWS THE LINES AND NEVER THE BILLS.** A bill with no
    line of that service is still part of the cycle and is still counted — it is
    a bill the draft does not touch, which is a finding (*88 unchanged*) rather
    than an absence. Dropping it would make the denominator of every percentage
    on the screen wrong.

    ⚠ **NO ROUNDING AND NO `Decimal` CROSSES.** Money travels as its stored
    four-decimal string, exactly as `issued_bills_for_account` sends it.
    """
    from apps.billing import models as billing_models

    invoices = list(
        billing_models.Invoice.objects.filter(bill_run_id=run_id)
        .exclude(status=billing_models.INVOICE_DRAFT)
        .order_by("account_id", "id")
    )
    if not invoices:
        return {"bills": [], "bills_in_the_cycle": 0, "lines_of_this_service": 0}
    lines = billing_models.InvoiceLine.objects.filter(
        invoice_id__in=[one.pk for one in invoices]
    ).select_related("service").order_by("created_at", "id")
    by_invoice: dict[str, list[dict[str, object]]] = {}
    counted = 0
    for line in lines:
        code = line.service.code if line.service_id else None
        if service_code and code != service_code:
            continue
        counted += 1
        by_invoice.setdefault(str(line.invoice_id), []).append(
            {
                "kind": line.kind,
                "description": line.description,
                "amount": str(line.amount),
                "quantity": None if line.quantity is None else str(line.quantity),
                "unit": line.unit,
                "unit_price": None if line.unit_price is None else str(line.unit_price),
                "service": code,
                "taxable": bool(line.taxable),
                # ⚠ **WHICH VERSION PRICED THIS LINE, STAMPED AT ISSUE AND
                # FROZEN** — the only honest answer to *what was this bill priced
                # under*, and what lets the preview say whether a bill was
                # already on the version it is being compared with.
                "tariff_version_id": (
                    str(line.tariff_version_id) if line.tariff_version_id else None
                ),
            }
        )
    return {
        "bills": [
            {
                "bill_id": str(one.pk),
                "invoice_no": one.invoice_no,
                "account_id": str(one.account_id),
                "period_start": one.period_start.isoformat() if one.period_start else None,
                "period_end": one.period_end.isoformat() if one.period_end else None,
                "service_date": one.service_date.isoformat() if one.service_date else None,
                "currency": one.currency,
                "subtotal": str(one.subtotal),
                "tax_total": str(one.tax_total),
                "total": str(one.total),
                "lines": by_invoice.get(str(one.pk), []),
            }
            for one in invoices
        ],
        "bills_in_the_cycle": len(invoices),
        "lines_of_this_service": counted,
    }

def budget_level_decision(
    *,
    actuals,
    months: int,
    rounding: str,
    current_level,
    drift_pct,
    months_since_last_level: int,
    cadence_months: int,
) -> dict[str, object]:
    """What level these actuals support, and whether `BR-BIL-017` moves it.

    ⚠ **THIS IS A SEAM AND NOT A CONVENIENCE, AND `G115` IS WHAT MADE IT ONE.**
    The first build of runbook 33 did `from apps.billing import budget` inside a
    step and called `compute_level`, `drift_fraction` and `relevel_due`
    directly. That is a foreign import outside the two lawful doors —
    `BR-RBS-039` — and `G115` refused it by file and line before it could merge.
    **The fix is not to move the import; it is to move the QUESTION.** A runbook
    asks *what level do these actuals support and does it move*, and billing
    answers with its own signed arithmetic; a runbook that imported the three
    functions would be assembling `BR-BIL-017`'s rule on this side of the seam,
    where the next lane could reorder its two gates without billing noticing.

    ⚠ **THE ARITHMETIC IS ❄️ FROZEN AND IS NOT RE-IMPLEMENTED ANYWHERE.**
    `apps.billing.budget.compute_level` is `GT-24`'s own: $2,904 over twelve
    months rounds half-up to a level of **$242**. `relevel_due` applies BOTH of
    `BR-BIL-017`'s gates — at cadence AND past the drift band — in that order.

    ⚠ **THE TWO REFUSALS TRAVEL AS ANSWERS RATHER THAN AS EXCEPTIONS.** A zero
    current level cannot be a denominator and `drift_fraction` refuses one by
    name; an unknown rounding mode stops the enrolment rather than falling
    through to whole dollars. Both would otherwise fail the whole record inside
    its savepoint, which reads on screen as *this account errored* when the
    truth is *this account has no level to measure a change against*. So they
    come back as `supported_level: None` with a `refused` sentence, and the
    runbook puts that sentence on the row.
    """
    from apps.billing import budget as budget_math

    try:
        supported = budget_math.compute_level(
            trailing_actuals=list(actuals), months=months, rounding=rounding
        )
    except ValueError as refusal:
        return {"supported_level": None, "refused": str(refusal), "moves": False}
    try:
        drift = budget_math.drift_fraction(current_level=current_level, recomputed_level=supported)
    except ValueError as refusal:
        return {
            "supported_level": str(supported),
            "refused": str(refusal),
            "moves": False,
        }
    moves = budget_math.relevel_due(
        current_level=current_level,
        recomputed_level=supported,
        drift_pct=drift_pct,
        months_since_last_level=months_since_last_level,
        cadence_months=cadence_months,
    )
    return {
        "supported_level": str(supported),
        "drift_fraction": str(drift),
        "moves": bool(moves),
        "at_cadence": months_since_last_level >= cadence_months,
        "refused": "",
    }

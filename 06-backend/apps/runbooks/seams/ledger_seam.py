# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-041 (EP-RBS-01) — CR-075 wave A task A4.
# Rules:    BR-RBS-039 (read through a seam this module owns, by name, in
#           process, under the tenant context) · CLAUDE.md hard rule 1 ·
#           hard rule 5 (only the ledger posting service writes journal lines) ·
#           BR-RBS-030 (closing a period stays a named person's act)
# Tests:    06-backend/tests/test_us_rbs_041_module.py
# Impacts:  B2 Addendum r25 (this seam's row in the cross-module interface
#           register, added in the same commit as this file)
# ───────────────────────────────────────────────────────
"""operations → ledger — period postings, journal lines. READ ONLY.

The month-end tie-out and the cutover reconciliation read here, mostly in **set
mode**: a totals comparison over 1.2M journal lines would be awkward and slow
one row at a time, which is why the contract has two step modes rather than one.

⚠ **THERE IS NO LEDGER PORT AT ALL** — not one of the thirteen is owned by
`ledger`, and that is deliberate rather than an omission. Only the ledger
posting service writes journal lines (CLAUDE.md hard rule 5), so a runbook can
tell a clerk the books do not tie out to the penny and **cannot post the
correction**. Closing a period likewise stays a named person's act
(`BR-RBS-030`): the button enables when the exception list is empty and a person
presses it. Whether that could ever be automated is `OQ-RBS-1736`, which is
OPEN — and a later *yes* would be an addition, never a correction.

⚠ **THIS FILE DECLARES THE PAIR AND HOLDS NO CALLABLE YET, ON PURPOSE.** Wave A
builds the module and its boundary; wave K brings the books tie-out and the
reads it actually needs. A selector written here now would be a function nothing
calls (hard-won law 2), and naming one in prose that `ledger` does not expose
would fail `G20` — the guard that caught `DEF-075`. What this module will need
and `ledger` does not offer today is inventoried in
`17-runbooks/13-selector-inventory.md`, and **`ledger` adds each of them** —
never this file reaching past the seam.
"""

from apps.runbooks.boundary import SeamDeclaration

SEAM = SeamDeclaration(
    module="ledger",
    pair="operations → ledger",
    crosses="period postings, journal lines",
)


# ── CR-075 wave C · the reads runbook 1 makes (US-RBS-001) ────────────────


def revenue_account_for(service_code: str):
    """The revenue account a service's usage line lands in, or `None`.

    `apps.ledger.selectors.revenue_account_id_for_service`. `None` is a real
    state rather than an error — the nine accounts `CR-066` adds reach a tenant
    on the day it is PROVISIONED and never afterwards (hard-won law 4) — and it
    is exactly the state runbook 1 step 10 exists to put on a screen, because a
    line with no account refuses at issue and the refusal arrives on bill day.
    """
    from apps.ledger import selectors as ledger_selectors

    return ledger_selectors.revenue_account_id_for_service(service_code)


def unmapped_designations() -> list[str]:
    """The ledger designations this tenant has NOT mapped to an account.

    `apps.ledger.selectors.designation_map` returns all eleven keys always, with
    `None` where nothing is mapped — which is why it can answer this at all: a
    map that omitted its gaps could only ever report success.
    """
    from apps.ledger import selectors as ledger_selectors

    return sorted(name for name, account in ledger_selectors.designation_map().items() if not account)


# ── CR-075 · the reads the month-end journal file makes (US-RBS-042) ───────


def posted_months() -> tuple[tuple, ...]:
    """Every accounting month this tenant has posted into — the input's DOMAIN.

    `apps.ledger.selectors.posted_months`. `BR-RBS-042` clause 2: a domain is
    tenant-resolved and never hardcoded, and **an empty domain says so** rather
    than silently offering nothing — a utility that has posted nothing has no
    month to export and the runbook says that in words rather than producing an
    empty file.
    """
    from apps.ledger import selectors as ledger_selectors

    return ledger_selectors.posted_months()


def accounts_without_a_code() -> tuple[dict, ...]:
    """Live accounts a bookkeeper's chart cannot be mapped to — a blank code.

    `apps.ledger.selectors.accounts_without_a_code`. This is the one shape of
    *cannot be exported* that lives on the account rather than on the money: an
    importer addresses an account by its CODE, so a blank one has nothing to put
    in the column. **The export reports it and never invents one** — a guessed
    code imports cleanly and puts money where nobody chose it.
    """
    from apps.ledger import selectors as ledger_selectors

    return ledger_selectors.accounts_without_a_code()


def period_figures(period_start, period_end) -> dict:
    """One month's books, as the LEDGER publishes them. **Nothing is re-summed.**

    `apps.ledger.exports.export_preview` with the plain-CSV target. It is a
    READ — its own docstring says *"Writes NOTHING"* — and it already answers
    every question this runbook has to ask of a period: the per-account debit
    and credit rows, whether the period foots, whether it has been closed, and
    whether an account is missing the target's reference.

    ⚠ **CALLING IT IS THE POINT, NOT A CONVENIENCE.** `apps/ledger/exports.py`
    opens with *"THIS MODULE COMPUTES NO MONEY … a second summation here would
    be a second answer to what did July hold, and the day the two disagreed the
    ERP would hold the wrong one."* A runbook that added its own `SUM(amount)`
    over `journal_lines` would be exactly that second answer, and it would be
    the one on the bookkeeper's desk. So the figures cross this seam and the
    arithmetic never does.

    ⚠ **THE LEDGER'S OWN OBJECTS DO NOT CROSS.** `SummaryRow` is a `ledger`
    dataclass; what comes back here is plain data with `Decimal` money, for the
    same reason runbook 1 names `BASIS_METERED` by value rather than importing
    another module's constant — **the VALUE crosses the seam, never the name**.

    ⚠ **THE TARGET IS THE PLAIN CSV AND THAT DECIDES ONE THING.**
    `REF_FIELD_BY_TARGET` maps `csv` to `None`, so `missing_refs` is empty by
    construction: a general-journal CSV addresses an account by code and name
    and needs no QuickBooks or Xero reference. It is still read and still
    reported, because the day a tenant exports to one of those targets the
    same list is what refuses.
    """
    from apps.ledger import exports as ledger_exports

    preview = ledger_exports.export_preview(
        period_start=period_start, period_end=period_end, target="csv"
    )
    return {
        "rows": tuple(
            {
                "code": row.code,
                "name": row.name,
                "debit": row.debit,
                "credit": row.credit,
                "window_end": row.window_end,
            }
            for row in preview["rows"]
        ),
        "total_debits": preview["period_total_debits"],
        "total_credits": preview["period_total_credits"],
        "balanced": bool(preview["balanced"]),
        "period_closed": bool(preview["period_closed"]),
        "missing_refs": tuple(preview["missing_refs"]),
    }


# ── CR-075 waves J and K · the reads runbooks 2 and 9 make ─────────────────
#
# `US-RBS-008` (cutover reconciliation) and `US-RBS-009` (books tie-out). Every
# one resolves a callable the LEDGER already publishes and computes nothing:
# hard rule 5 says only the ledger posting service writes journal lines, and the
# quieter half of it is that only the ledger DECIDES what the books hold. A
# tie-out READS.


def account_positions(as_of=None) -> dict:
    """What each customer account still owes, per account — `{id: Decimal}`.

    `apps.ledger.reporting.ar_positions`. It is the PER-ACCOUNT slice of the
    same Σ the AR control total publishes, so an account row, the finance KPI
    and the cutover comparison are one derivation grouped three ways and cannot
    disagree (`BR-REP-002`).

    ⚠ **AN EMPTY `positions` IS NOT ZEROS AND THE FLAG IS WHY THIS RETURNS A
    MAPPING RATHER THAN A DICT OF MONEY.** `DEF-127`: with no AR designation at
    all the ledger can answer nothing, and a caller that read the empty dict as
    "everybody owes nothing" would tell an implementer their cutover balanced
    when nothing had been compared. `available` carries the difference and
    runbook 2 refuses the step on it.

    ⚠ **IT IS NOT `accounts.balance`.** That column is customers' CACHE
    (`BR-CUS-015`) and nothing in this product has ever written it, so a cutover
    driven off it would report every loaded balance as `$0.00` and every account
    in the legacy file as a difference — 2,907 findings and not one of them
    real.
    """
    from apps.ledger import reporting as ledger_reporting

    answer = ledger_reporting.ar_positions(as_of=as_of)
    return {
        "positions": {str(key): value for key, value in (answer.get("positions") or {}).items()},
        "currency": answer.get("currency"),
        "available": bool(answer.get("available")),
        "unavailable": tuple(answer.get("unavailable") or ()),
    }


def tie_out_rows(period_start, period_end) -> dict:
    """The four control-vs-register comparisons, and whether they block a close.

    `apps.ledger.tie_out.tie_outs` — accounts receivable, deposit liability, tax
    payable and cost of service, each with the GL figure, the register figure,
    the drift and a verdict. This is `BR-LED-007` applied, and it is the ONLY
    place in the product that applies it: `_verdict` says so in its own words —
    *"one implementation so that the API, the screen and the audit row cannot
    disagree about whether a book is drifting, which would be this check
    developing the very fault it exists to detect."*

    ⚠ **RUNBOOK 9 SUBTRACTS NOTHING.** A month-end tie-out that computed its own
    `gl − register` would be a second answer to *do the books agree*, and it
    would be the one on the finance user's desk on the day they disagreed. Every
    figure below crosses this seam already decided.

    ⚠ **THE TAX ROW IS KNOWN TO BE WRONG FROM THE SECOND POSTED PERIOD ONWARD —
    `DEF-LED-4356`, found by this very runbook on 2026-09-07 and filed rather
    than fixed here.** `_tax_row` takes the GL side cumulative to `period_end`
    and the register side for `period_start..period_end`, so from month two the
    drift contains every earlier month's tax on a correct book. Measured on the
    seeded utility: July GL 816.45 against 818.75 outstanding, drift −2.30 —
    the one real discrepancy — and August GL 1,657.64 against 841.19, drift
    +816.45, which is exactly July's cumulative GL. **Runbook 9 names the defect
    on the row rather than smoothing it**, because a tie-out that quietly
    corrected another module's arithmetic would be the second answer this seam
    exists to prevent, and one nobody could find.

    `TieOutRow` is a `ledger` dataclass and does NOT cross: what comes back is
    plain data with `Decimal` money, for the same reason `period_figures` above
    passes values rather than names.
    """
    from apps.ledger import tie_out as ledger_tie_out

    answer = ledger_tie_out.tie_outs(period_start=period_start, period_end=period_end)
    return {
        "rows": tuple(
            {
                "subledger": row.subledger,
                "state": row.state,
                "gl": row.gl,
                "register": row.register,
                "drift": row.drift,
                "currency": row.currency,
                "causes": tuple(dict(cause) for cause in row.causes),
            }
            for row in answer["rows"]
        ),
        "drifting": tuple(answer["drifting"]),
        "unverifiable": tuple(answer["unverifiable"]),
        "release_blocked": bool(answer["release_blocked"]),
    }


def close_checklist(period_start, period_end) -> dict:
    """The seven items the LEDGER requires before a period may be closed.

    `apps.ledger.close.close_checklist`. Runbook 9 does not invent a month-end
    checklist: the ledger owns the period and `BR-LED-006` requires these items
    *"computed from live register states, never checkboxes typed by hand"*.
    This seam carries them into a runbook's steps so that the finding a clerk
    reads and the thing that would actually refuse the close are the same fact.

    ⚠ **THREE STATES AND NOT TWO.** `complete` · `incomplete` · `unknown`, and
    `unknown` means *the register could not be read*, which counts as incomplete
    on purpose — a green tick nobody computed is hard-won law 1 exactly. Runbook
    9 renders the three differently, because *"we looked and it is not done"*
    and *"we could not look"* are different sentences to a finance user and only
    one of them names a fix they can perform.

    ⚠ **`ready` IS THE LEDGER'S OWN WORD FOR *nothing is outstanding* AND IT IS
    NOT THE SAME AS *the books balance*.** The checklist is about work; the
    tie-outs above are about arithmetic. Runbook 9 needs both and neither
    subsumes the other — a month can have every task done and still not foot.
    """
    from apps.ledger import close as ledger_close

    answer = ledger_close.close_checklist(period_start=period_start, period_end=period_end)
    return {
        "items": tuple(
            {
                "code": item.code,
                "state": item.state,
                "detail": item.detail,
                "outstanding": item.outstanding,
                "wanted_reads": tuple(item.wanted_reads),
            }
            for item in answer["items"]
        ),
        "ready": bool(answer["ready"]),
        "closed": bool(answer["closed"]),
        "unavailable": tuple(dict(one) for one in answer["unavailable"]),
    }

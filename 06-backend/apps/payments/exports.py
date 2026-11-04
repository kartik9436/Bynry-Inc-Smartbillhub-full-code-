# ── Trace ──────────────────────────────────────────────
# Change:   P4.6 (Finance blueprint p017) — "Deposit slip · no deposits export
#           resource is registered anywhere". Outcome: *"a bookkeeper gets the
#           slip the screen has been promising"*.
# Rules:    BR-TEN-031 (the OWNING module supplies the column set, the selector
#           call and the vocabulary — deposits are payments') · BR-REP-018 /
#           IS-11 (CSV always, strict contract, context in the filename) ·
#           BR-REP-001 (a money file LABELS its date basis) · BR-SHL-016 /
#           BR-SHL-029 (server-side, capped, money exports write `audit_log`) ·
#           BR-SHL-011 (the export mirrors the list's OWN filter state) ·
#           CLAUDE.md rule 2 (money 4dp stored, 2dp displayed) · rule 7
# Tests:    06-backend/tests/test_p4_6_deposit_slip.py
# Impacts:  apps/payments/apps.py registers this at startup ·
#           apps/tenancy/exports.py (the kernel that writes the bytes) ·
#           07-frontend DepositsPage.tsx (the control that was disabled)
# ───────────────────────────────────────────────────────
"""The deposit slip — S37's download, on the ONE export kernel.

`DepositsPage.tsx` has carried a DISABLED download since the screen shipped,
with `payments.deposits.slipUnavailable` beside it and this comment above it:

    BR-SHL-025 — the affordance exists and says why it cannot be used, rather
    than being hidden so nobody knows it is coming.

That was right, and the reason it gave was true: no deposits export resource
was registered anywhere. This file is the registration, and the control works.

**THE BASIS IS `clearing`, AND THAT IS THE WHOLE OF `BR-REP-001` HERE.** A
deposit batch is a BANK event — it is money that has left the counter and
reached an account — so its date is a clearing-side date, not a posting-side
one. `apps/reports/exports.py` labels `payments_by_method` the same way for the
same reason, and its comment says why in one sentence: *"a bookkeeper holding
two files of the same month can tell which is which"*. A deposit file stamped
`posting` would sit beside the trial balance claiming to be the same kind of
number, and it is not.

**WHAT THE FILE IS NOT.** It is the deposit LIST — one row per batch, which is
what the control on S37 is attached to and what a bookkeeper reconciling
against a bank statement needs. It is **not** a per-batch paying-in slip with
the individual payments on it; that is a different artefact off a different
screen (`DepositBatchPage`), and building it here would put two meanings behind
one button. Stated rather than left to be discovered.

⚠ **`difference` IS `None` UNTIL A BANK TOTAL IS TYPED, AND A `None` MUST NOT
BECOME `0.00`.** `bankrec_read.batch_row` returns `None` when `bank_total` is
unset, and zero there reads as *"the batch reconciles exactly"* about a batch
nobody has checked. The kernel's `format_value` writes an empty cell for a
None, which is the honest shape and is the same thing the screen shows.
"""

from __future__ import annotations

from typing import Any

from apps.tenancy import exports as export_kernel
from core.pagination import ListParams

from . import bankrec_read

#: IS-11's `{report}` segment. Hyphenated — a filename is a DISPLAY artifact
#: and the API key is a CONTRACT (`DEF-131`).
SLUG = "deposits"


def _rows(params: ListParams) -> list[dict[str, Any]]:
    """S37's own rows, from the SAME read the screen renders.

    `status` and `method` ride from the list's filter state, so the file is the
    list a person is looking at rather than an approximation of it re-derived
    under different defaults. A filter the read does not honour is ignored
    here exactly as it is there — BR-SHL-011, *"fall back, never 4xx"*.
    """
    filters = params.filters or {}
    return list(
        bankrec_read.batch_list(
            status=filters.get("status") or None,
            method_code=filters.get("method") or None,
        ).get("rows", ())
    )


DEPOSITS = export_kernel.ExportResource(
    name="deposits",
    slug=SLUG,
    module="payments",
    select=_rows,
    columns=(
        # S37's own capability row, in the order the table draws them.
        export_kernel.ExportColumn("batch", "code"),
        export_kernel.ExportColumn("method", "method_name"),
        export_kernel.ExportColumn("deposited_on", "deposited_on", export_kernel.DATE),
        export_kernel.ExportColumn("payments", "payment_count", export_kernel.NUMBER),
        export_kernel.ExportColumn("recorded_total", "recorded_total", export_kernel.MONEY),
        export_kernel.ExportColumn("bank_total", "bank_total", export_kernel.MONEY),
        # ⚠ EMPTY, never 0.00, until somebody types the bank total. See the
        # module docstring — a zero here says the batch reconciles exactly.
        export_kernel.ExportColumn("difference", "difference", export_kernel.MONEY),
        export_kernel.ExportColumn("status", "status"),
    ),
    money=True,
    # BR-REP-001 — a deposit is a BANK event. See the module docstring.
    basis="clearing",
    period="full-list",
    filters=("status", "method"),
)

RESOURCES = (DEPOSITS,)


def register() -> None:
    """Called once from `PaymentsConfig.ready()`."""
    for resource in RESOURCES:
        export_kernel.register_export_resource(resource)


# ── Lifecycle ─────────────────────────────────────────────
# packet: P4.6 (05-prototype/07 Finance Blueprint.pdf p017 · apps/reports/exports.py and apps/ledger/finance_exports.py, the precedents this copies)
# screens: 3·1 Deposits (S37)
# generated: 2026-09-24 by lane FIN-P4
# checklist: A✔ B✔ C✔ D=deferred(registers against POST /exports, which already exists) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: (1) this is the deposit LIST, not a per-batch paying-in slip with its individual payments — the control on S37 is attached to the list, and two meanings behind one button is a worse answer than one stated meaning · (2) the basis is `clearing` rather than `posting`, because a deposit is a bank event (BR-REP-001) · (3) NO PDF — this deployment has no PDF renderer of any kind
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

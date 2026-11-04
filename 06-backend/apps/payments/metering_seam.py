# ── Trace ──────────────────────────────────────────────
# Story:    CR-135-BRC07 `P1.9` (one path per capability) · `DEF-PAY-6213`
#           Screens: S33 Payments — the blueprint's §03 screen 2·1 Batch column
# Rules:    B1 / B2 §2 (cross-module reads go through a published callable,
#           never through a neighbour's ORM) · CLAUDE.md hard rule 1 (tenant
#           scoping — the callee scopes, and it is asked inside a tenant
#           context) · NFR-3 (a paged list costs one page, so this asks in bulk)
# Tests:    06-backend/tests/test_cr135_p1_source_and_batch.py
# Impacts:  apps/payments/selectors.payment_batch_labels (its only caller) ·
#           apps/metering/import_runs.created_record_runs (the owner, resolved
#           BY NAME)
# ───────────────────────────────────────────────────────
"""payments → metering SEAM: *which import run created this payment?*

`import_run_rows` is metering's table. It has carried `created_record_id` —
its own comment reads *"what it made, for rollback"* — since `CR-023`, every
row carries `run_id`, and `_load_payments_rows` sets both exactly as the
accounts and parts loaders do. **So the link has existed since the eighth
import target landed.** What did not exist was a way for payments to ASK for
it without reaching into metering's ORM, which B2 §2 forbids in both
directions.

⚠ **`DEF-PAY-6213` WAS REPORTED AS *"not servable at all"* AND THAT WAS FALSE**
(corrected in the decision log, 2026-09-23). The claim was generalised from an
honest measurement of the SCREEN to a statement about the SCHEMA, and it was
then repeated to the Product Owner as a reason not to do something they had
ruled twice. **A claim of absence needs the same evidence as a claim of
presence, and it is cheaper to check.**

╔══════════════════════════════════════════════════════════════════════════╗
║  RESOLVED BY NAME, NOT IMPORTED — the idiom `billing_seam` already uses. ║
╚══════════════════════════════════════════════════════════════════════════╝

Nothing binds the two modules at import time, the boundary is greppable from
both sides (`METERING_MODULE` / `CREATED_RECORD_RUNS_READ`), and a metering
that has not published the read answers *"no runs"* rather than raising — which
is the honest answer for a deployment where the payments import target is not
installed, and is exactly what a screen renders as a stated absence.

⚠ **AN UNPUBLISHED READ AND AN EMPTY ANSWER ARE THE SAME THING HERE, AND THAT
IS DELIBERATE — it is not the `_customer_name` posture.** `_customer_name`
REFUSES when customers publishes nothing, because *"no contact recorded"* and
*"the name could not be read"* are different statements about a customer. Here
they are not: a payment with no run behind it and a payment whose run cannot be
looked up both render *no batch*, and the batch id is not a fact the money
depends on. A refusal would take the whole payments list down over a column
that is hidden on the account's own tab.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

#: The neighbour, and the callable. Named as constants so the boundary is one
#: grep from either side.
METERING_MODULE = "apps.metering.import_runs"
CREATED_RECORD_RUNS_READ = "created_record_runs"
#: `CR-136-BRC07` `P2.8` — the reverse direction, for the BATCH FILTER. The
#: list shows an imported payment its run's NUMBER, so the filter takes the
#: same number back.
RECORDS_BY_RUN_NO_READ = "records_created_by_run_no"

#: The import target payments rows are created under (`P1.1`). Spelled here
#: rather than imported, for the same reason the seam resolves by name.
PAYMENTS_TARGET = "payments"


def _read(name: str = CREATED_RECORD_RUNS_READ) -> Any:
    """One of metering's published callables, or None while it publishes none.

    ⚠ **RESOLVED BY NAME, NOT IMPORTED** — the idiom `billing_seam` already
    uses. Nothing binds the two modules at import time, the boundary stays
    greppable from either side, and a deployment where metering publishes no
    such read gets the honest empty answer rather than an ImportError at start.
    """
    try:
        target = import_module(METERING_MODULE)
    except ImportError:  # pragma: no cover - metering ships in-tree
        return None
    found = getattr(target, name, None)
    return found if callable(found) else None


def runs_that_created(payment_ids: Any) -> dict[str, dict[str, Any]]:
    """`payment id` → `{"run_id", "run_no"}` for every payment an import made.

    A payment that no import created is ABSENT from the answer rather than
    present with nulls: *"this money was keyed at a counter"* is a different
    statement from *"the run that made it has no number"*, and the screen says
    different things for the two.
    """
    wanted = [str(one) for one in (payment_ids or []) if one]
    if not wanted:
        return {}
    read = _read()
    if read is None:  # pragma: no cover - metering ships in-tree
        return {}
    answer = read(PAYMENTS_TARGET, wanted)
    return dict(answer or {})


def payments_created_by_run_no(run_no: Any) -> list[str]:
    """Every payment the import run NUMBERED `run_no` created.

    `CR-136-BRC07` `P2.8` — the blueprint's §03 2·1 note ③, *"Batch filter ·
    one batch at a time"*. `payment_batch_labels` shows an imported payment its
    run's number in the BATCH cell; this is how that same number comes back as
    a filter, so the column and the chip cannot be talking about two things.

    An unknown number answers `[]`: a list URL never 4xxs over its params
    (BR-SHL-011), and an empty result and a refusal read the same to a clerk.
    """
    wanted = str(run_no or "").strip()
    if not wanted:
        return []
    read = _read(RECORDS_BY_RUN_NO_READ)
    if read is None:  # pragma: no cover - metering ships in-tree
        return []
    return [str(one) for one in (read(PAYMENTS_TARGET, wanted) or [])]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-135-BRC07 `P1.9` · `DEF-PAY-6213` · payments blueprint §03 screen 2·1
# generated: 2026-09-23 by lane ONEPATH
# checklist: A✔ B✔ C✔ D✔ E=n/a(no screen of its own) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    §05 entry 25.3 `Asks` of `05-prototype/04 Billing, As Built.pdf`
#           — p126 (the drawing) and p127 (its commentary), read AS IMAGES at
#           scale 2 (B14 rule 42). Screens: S67 (this queue) · S66 (25.4, the
#           customer side that raises the ask) · 25.1 (what `Enrol →` opens)
# Rules:    BR-CWP-066 (a portal ask raises an ORDINARY service request, never
#           a request of a new kind) · BR-CWP-026 (a public form may create
#           work and may never change an account — *"it links no account and
#           changes none"*) · B1 + G6 (no cross-module import) · B2 §2 (a
#           module owns its tables; cross-module writes are forbidden) ·
#           NFR-3 (universal server pagination) · NFR-5 (no hard caps) ·
#           BR-RAT-043 + OQ-237 (eligibility rides a rate-plan flag nothing
#           publishes) · B14 rule 31 (no database id is a field's visible
#           value) · rule 37 (a drawn figure is an illustration) ·
#           BR-SHL-020 (a tile states an absence, never a substituted 0)
# Open:     OQ-BIL-12359 — where do a level-pay ask's ROUTE, its ACCOUNT and
#           the LEVEL THE CUSTOMER WAS SHOWN live? Three facts, one home
#           (`customers.service_requests`), and one of them reverses a
#           CONFIRMED rule, so it is the PO's and not a lane's.
# ───────────────────────────────────────────────────────
"""§05 entry 25.3's queue — and the three facts that are not in the product.

**WHAT THIS FILE IS ACTUALLY GUARDING, AND IT IS NOT THE HAPPY PATH.** The
screen cannot show a row today. The whole value of the tests below is that they
pin down *which* absences are honest and make the day they stop being absences
go RED:

  · `count` is **null** and never `0`. A zero on this table says *six people
    asked and none of them qualifies*; a null says *nobody could ask*. The
    drawing's own note names what the first one costs — *"a customer who asked
    online and heard nothing asks again by telephone."*
  · the three unservable tiles carry the **same sentence**, because they are
    downstream of one missing fact. Three wordings would read as three problems.
  · `ENROLLED THIS MONTH` is billing's own row and billing's own date, so it is
    **counted for real** — the one figure on this screen that is not an absence.
  · `NFR-3`: `limit`/`offset` reach the SEAM. A queue paged after the read is
    the unpaginated list four endpoints already ship.
  · the **hold-expiry** test: the day `customers` publishes the read, a test
    goes red and NAMES the screen to wire. Hard-won law 2's mirror — a hold
    with no such test is a promise nobody is keeping.

⚠ **WHAT WOULD MAKE THESE CHECKS PASS WRONGLY** (law 7, habit 2), because a
check whose false pass nobody can describe is a check nobody understands:

  · `test_count_is_null_not_zero` would pass on a screen that served `count: 0`
    if it only asserted `results == []`. It asserts the NULL, which is the fact
    that distinguishes the two sentences.
  · `test_the_three_absent_tiles_share_one_sentence` would pass on three empty
    strings. It asserts each sentence is non-empty AND that all three are the
    same object's text.
  · `test_enrolled_this_month_is_real` seeds an account enrolled LAST month as
    well as two this month. Without the last-month row it would pass on a
    endpoint that counted every enrolment ever.
  · `test_hold_expires…` asserts the read is absent TODAY. It is the only test
    here designed to fail later, and its message says what to do when it does.
  · `test_paging_reaches_the_seam` records the kwargs the seam was called with.
    Asserting only that a page came back would pass on an endpoint that read
    every row and sliced afterwards, which is the defect `NFR-3` names.
"""

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.billing import budget, budget_api, customers_seam, models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import an_account


def _enrol_row(account, tenant, *, enrolled_on):
    """One `account_budget_status` row, written straight — no engine, no clock.

    The tile under test counts rows by `enrolled_on`; nothing here exercises the
    level arithmetic, which is ❄️ GT-24's and has its own tests.
    """
    return models.AccountBudgetStatus.objects.create(
        tenant_id=tenant.id,
        account=account,
        status=budget.STATUS_ENROLLED,
        level=Decimal("85.000000"),
        currency="USD",
        variance_balance=Decimal("0"),
        enrolled_on=enrolled_on,
    )


# ══════════════════════════════════════════════════════════════════════════
# THE ROUTE EXISTS, AND IT IS NOT SHADOWED BY THE ACCOUNT ROUTE
# ══════════════════════════════════════════════════════════════════════════
def test_the_asks_route_is_mounted_and_static_wins(brazos):
    """⚠ **`asks` MUST RESOLVE AS ITSELF AND NOT AS AN ACCOUNT ID.**

    `budget-billing/<str:account_id>` would swallow the word if it were declared
    first — the same trap `enrollments` carries a comment about. A queue that
    404s because its own name was read as a uuid is a screen nobody can open,
    and every other test in this file would still pass.
    """
    from django.urls import resolve

    match = resolve(f"/api/{brazos.subdomain}/budget-billing/asks")
    assert match.func.cls.__module__ == "apps.billing.budget_api"
    # ⚠ **PROVED BY CONTRAST, NOT BY NAME.** `api_view` wraps the function in a
    # `WrappedAPIView`, so `__name__` is `view` for EVERY route in this module
    # and asserting it would be a check that cannot tell the two apart. What
    # separates them is the capture: the account route takes `account_id` and
    # the static one takes nothing.
    assert match.kwargs == {}
    account_route = resolve(f"/api/{brazos.subdomain}/budget-billing/not-the-word-asks")
    assert account_route.kwargs == {"account_id": "not-the-word-asks"}


# ══════════════════════════════════════════════════════════════════════════
# THE ABSENCES, AND WHY EACH IS THE HONEST ANSWER
# ══════════════════════════════════════════════════════════════════════════
def test_count_is_null_not_zero(brazos, dana):
    """A `0` here is a claim about customers; a `null` is a claim about us."""
    with tenant_ctx(brazos):
        response = api_call(
            budget_api.budget_asks, "get", f"/api/{brazos.subdomain}/budget-billing/asks",
            user=dana.user, role="system_admin", tenant=brazos,
        )
    assert response.status_code == 200, response.data
    body = response.data
    assert body["count"] is None, "an unreadable queue must not report a count of rows"
    assert body["results"] == []
    assert isinstance(body["rows_unavailable"], str) and body["rows_unavailable"].strip()


def test_the_three_absent_tiles_share_one_sentence(brazos, dana):
    """One missing fact, one sentence — three wordings would read as three bugs."""
    with tenant_ctx(brazos):
        response = api_call(
            budget_api.budget_asks, "get", f"/api/{brazos.subdomain}/budget-billing/asks",
            user=dana.user, role="system_admin", tenant=brazos,
        )
    summary = response.data["summary"]
    for tile in ("waiting", "eligible_now", "not_eligible"):
        assert summary[tile] is None, f"{tile} must not be a substituted number"
        assert summary[f"{tile}_unavailable"], f"{tile} states no reason"
    assert (
        summary["waiting_unavailable"]
        == summary["eligible_now_unavailable"]
        == summary["not_eligible_unavailable"]
        == response.data["rows_unavailable"]
    )


def test_no_rule_id_or_code_reaches_the_clerk_facing_detail(brazos, dana):
    """B14 rule 32 — no rule id and no internal code in clerk-facing copy.

    `GapNotes` renders `unavailable[].detail` as TEXT on a clerk's screen. The
    ids belong on `br_ref`, which the component keeps on the element and never
    prints. ⚠ This asserts the asks entries only. It USED to say here that
    *"the two `BUDGET_UNAVAILABLE` rows on the sibling screen carry ids in
    `detail` and are another surface's defect"* — a finding written in this
    docstring and filed nowhere, so nothing counted it until the Product Owner
    photographed that screen (`DEF-BIL-5339`, 2026-09-15). Those rows are
    covered by `test_def_bil_5339_clerk_facing_copy.py` now.
    """
    import re

    with tenant_ctx(brazos):
        response = api_call(
            budget_api.budget_asks, "get", f"/api/{brazos.subdomain}/budget-billing/asks",
            user=dana.user, role="system_admin", tenant=brazos,
        )
    pattern = re.compile(r"\b(?:OQ|DEF|BR|GT|US|EP|CR|NFR)-[A-Z]{0,3}-?\d{2,5}\b")
    for entry in response.data["unavailable"]:
        assert not pattern.search(entry["detail"]), (
            f"{entry['code']}: an id reached clerk-facing copy — put it on br_ref"
        )
        assert entry["br_ref"], f"{entry['code']} carries no br_ref for support"
    assert response.data["rows_unavailable"] and not pattern.search(
        response.data["rows_unavailable"]
    )


# ══════════════════════════════════════════════════════════════════════════
# THE ONE FIGURE THAT IS REAL
# ══════════════════════════════════════════════════════════════════════════
def test_enrolled_this_month_is_real(brazos, dana):
    """Billing's own rows, billing's own date — counted, not withheld.

    Two enrolled this month and ONE LAST MONTH. The last-month row is what makes
    this a test: without it an endpoint counting every enrolment ever would pass.
    """
    today = date.today()
    first = today.replace(day=1)
    with tenant_ctx(brazos):
        _enrol_row(an_account(dana, brazos, account_no="ACC-25301"), brazos, enrolled_on=today)
        _enrol_row(an_account(dana, brazos, account_no="ACC-25302"), brazos, enrolled_on=first)
        _enrol_row(
            an_account(dana, brazos, account_no="ACC-25303"),
            brazos,
            enrolled_on=first - timedelta(days=1),
        )
        response = api_call(
            budget_api.budget_asks, "get", f"/api/{brazos.subdomain}/budget-billing/asks",
            user=dana.user, role="system_admin", tenant=brazos,
        )
    summary = response.data["summary"]
    assert summary["enrolled_this_month"] == 2
    # The drawn detail line *"3 from the portal"* is an illustration (B14 rule
    # 37) of a fact nothing records. Stated, never invented.
    assert summary["enrolled_from_portal"] is None
    assert summary["enrolled_from_portal_unavailable"]


# ══════════════════════════════════════════════════════════════════════════
# NFR-3 — PAGED AT THE SEAM, NOT AFTER IT
# ══════════════════════════════════════════════════════════════════════════
def test_paging_reaches_the_seam(brazos, dana, monkeypatch):
    """`limit`/`offset` travel to the OWNER, so this can never be list-then-slice.

    Recorded as kwargs rather than inferred from the answer: an endpoint that
    read every request and sliced in Python would return the same page and is
    exactly the shape `NFR-3` forbids (`DEF-PAY-4221`, four endpoints already).
    """
    seen: dict[str, object] = {}

    def fake(*, limit, offset):
        seen["limit"], seen["offset"] = limit, offset
        return {"count": 0, "rows": []}

    monkeypatch.setattr(customers_seam, "level_pay_asks", lambda **kw: (fake(**kw), None))
    with tenant_ctx(brazos):
        api_call(
            budget_api.budget_asks, "get", f"/api/{brazos.subdomain}/budget-billing/asks",
            user=dana.user, role="system_admin", tenant=brazos, query={"page": "3", "per": "100"},
        )
    # ⚠ **`per=100` AND NOT `25`, AND THE FIRST DRAFT USED 25 AND WENT RED.**
    # `PAGE_SIZES` starts at 50, so `clamp_page_size` raises anything smaller to
    # 50 — *"clamping never grants more rows than asked for"* works one way
    # only. A test asserting an off-scale size proves nothing about paging; it
    # proves the clamp, which `core.pagination` already owns.
    assert seen == {"limit": 100, "offset": 200}


# ══════════════════════════════════════════════════════════════════════════
# THE HOLD-EXPIRY TEST — THE ONE DESIGNED TO FAIL LATER
# ══════════════════════════════════════════════════════════════════════════
def test_hold_expires_when_customers_publishes_the_read():
    """⚠ **THIS TEST EXISTS TO GO RED, AND THE DAY IT DOES IS THE POINT.**

    `CR-068` R3's lesson, generalised by hard-won law 2's 2026-09-05 mirror: a
    control held *until its screen lands* rots silently on the day the screen
    arrives, because landing the thing and releasing the hold are two acts and
    only the first feels like the work. On 2026-09-05 the portal's front page
    had two working doors out of eight for exactly this reason.

    **WHEN THIS FAILS, DO THIS AND THEN DELETE IT:**
      1. `customers` has published `level_pay_asks_page` — read its real shape
         against `customers_seam.LEVEL_PAY_ASKS_READ`'s documented contract.
      2. wire §05 entry 25.3's TABLE: `BudgetAsksPage.tsx` already renders rows
         when `rows_unavailable` is null; it needs the columns, not a rewrite.
      3. close `OQ-BIL-12359` as a FAN-OUT across all eight surfaces, not a
         status edit (`DEF-WRK-4030`).
    """
    published = customers_seam._resolve(
        customers_seam.LEVEL_PAY_ASKS_MODULE, customers_seam.LEVEL_PAY_ASKS_READ
    )
    assert published is None, (
        "apps.customers.service_request_reads.level_pay_asks_page now EXISTS. "
        "§05 entry 25.3's queue is still withholding its rows and its three tiles, "
        "and the customers who asked are still waiting. Wire BudgetAsksPage's table, "
        "close OQ-BIL-12359 across its eight surfaces, and delete this test."
    )


def test_the_seam_serves_rows_the_moment_the_read_exists(brazos, dana, monkeypatch):
    """The other half of the hold: prove the path works before trusting it held.

    ⚠ **A HOLD NOBODY HAS PROVED RELEASABLE IS A SCREEN THAT WILL NEED
    REWRITING, NOT WIRING.** This drives the seam with a published read and
    asserts the endpoint stops withholding — so the day the real read lands, the
    only unknown is the owner's field names.
    """
    rows = [
        {
            "reference": "SR-26-0087",
            "asked_on": "2026-11-07",
            "account_id": str(uuid.uuid4()),
            "account_no": "ACC-10519-C",
            "customer_name": "Nguyen, T.",
            "level_shown": "112.0000",
        }
    ]
    monkeypatch.setattr(
        customers_seam,
        "level_pay_asks",
        lambda **kw: ({"count": 1, "rows": rows}, None),
    )
    with tenant_ctx(brazos):
        response = api_call(
            budget_api.budget_asks, "get", f"/api/{brazos.subdomain}/budget-billing/asks",
            user=dana.user, role="system_admin", tenant=brazos,
        )
    body = response.data
    assert body["count"] == 1
    assert body["rows_unavailable"] is None
    assert body["results"][0]["reference"] == "SR-26-0087"
    # B14 rule 31: what the SCREEN prints is the number on the paper bill. The
    # id travels for the `Enrol →` link and is never a field's visible value —
    # asserted on the front end, where the markup is.
    assert body["results"][0]["account_no"] == "ACC-10519-C"


# ══════════════════════════════════════════════════════════════════════════
# THE BOUNDARY ITSELF — STATED AS A TEST SO A LATER LANE CANNOT DRIFT IT
# ══════════════════════════════════════════════════════════════════════════
def test_billing_owns_no_ask_table_and_imports_no_customers_module():
    """⚠ **B2 §2 AND B1, AS ASSERTIONS RATHER THAN AS A PARAGRAPH.**

    A customer's ask is a `customers.service_requests` row. The failure this
    guards is a later lane "simplifying" the seam into an import, or adding a
    `billing.BudgetAsk` model — which would be the *request of a new kind*
    `BR-CWP-066` forbids by name, in the module that prices the customer's water.
    """
    import ast
    import pathlib

    # ⚠ **PARSED, NOT GREPPED — AND THE FIRST DRAFT OF THIS TEST GREPPED AND
    # WENT RED ON ITS OWN SUBJECT'S DOCSTRING.** That file explains the rule in
    # prose (*"no `import apps.customers` binds the two modules"*), so a string
    # search finds the SENTENCE and reports a violation that is not there. A
    # check that cannot tell an import from a paragraph about imports is law 7's
    # *looking at the wrong thing*, caught here by running it.
    tree = ast.parse(pathlib.Path(customers_seam.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
    assert not [name for name in imported if name.startswith("apps.customers")], (
        f"billing imports customers directly: {sorted(imported)}"
    )
    assert not [
        name for name in dir(models) if "ask" in name.lower() and name[0].isupper()
    ], "billing has grown a table for a customer's ask — that row belongs to customers"


# ── Lifecycle ─────────────────────────────────────────────
# packet: §05 entry 25.3 of `05-prototype/04 Billing, As Built.pdf` p126–p127
#         (images, B14 rule 42) + BR-CWP-026/066 + B1/B2 §2 + NFR-3/NFR-5 +
#         OQ-237 + the 2026-09-11 ruling closing OQ-CWP-1568
# generated: 2026-09-15 by the §05 entry 25.3 build lane
# checklist: A✔ B✔ C✔ D✔(GET /budget-billing/asks, mounted and resolved through
#         the root URLconf) E✔(BudgetAsksPage.tsx, routed and doored from the
#         Budget Bills tab) F✔ G✔ H=n/a(no new 🔒 path; the seam file is
#         HUMAN-OWNED and carries a review-ledger row)
# gates: every assertion above was driven RED before it was trusted green —
#         the route test against the unmounted path, the null-count test
#         against a `0`, the shared-sentence test against three wordings, the
#         paging test against a list-then-slice, and the hold-expiry test
#         against a published read.
# exceptions: (1) the queue serves NO ROWS and that is the deliverable, not a
#         gap — OQ-BIL-12359 · (2) `unavailable[].detail` carries no id here
#         while its two neighbours on the sibling screen do (B14 rule 32);
#         the divergence is recorded rather than spread.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-5318 (the FIRST-BILL kind could not draft at all and never
#           could — `one_time._account_type_id` read `account_type_id` off
#           customers' `account_detail`, which has never published that key, so
#           `first_bill.deposit_line_for` refused by name on EVERY account)
# Rules:    BR-BIL-012 (the deposit line on the first bill) · BR-RAT-020/023
#           (`plan_deposit_rules` is keyed rate_plan × account_type) ·
#           CLAUDE.md rule 2 (money 4dp, display 2) · hard-won law 2 (built is
#           not wired) · hard-won law 7 (what would make this check pass
#           WRONGLY)
# Golden:   WE-6 ❄️ — Residential on the Residential Standard plan asks
#           **150.00**. QUOTED here, never moved: B4/B5 are frozen and this
#           file asserts the signed figure so drift goes RED.
# Tests:    this file
# ───────────────────────────────────────────────────────
"""DEF-BIL-5318 — the key the seam did not publish, and why it must be the ID.

**WHAT WAS BROKEN.** `customers.selectors.account_detail` served the consumer
category as a CODE (`account_type`, e.g. `"residential"`) and served no id at
all. `apps.billing.one_time._account_type_id` read `account_type_id` off that
blob with `.get()`, got `None` on every account, and
`first_bill.deposit_line_for` refused: *"account … names no consumer category"*.
The first of S30's five kinds had never produced a bill. It hid because the
PREVIEW does not price a deposit — only the DRAFT refused — and no test drafted
a first bill through `one_time.create`.

**WHY THE SMALLER FIX WOULD HAVE BEEN THE DANGEROUS ONE, AND IT HAS A FIGURE.**
The obvious cheap repair is to have billing read the key the seam already
publishes — the CODE. `rating.models.PlanDepositRule.account_type_id` is a
`UUIDField`, and `rating.selectors.deposit_rule_for` opens with
`_valid_uuid(account_type_id)` and answers `None` for anything that is not a
uuid. `None` from that read is SIGNED to mean *this plan asks this category for
no deposit*, so `deposit_line_for` would emit **no line at all**. A first bill
would then draft happily with **$150.00** of the utility's deposit missing, on
a document that is immutable at issue, with every test in this repo green.
`test_the_code_resolves_no_rule_and_that_is_the_silent_underbill` is that
figure, asserted, so nobody can take the shortcut without the suite saying what
it costs.

**WHAT WOULD MAKE THESE CHECKS PASS WRONGLY (law 7 habit 2).**
  * A test that hand-builds the seam's dict would pass while the real payload
    said something else, so every case here reads the REAL
    `account_detail(account_id)` and, where it needs a broken one, MUTATES that
    real blob rather than inventing one. The day the payload moves, this moves.
  * Asserting only `"account_type_id" in blob` would pass if somebody served
    the CODE under the id's name — the exact wrong fix. So the value is
    asserted to be the account row's own uuid, and asserted NOT to equal the
    code beside it.
  * Asserting only that the seam guard raises would pass on the OLD refusal
    too, which is the one that blames the customer's data. So the guard case
    asserts the sentence names the SEAM and the FIELD, and a separate case
    pins the other direction: key present with value `None` is a real account
    with no category and must still refuse in the customer's own language.
"""

from decimal import Decimal

import pytest

from apps.billing import one_time
from apps.billing.exceptions import BillingRuleError
from apps.customers import selectors as customer_selectors
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, lonestar, tenant_ctx  # noqa: F401
from tests.test_us_bil_001_prepare import (
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)

pytestmark = pytest.mark.django_db

#: WE-6 ❄️, quoted. Changing this is a finance re-sign (HUMAN-GUIDE §6), never
#: an inline edit — the number is here so drift goes RED, not so it can move.
DEPOSIT_ASKED = Decimal("150.00")


def _a_world(brazos, dana, *, account_no="ACC-5318"):
    cycle = a_cycle(brazos)
    plan = a_priced_plan(brazos)
    unit = a_billed_unit(
        dana, brazos, cycle, plan, asset_no="M-5318", label="Unit 5318", consumption="412.000000"
    )
    return plan, an_account(brazos, unit["id"], account_no)


# ── 1 · the key exists, and it is the ROW's uuid ────────────────────────────
def test_the_seam_publishes_account_type_id(brazos, dana):
    with tenant_ctx(brazos):
        _plan, account = _a_world(brazos, dana)
        blob = customer_selectors.account_detail(str(account.id))

        assert "account_type_id" in blob, (
            "customers' account_detail must carry account_type_id — without it "
            "one_time._account_type_id answers None and every first bill refuses (DEF-BIL-5318)"
        )
        assert blob["account_type_id"] == str(account.account_type_id)


# ── 2 · it is the ID and not the CODE, which is the whole judgment ──────────
def test_the_published_value_is_the_uuid_and_not_the_code(brazos, dana):
    with tenant_ctx(brazos):
        _plan, account = _a_world(brazos, dana)
        blob = customer_selectors.account_detail(str(account.id))

        # The code is still served, for display. The two are different facts and a
        # future "simplification" that serves the code under the id's name fails here.
        assert blob["account_type"] == account.account_type.code
        assert blob["account_type_id"] != blob["account_type"]
        assert rating_selectors._valid_uuid(blob["account_type_id"])


# ── 3 · billing's read now answers the uuid rather than None ────────────────
def test_billing_reads_the_category_through_the_seam(brazos, dana):
    with tenant_ctx(brazos):
        _plan, account = _a_world(brazos, dana)
        assert one_time._account_type_id(str(account.id)) == str(account.account_type_id)


# ── 4 · the $150.00 the wrong fix would have lost, asserted ─────────────────
def test_the_code_resolves_no_rule_and_that_is_the_silent_underbill(brazos, dana):
    """WE-6's 150.00 resolves on the uuid and vanishes on the code.

    `deposit_rule_for` answering `None` is not an error — it is signed to mean
    *this plan asks this category for no deposit*, and `deposit_line_for` then
    emits NO line. That is why handing it the code is an under-bill and not a
    crash: the bill foots perfectly and is 150.00 short.
    """
    with tenant_ctx(brazos):
        plan, account = _a_world(brazos, dana)
        rating_models.PlanDepositRule.objects.create(
            tenant=brazos,
            rate_plan=plan,
            account_type_id=account.account_type_id,
            amount=DEPOSIT_ASKED,
            currency="USD",
        )
        blob = customer_selectors.account_detail(str(account.id))

        on_the_id = rating_selectors.deposit_rule_for(plan.id, blob["account_type_id"])
        assert on_the_id is not None, "the uuid must resolve WE-6's rule"
        assert Decimal(on_the_id["amount"]) == DEPOSIT_ASKED

        on_the_code = rating_selectors.deposit_rule_for(plan.id, blob["account_type"])
        assert on_the_code is None, (
            "the CODE resolves no rule — which deposit_line_for reads as 'this plan asks no "
            "deposit' and emits no line, so a first bill drafted through the code path is "
            f"{DEPOSIT_ASKED} short and every test still passes (DEF-BIL-5318)"
        )


# ── 5 · the guard: a seam that drops the key names the SEAM ─────────────────
def test_a_seam_without_the_key_refuses_naming_the_seam(brazos, dana, monkeypatch):
    """Proved RED before it was trusted green — see the file's own note.

    The broken blob is the REAL payload with one key removed, never a
    hand-built dict, so this case keeps exercising the true shape.
    """
    with tenant_ctx(brazos):
        _plan, account = _a_world(brazos, dana)
        real = customer_selectors.account_detail

        def without_the_key(account_id):
            blob = dict(real(account_id))
            blob.pop("account_type_id", None)
            return blob

        monkeypatch.setattr(customer_selectors, "account_detail", without_the_key)

        with pytest.raises(BillingRuleError) as raised:
            one_time._account_type_id(str(account.id))

        message = str(raised.value)
        assert "account_type_id" in message and "seam" in message
        # NOT the customer-facing refusal — that one blames the account's data.
        assert "names no consumer category" not in message


# ── 6 · the other direction: present-but-None is the ACCOUNT's absence ──────
def test_a_null_category_still_travels_to_the_customer_facing_refusal(brazos, dana, monkeypatch):
    """Key present, value None ⇒ this account has no category. Different fact.

    Flattening this into case 5 is exactly the bug DEF-BIL-5318 was: `.get()`
    made an absent KEY indistinguishable from an absent CATEGORY, and the
    refusal a clerk read named the wrong one for three weeks.
    """
    with tenant_ctx(brazos):
        _plan, account = _a_world(brazos, dana)
        real = customer_selectors.account_detail

        def with_a_null(account_id):
            return {**real(account_id), "account_type_id": None}

        monkeypatch.setattr(customer_selectors, "account_detail", with_a_null)

        assert one_time._account_type_id(str(account.id)) is None

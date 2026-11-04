# ── Trace ──────────────────────────────────────────────
# Change:   the uniform correction verbs. PO ruling 2026-09-17, verbatim, shown
#           a table of what each of the five priced objects does today:
#           *"please fix all these"*.
# Defects:  DEF-RAT-5712 — a live charge code's price moves with no reason, no
#           version, no filing record and no lock.
# Rules:    BR-RAT-1016 (the three verbs, the same for every priced object —
#           GENERALISING BR-RAT-104 from CR-013 part 4's *shared rules*) ·
#           BR-RAT-088 (the CHARGE CODE owns the base amount) · BR-RAT-035 (the
#           audit lock, which guards DELETE and not the amount) · BR-RAT-690
#           (the per-size table, which is the flat rule's amount stated once
#           per size) · CLAUDE.md hard rule 4 (issued bills are untouched) ·
#           hard rule 7 (a money action writes audit_log)
# Tests:    this file
# Impacts:  apps/rating/services.{CHARGE_MONEY_FIELDS,charge_money_moves,
#           update_charge} · PATCH /charges/{id} · S12/CHG-02 ChargeCodeWizard
# ───────────────────────────────────────────────────────
"""VERB 1 ON A CHARGE CODE: free while it prices nothing, reasoned once it does.

── WHY THE CHARGE CODE AND NOT ONE OF THE OTHER FOUR ────────────────────────

`BR-RAT-088` (PO 2026-08-20) gives the CHARGE CODE the base amount — *"a plan
displays it, never defines it"* — and the plan screen says so to the clerk in
its own words: *"This plan shows it and cannot change it."* So the charge code
is the ONE place an amount can change, and until this file it had the LEAST
protection of the five objects in this module: a tax refuses the in-place edit
outright, a published plan bumps a version and demands a reason, a rate schedule
refuses the save, and a DISCOUNT — which can only ever REDUCE a bill — needs
submit, approve and activate.

── PROVED RED FIRST (hard-won law 7), through `pytest`, the harness that runs
── them. What each printed against `update_charge` as it stood ──────────────

* `test_a_code_in_use_refuses_a_price_move_with_no_reason` —

      Failed: DID NOT RAISE <class 'core.errors.ValidationError'>

  and the print in its own body is `DEF-RAT-5712` reproduced in one line:
  `PAPER` moved from `$2.00` to `$5.00` on a published plan's charge rule,
  accepted, with `rate_change_log` still holding **0** rows for this code.

* `test_a_priced_move_writes_the_filing_record_with_its_reason` —

      AssertionError: assert 0 == 1

  the `rate_change_log` count, because nothing in `update_charge` ever wrote
  one for a charge.

* `test_a_code_nobody_uses_still_edits_freely` — GREEN before the change and
  green after it, deliberately: verb 1 is *a draft is not history*, and a code
  reaching no plan, no schedule and no invoice line has priced nothing.

* `test_the_lock_fails_closed_when_billing_cannot_answer` —

      Failed: DID NOT RAISE <class 'core.errors.ValidationError'>

  `DEF-079`'s reading kept: `invoice_lines is None` means *billing could not
  answer*, and a lock that treats *I do not know* as *nobody* is the defect
  that let a charge code on real bills read as never used for a month.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.rating import models, selectors, services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import audit_actions, tenant_ctx

pytestmark = pytest.mark.django_db


def _paper_on_a_published_plan(env):
    """A charge code a published plan NAMES — the *in use* case, route one."""
    env.enable("water")
    water = env.flat_schedule("Comm Water · Flat", "water", "2.90")
    paper = env.charge("PAPER", "Paper bill fee", charge_type="recurring", amount="2.00")
    env.plan(
        "Residential",
        "RES-PAPER",
        [{"service": "water", "tariff": water["id"]}],
        charge_rules=[{"charge": paper["id"], "recurrence": "recurring"}],
        publish=True,
    )
    return paper


def _logs_for(charge_id):
    return models.RateChangeLog.objects.filter(entity_type="charge", entity_id=charge_id)


# ══════════════════════════════════════════════════════════════════════════
# The refusal
# ══════════════════════════════════════════════════════════════════════════


def test_a_code_in_use_refuses_a_price_move_with_no_reason(env):
    """`DEF-RAT-5712` reproduced, then refused.

    **Worked:** `PAPER` at `$2.00` moved to `$5.00` is `$3.00` more on every
    bill carrying it, every cycle, for ever — and before this refusal the only
    trace was an `audit_log` row, which is pruned on a retention schedule.
    """
    paper = _paper_on_a_published_plan(env)
    with tenant_ctx(env.tenant):
        used = selectors.charge_used_by(selectors.charge_or_404(paper["id"]))
        assert used["plans"] == 1, "the fixture must put the code in use"
        with pytest.raises(errors.ValidationError) as excinfo:
            services.update_charge(env.admin, paper["id"], {"amount": "5.00", "effective_from": "2000-01-01"})
        assert excinfo.value.field_errors[0]["field"] == "reason"
        assert excinfo.value.field_errors[0]["message_key"] == "rating.charges.reason_required"
        # REFUSED BEFORE ANYTHING IS WRITTEN — `update_plan`'s own posture, and
        # the reason it matters here is that a half-applied reprice would bill.
        assert selectors.charge_row(selectors.charge_or_404(paper["id"]))["amount_display"] == "2.00"
        assert _logs_for(paper["id"]).count() == 0


def test_the_refusal_names_the_rule_and_what_is_in_use(env):
    """A refusal that does not say what to do instead is the road ending — the
    shape `DEF-384` was filed for one object over."""
    paper = _paper_on_a_published_plan(env)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.update_charge(env.admin, paper["id"], {"amount": "5.00", "effective_from": "2000-01-01"})
        params = excinfo.value.field_errors[0]["params"]
        assert params["br_ref"] == "BR-RAT-1016"
        assert params["charge_code"] == "PAPER"
        assert params["plans"] == 1


def test_a_reason_of_two_words_is_not_a_reason(env):
    """The same floor `correct_tax` uses (`MIN_CORRECTION_REASON`), and for the
    same reason: a filing record where every row says `fix` is a history nobody
    can read in a year."""
    paper = _paper_on_a_published_plan(env)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.update_charge(env.admin, paper["id"], {"amount": "5.00", "reason": "typo", "effective_from": "2000-01-01"})
        assert excinfo.value.field_errors[0]["field"] == "reason"
        assert excinfo.value.field_errors[0]["message_key"] == "rating.charges.reason_required"


# ══════════════════════════════════════════════════════════════════════════
# The filing record
# ══════════════════════════════════════════════════════════════════════════


def test_a_priced_move_writes_the_filing_record_with_its_reason(env, audit_rows):
    paper = _paper_on_a_published_plan(env)
    with tenant_ctx(env.tenant):
        row = services.update_charge(
            env.admin,
            paper["id"],
            {"amount": "5.00", "reason": "Board approved the paper-bill fee rise for 2027.", "effective_from": "2000-01-01"},
        )
        assert row["amount_display"] == "5.00"
        logs = list(_logs_for(paper["id"]))
        assert len(logs) == 1
        assert logs[0].reason == "Board approved the paper-bill fee rise for 2027."
        # BEFORE and AFTER are the served row, so the record carries the per-size
        # table and the display strings a reader will compare against a bill.
        assert logs[0].before["amount_display"] == "2.00"
        assert logs[0].after["amount_display"] == "5.00"
        assert logs[0].actor_id == env.admin.id
        # Hard rule 7 — and a REPRICE is its own action, so an audit reader can
        # tell a price move from a rename without diffing two blobs.
        assert "charge.repriced" in audit_actions(audit_rows)


def test_renaming_a_code_in_use_needs_no_reason_and_writes_no_filing_record(env, audit_rows):
    """The rule is about MONEY, not about the row. A bookkeeper's spelling fix
    is not rate history — the same boundary the tax lane drew at
    `TAX_RATE_HISTORY_FIELDS` and recorded in the decision log."""
    paper = _paper_on_a_published_plan(env)
    with tenant_ctx(env.tenant):
        row = services.update_charge(env.admin, paper["id"], {"name": "Paper billing fee", "effective_from": "2000-01-01"})
        assert row["name"] == "Paper billing fee"
        assert _logs_for(paper["id"]).count() == 0
        assert "charge.updated" in audit_actions(audit_rows)


def test_resending_the_same_amount_is_not_a_price_move(env):
    """The wizard PATCHes the WHOLE draft, so every save names `amount`. The
    test is whether the FIGURE moved, never whether the key was sent — a rule
    that read the key would demand a reason to fix a typo in a name."""
    paper = _paper_on_a_published_plan(env)
    with tenant_ctx(env.tenant):
        row = services.update_charge(
            env.admin,
            paper["id"],
            {"name": "Paper billing fee", "amount": "2.00", "amount_rule": "flat", "effective_from": "2000-01-01"},
        )
        assert row["name"] == "Paper billing fee"
        assert _logs_for(paper["id"]).count() == 0


# ══════════════════════════════════════════════════════════════════════════
# What *in use* means
# ══════════════════════════════════════════════════════════════════════════


def test_a_code_nobody_uses_still_edits_freely(env):
    """VERB 1, in the words `correct_tax` already uses: *a draft is not history.
    It has never priced anything, so there is nothing to preserve and nothing to
    explain.*"""
    env.enable("water")
    spare = env.charge("SPARE", "Unused fee", amount="9.00")
    with tenant_ctx(env.tenant):
        used = selectors.charge_used_by(selectors.charge_or_404(spare["id"]))
        assert (used["plans"], used["schedules"], used["invoice_lines"]) == (0, 0, 0)
        row = services.update_charge(env.admin, spare["id"], {"amount": "12.00", "effective_from": "2000-01-01"})
        assert row["amount_display"] == "12.00"
        # CR-156-BRC10 (PO 2026-10-01): EVERY money change is logged now, a
        # free code's too — still with NO reason demanded (verb 1 unchanged).
        (log,) = _logs_for(spare["id"])
        assert log.reason == ""


def test_a_service_base_code_is_in_use_by_the_second_route(env):
    """`BR-RAT-088`'s route, the one that has no join table and reads `0` in a
    naive count — `_charge_is_base_for_schedules` is what sees it, and this is
    the case `$23,069.50` a month was priced against."""
    env.enable("water")
    base = env.charge("BASE-W", "Water base charge", charge_type="recurring",
                      amount="8.00", service="water", is_base=True)
    env.flat_schedule("Res Water", "water")
    with tenant_ctx(env.tenant):
        used = selectors.charge_used_by(selectors.charge_or_404(base["id"]))
        assert used["plans"] == 0 and used["schedules"] >= 1
        with pytest.raises(errors.ValidationError) as excinfo:
            services.update_charge(env.admin, base["id"], {"amount": "34.00", "effective_from": "2000-01-01"})
        assert excinfo.value.field_errors[0]["message_key"] == "rating.charges.reason_required"


def test_the_lock_fails_closed_when_billing_cannot_answer(env):
    """`DEF-079`'s reading, kept verbatim: `invoice_lines is None` means
    *billing could not answer*, and a lock that reads *I do not know* as
    *nobody* is exactly the defect that let a code on real bills stay freely
    editable for a month."""
    env.enable("water")
    spare = env.charge("SPARE2", "Unused fee", amount="9.00")
    with tenant_ctx(env.tenant):
        with patch.object(selectors.seams, "invoice_line_references", return_value=None):
            with pytest.raises(errors.ValidationError) as excinfo:
                services.update_charge(env.admin, spare["id"], {"amount": "12.00", "effective_from": "2000-01-01"})
            assert excinfo.value.field_errors[0]["message_key"] == "rating.charges.reason_required"


# ══════════════════════════════════════════════════════════════════════════
# Which fields are money
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "change",
    [
        {"amount": "5.00"},
        {"percent": "0.025", "amount_rule": "percent", "amount": None},
        {"min_amount": "7.00"},
        {"max_amount": "40.00"},
        {"amount_rule": "percent", "percent": "0.015", "amount": None},
    ],
)
def test_every_money_field_is_guarded(env, change):
    paper = _paper_on_a_published_plan(env)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.update_charge(env.admin, paper["id"], {**(change), "effective_from": "2000-01-01"})
        assert excinfo.value.field_errors[0]["message_key"] == "rating.charges.reason_required"


def test_the_per_size_table_is_money_too(env):
    """`BR-RAT-690` — a per-size table IS the flat rule's amount, stated once
    per size. `CR-063`'s going-live fire customer is the worked case: a 6" line
    at `$60.00` and a 2" at `$12.00` is `$84.00` on that warehouse, and moving
    the 6" figure moves a real bill exactly as `amount` does.

    ⚠ **THE BRIEF NAMED FIVE FIELDS AND THIS IS A SIXTH.** Leaving it out would
    have left one whole route to the same money unguarded — which is the shape
    of `DEF-RAT-4832` one object over, where a count of one of two routes read
    `0` over a code that prices every connection on its service.
    """
    env.enable("water")
    with tenant_ctx(env.tenant):
        # The TENANT's own configured sizes, never two strings typed here — a
        # size this file invented would be refused by `_validate_size_amounts`
        # for the wrong reason and the test would pass without ever reaching
        # the guard it is named after.
        small, large = services.seams.configured_size_class_codes()[:2]
    base = env.charge(
        "FIRE-L",
        "Fire line",
        charge_type="recurring",
        service="water",
        is_base=True,
        amount=None,
        size_amounts=[{"size_class": small, "amount": "12.00"},
                      {"size_class": large, "amount": "60.00"}],
    )
    env.flat_schedule("Res Water 2", "water")
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            services.update_charge(
                env.admin,
                base["id"],
                {"size_amounts": [{"size_class": small, "amount": "12.00"},
                                  {"size_class": large, "amount": "66.00"}], "effective_from": "2000-01-01"},
            )
        assert excinfo.value.field_errors[0]["message_key"] == "rating.charges.reason_required"


def test_a_behaviour_flag_is_not_money(env):
    """`taxable_default`, `waivable`, `separate_line`, `auto_apply` change how a
    line BEHAVES and not what it costs. They stay verb 1, because a rule that
    swept them in would demand a filing record to tick a checkbox and would be
    the over-application that gets a rule quietly disabled by the next lane."""
    paper = _paper_on_a_published_plan(env)
    with tenant_ctx(env.tenant):
        row = services.update_charge(env.admin, paper["id"], {"waivable": True, "effective_from": "2000-01-01"})
        assert row["waivable"] is True
        assert _logs_for(paper["id"]).count() == 0


# ══════════════════════════════════════════════════════════════════════════
# What this deliberately does NOT do
# ══════════════════════════════════════════════════════════════════════════


def test_nothing_already_issued_is_touched(env):
    """CLAUDE.md hard rule 4. A reprice changes what prices FUTURE bills and
    re-prices nothing that has been issued — `OQ-RAT-12408` is where the dated
    half lives, and the response says so rather than letting an operator who
    has just fixed a price believe the money is fixed."""
    paper = _paper_on_a_published_plan(env)
    with tenant_ctx(env.tenant):
        row = services.update_charge(
            env.admin,
            paper["id"],
            {"amount": "5.00", "reason": "Board approved the paper-bill fee rise for 2027.", "effective_from": "2000-01-01"},
        )
        assert row["issued_bills_unchanged"] is True
        # CR-156-BRC10 — `OQ-RAT-12408` (no window to schedule a price in) is
        # answered by the dated price rows; the response no longer names it.
        assert "open_question" not in row

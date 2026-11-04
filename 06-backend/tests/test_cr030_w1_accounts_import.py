# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-019/020/021/022/023 (EP-CUS-07 account onboarding)
#           Screens: S68 (the wizard on the ONE runner) · S81 (the Imports tab)
# Change:   CR-030 W1 — accounts, the sixth ETL target
# Rules:    BR-MET-096 (one runner, target parameterised) · BR-CUS-047
#           (migration order — a missing unit ERRORS) · BR-CUS-048 (four aged
#           buckets) · BR-CUS-049 (balanced opening JEs at cutover) ·
#           BR-CUS-017 (one live account per unit) · CLAUDE.md rules 1/4/5/6/7
# Golden:   GT-16 ❄️ FROZEN
# ───────────────────────────────────────────────────────
"""CR-030 W1 — a utility's account base, end to end, through the ONE runner.

The stages are not re-tested here: CR-023 and CR-028 own them, and BR-MET-096's
whole point is that *"a kind is copy and a route, never behaviour"*. What is
tested is what ACCOUNTS adds — the unit binding the PO asked for, the four aged
buckets, the ledger handoff, and the two refusals that protect money.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.customers import models as customers_models
from apps.metering import import_runs, models as metering_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_us_cus_003_account_write import _plan  # noqa: E402

pytestmark = pytest.mark.django_db

CUTOVER = "2026-08-31"
ALL_OFF = {key: False for key in import_runs.ROW_HANDLING_KEYS}

#: GT-16's own row, and one with no opening position at all (US-CUS-021 TC-5's
#: A-12140). Header names are deliberately the CUSTOMER'S, not ours — the point
#: of the mapping step DEF-611 says was never built.
#: ⛔ **THE TWO IDENTITY CELLS ARE NOT DECORATION — `BR-CUS-1041`, PO ruling
#: 2026-09-01.** Since `CR-058` W7 a row carrying a name and no identifier
#: creates NOTHING, so this fixture would load zero accounts and every figure
#: below would be measuring an empty run. `CUST_ID` is the LEGACY key and is
#: explicitly not an identifier (it names a row in somebody else's database), so
#: the kind and one government identifier are what make these rows loadable.
#: The two accounts, the two numbers and every money figure are unchanged.
CSV = (
    "UNIT_REF,ACCT,NAME,CUST_ID,KIND,SSN,TYPE,OPENED,CURRENT,31-60,61-90,90+,DEPOSIT,DEPOSIT_DATE\n"
    '{u1},A-12103,"Harmon, Luis",CUST-118,person,123-45-6789,residential,2024-02-12,84.20,62.10,0.00,121.00,150.00,2024-02-12\n'
    '{u2},A-12140,"Alvarez, Rosa",CUST-119,person,987-65-4321,residential,2025-06-01,,,,,,\n'
)

MAPPING = {
    "UNIT_REF": "unit_ref",
    "ACCT": "account_no",
    "NAME": "customer_name",
    "CUST_ID": "customer_ref",
    # CR-058 W7 · BR-CUS-1041 — see the note above the fixture.
    "KIND": "customer_kind",
    "SSN": "customer_ssn",
    "TYPE": "account_type",
    "OPENED": "opened_at",
    "CURRENT": "ob_current",
    "31-60": "ob_31_60",
    "61-90": "ob_61_90",
    "90+": "ob_90_plus",
    "DEPOSIT": "deposit_on_file",
    "DEPOSIT_DATE": "deposit_received_on",
}


def _two_units(actor, tenant):
    premises = make_premises(actor, services_available=["electric"])
    units = []
    for label in ("W1 Unit A", "W1 Unit B"):
        unit = make_unit(actor, premises["id"], label=label)
        from apps.metering import services as metering_services

        metering_services.assign_unit_plan(
            actor, unit["id"], {"tariff_id": str(_plan(tenant, service_code="electric").id)}
        )
        metering_services.ensure_service_point(unit["id"], "electric")
        units.append(unit)
    return units


def _csv_for(units):
    return CSV.format(u1=units[0]["unit_no"], u2=units[1]["unit_no"])


def _run(actor, content, *, options=None, mapping=None):
    run = import_runs.extract(
        actor,
        {
            "target": import_runs.TARGET_ACCOUNTS,
            "source_kind": "file",
            "file_name": "customer_accounts_migration.csv",
            "content": content,
            "session_ref": "sess_cr030",
        },
    )
    payload = {"mapping": mapping or MAPPING, "row_handling": ALL_OFF}
    if options is not None:
        payload["options"] = options
    import_runs.transform(actor, run["id"], payload)
    import_runs.validate(actor, run["id"])
    return run["id"]


def test_w1_e2e__accounts_is_a_target_on_the_one_runner():
    """BR-MET-096 — `kinds.ts` promised since CR-023 that *"the kinds are DATA
    so the tenth one costs an object"*. SEVEN now travel the same five stages:
    `parts` joined on 2026-09-07 (`CR-077`).

    ⚠ **THE COUNT IS ASSERTED AND THE NAME NO LONGER CARRIES IT.** The literal
    is kept — a target arriving unnoticed is exactly what this line is for —
    but the function was called `…_is_the_sixth_target…` and a case named after
    a number goes stale the first time the number moves, which is CLAUDE.md's
    pointer-rot shape with a test attached."""
    assert import_runs.TARGET_ACCOUNTS in import_runs.TARGETS
    # `DEF-MET-9260` — EIGHT since the lockbox payments target (`c8bce7c8a`,
    # 2026-09-22); this literal was not moved with it.
    assert len(import_runs.TARGETS) == 8
    assert import_runs.EXPLICIT_COLUMNS_BY_TARGET[import_runs.TARGET_ACCOUNTS]


def test_w1_e2e__every_target_has_a_rules_catalogue():
    """⚠ **THE GUARD DEF-614 EARNED.** `import_rules.rules_for` reads
    `PLATFORM_CATALOG.get(target, ())`, so a target with no entry gets NO rules
    — and stage 2's parse refusals are then carried on the row and never read.

    That is not a theoretical hole. It let a NEGATIVE opening balance through as
    a clean row with the value silently dropped to NULL: the account loaded, its
    buckets were short, `accounts.balance` was wrong by the missing amount, and
    every count on the receipt said the run was perfect.

    CR-023 and CR-028 both added a target and its catalogue in one commit, so
    the default never fired across five targets. The sixth found it. This is the
    two-line assertion that fails the moment a seventh is registered without
    its rules."""
    from apps.metering import import_rules

    assert set(import_runs.TARGETS) == set(import_rules.PLATFORM_CATALOG)


def test_w1_e2e__a_migration_lands_accounts_buckets_and_a_balanced_entry(brazos, marcus):
    """The whole point of the wave, in one case.

    Two rows: GT-16's `A-12103` with a full opening position, and `A-12140` with
    none. Both become accounts; only one gets buckets and only one reaches the
    ledger — a zero journal entry says nothing and can never be corrected away
    (hard rule 4).
    """
    with tenant_ctx(brazos):
        units = _two_units(marcus, brazos)
        run_id = _run(marcus, _csv_for(units), options={"cutover_on": CUTOVER})
        receipt = import_runs.load(marcus, run_id, {"write_mode": "insert", "approved": True})

        assert receipt["counts"]["created"] == 2
        assert receipt["counts"]["with_opening_balance"] == 1

        harmon = customers_models.Account.objects.get(tenant_id=brazos.id, account_no="A-12103")
        rosa = customers_models.Account.objects.get(tenant_id=brazos.id, account_no="A-12140")

        # ❄️ GT-16: Σ buckets, exact — no recompute.
        buckets = customers_models.AccountOpeningBucket.objects.filter(account=harmon)
        assert buckets.count() == 4
        assert sum((b.amount for b in buckets), Decimal("0")) == Decimal("267.30")
        assert harmon.balance == Decimal("267.30")
        assert {b.as_of for b in buckets} == {date(2026, 8, 31)}

        # US-CUS-021 TC-5 — no position, no rows, no entry, balance untouched.
        assert not customers_models.AccountOpeningBucket.objects.filter(account=rosa).exists()

        # The account numbers the utility already quotes are KEPT (BR-CUS-046).
        assert {harmon.account_no, rosa.account_no} == {"A-12103", "A-12140"}

        # BR-CUS-054 — the legacy ref links a customer, and CR-030 W0 numbers it.
        link = customers_models.CustomerAccount.objects.get(account=harmon)
        assert link.customer.external_ref == "CUST-118"
        assert link.customer.customer_no


def test_w1_e2e__the_opening_entry_ties_out_and_the_ledger_wrote_it(brazos, marcus):
    """US-CUS-022 — customers asks, the LEDGER writes (hard rule 5), and the
    batch refuses to report success unless Σ AR debits = Σ clearing credits."""
    with tenant_ctx(brazos):
        units = _two_units(marcus, brazos)
        run_id = _run(marcus, _csv_for(units), options={"cutover_on": CUTOVER})
        receipt = import_runs.load(marcus, run_id, {"write_mode": "insert", "approved": True})
        assert Decimal(receipt["counts"]["opening_ar"]) == Decimal("267.30")


def test_w1_e2e__no_changeover_date_HOLDS_the_books_and_still_loads(brazos, marcus):
    """⛔⛔ **AMENDED 2026-08-27 — THIS TEST ASSERTED A REFUSAL AND THE PO
    REMOVED IT.** It read *"no cutover date REFUSES before a single account is
    written"*, and the reasoning it carried is still true and still enforced —
    it has simply moved from *"refuse the run"* to *"hold the books"*.

    PO verbatim, on meeting the field: *"in account upload - 2.2 Has a cutover
    date been given for this run? what is this ?"* — the Product Owner of this
    product could not tell what it was for, on a screen that **blocked an entire
    migration**. So the accounts load and only the money waits.

    **What is still protected, and by what:** `BR-TEN-043` still forbids reading
    a clock on the caller's behalf for a business event's date, and no journal
    entry is written under a date nobody chose. **The books are HELD** — the
    ledger is not called at all — because hard rule 4 makes a posted entry
    permanent, and a held batch is the only state in which the PO's own *"we can
    always change this date later"* is a true sentence.

    **The provisional date is today − 90 days, and the direction is the
    decision:** a FUTURE date would leave every opening balance not yet due —
    nothing overdue, no ageing, no reminder ever firing — wrong in the utility's
    favour, which is the direction nobody checks.
    """
    with tenant_ctx(brazos):
        units = _two_units(marcus, brazos)
        run_id = _run(marcus, _csv_for(units))  # no options — no changeover date
        receipt = import_runs.load(marcus, run_id, {"write_mode": "insert", "approved": True})

        # The migration is NOT blocked: both accounts are on file.
        assert receipt["counts"]["created"] == 2
        assert customers_models.Account.objects.filter(
            tenant_id=brazos.id, account_no="A-12103"
        ).exists()

        # …and the books are HELD, said as a number so a 90%-done migration
        # cannot look identical to a finished one.
        assert receipt["receipt"]["opening_held"] == 1, receipt["receipt"]
        assert receipt["receipt"]["changeover_on"] is None
        provisional = date.fromisoformat(receipt["receipt"]["changeover_provisional"])
        assert provisional < date.today(), "a future changeover date is never overdue"

        # ⚠ **NOTHING IS POSTED.** The whole point: no journal entry exists, so
        # the date is still changeable.
        assert Decimal(receipt["counts"]["opening_ar"] or "0") == Decimal("0")


def test_w1_e2e__confirming_the_changeover_date_re_dates_and_posts_once(brazos, marcus):
    """The other half of the ruling: the operator supplies the real date and
    the held batch posts, under THAT date, ONCE.

    ⚠ **RE-DATING A HELD BUCKET IS LAWFUL AND RE-DATING A POSTED ONE IS NOT.**
    `AccountOpeningBucket` is append-only *"because the moment US-CUS-022 posts,
    an immutable journal entry exists against these numbers"* — and while the
    batch is held, no such entry exists. That is the entire design.
    """
    with tenant_ctx(brazos):
        units = _two_units(marcus, brazos)
        run_id = _run(marcus, _csv_for(units))
        import_runs.load(marcus, run_id, {"write_mode": "insert", "approved": True})

        # ⚠ **NOT `CUTOVER`, AND THE REASON IS A REAL FINDING.** GT-16's frozen
        # worked case is dated **2026-08-31** while this repo's own "today" is
        # 2026-08-27 — so the ❄️ signed cutover is FOUR DAYS IN THE FUTURE. The
        # confirm door refuses a future changeover date (a future date leaves
        # every opening balance not yet due, so nothing is ever chased), and
        # putting the same guard on the LOAD path would refuse the frozen case
        # itself. That asymmetry is stated in the decision log rather than
        # papered over: the guard is on the new door only.
        real_changeover = (date.today() - timedelta(days=30)).isoformat()
        confirmed = import_runs.confirm_changeover_date(marcus, run_id, real_changeover)

        # ❄️ GT-16's own frozen figure, unchanged by the hold: the amounts never
        # moved, only the date they are recorded under.
        assert Decimal(confirmed["counts"]["opening_ar"]) == Decimal("267.30")
        assert confirmed["receipt"]["opening_held"] == 0
        assert confirmed["receipt"]["changeover_on"] == real_changeover
        assert (
            customers_models.AccountOpeningBucket.objects.filter(
                tenant_id=brazos.id, import_run_id=run_id
            )
            .exclude(as_of=date.fromisoformat(real_changeover))
            .count()
            == 0
        ), "every held bucket must carry the date the operator actually gave"

        # ⚠ **ONCE.** A second click must be neither an error nor a second
        # posting — a second posting would double a migration's AR.
        again = import_runs.confirm_changeover_date(marcus, run_id, real_changeover)
        assert Decimal(again["counts"]["opening_ar"]) == Decimal("267.30")


def test_w1_e2e__a_future_changeover_date_is_refused_by_name(brazos, marcus):
    """*The last day your old system was in charge of the money* cannot be in
    the future. A future date leaves every opening balance not yet due, so
    nothing is ever chased — and the error runs in the utility's favour."""
    with tenant_ctx(brazos):
        units = _two_units(marcus, brazos)
        run_id = _run(marcus, _csv_for(units))
        import_runs.load(marcus, run_id, {"write_mode": "insert", "approved": True})
        with pytest.raises(errors.BizError) as caught:
            import_runs.confirm_changeover_date(
                marcus, run_id, (date.today() + timedelta(days=1)).isoformat()
            )
        assert caught.value.br_ref == "BR-CUS-049"


def test_w1_e2e__a_row_naming_no_unit_on_file_is_an_error_never_an_autocreate(brazos, marcus, dana):
    """BR-CUS-047 — the migration order is Premises → Units + Plans → Assets →
    **Accounts** → opening reads. Auto-creating the unit would invent the
    premise half of a utility's estate from a billing spreadsheet.

    ⚠ **AMENDED 2026-08-30 — MARCUS CANNOT TICK `approved` AND THAT IS THE
    RULE, NOT A FIXTURE DETAIL.** BR-MET-098's approver clause — *"the approver
    is the same pair of roles as the rate-change second approval: Owner or
    Admin"* — was implemented in the engine by `DEF-545` and moved to the door
    by `DEF-1108`, so a Billing Clerk who crosses the error bar can no longer be
    their own second pair of eyes. This file's file DELIBERATELY carries a bad
    row, so it crosses the bar and needs a real approver; Dana is the System
    Admin. The other loads in this file still run as Marcus because their runs
    are clean and the flag grants nothing there — which is the engine's own
    deliberately narrower reading and is worth preserving in the fixtures.
    """
    with tenant_ctx(brazos):
        units = _two_units(marcus, brazos)
        content = _csv_for(units).replace(units[1]["unit_no"], "U-NOT-ON-FILE")
        run_id = _run(marcus, content, options={"cutover_on": CUTOVER})
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["counts"]["created"] == 1
        assert not customers_models.Account.objects.filter(
            tenant_id=brazos.id, account_no="A-12140"
        ).exists()


def test_w1_e2e__a_negative_bucket_LOADS_and_carries_the_credit(brazos, marcus):
    """⛔ **DEF-620 — THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-08-24.**

    It used to be `..._is_rejected_at_stage_3_and_names_OQ_065` and pinned the
    row as REJECTED. **OQ-065 closed on 2026-08-08** → BR-CUS-061, CONFIRMED:
    an opening CREDIT balance imports as a carried ACCOUNT CREDIT, and the
    aging buckets stay debit-only. Rejecting the row was option (c) — settle it
    in the legacy system — which the PO did not choose.

    ⚠ **THE HISTORY IS WORTH KEEPING BECAUSE THE ORIGINAL CASE WAS RIGHT ABOUT
    SOMETHING ELSE.** Writing it is what found DEF-614: the accounts target had
    no `PLATFORM_CATALOG` entry, so it got NO rules, `values_parse` never ran,
    and the negative came through CLEAN with the value silently dropped to NULL
    — the account loaded, its buckets were short, and every count on the
    receipt said the run was perfect. That guard stands; only the verdict on a
    credit has changed.

    US-CUS-021 TC-4's CivicCIS customer at −45.00 now MIGRATES.
    """
    with tenant_ctx(brazos):
        units = _two_units(marcus, brazos)
        content = _csv_for(units).replace(",84.20,", ",-45.00,")
        run_id = _run(marcus, content, options={"cutover_on": CUTOVER})
        run = metering_models.ImportRun.objects.get(pk=run_id)

        # Not a rejection any more — the row travels.
        assert import_runs.rejects(run) == []

        receipt = import_runs.load(marcus, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["counts"]["created"] == 2

        harmon = customers_models.Account.objects.get(tenant_id=brazos.id, account_no="A-12103")
        buckets = {
            row.bucket: row.amount
            for row in customers_models.AccountOpeningBucket.objects.filter(account=harmon)
        }
        # BR-CUS-061 debit-only: the CURRENT band takes nothing from the credit.
        assert buckets[customers_models.AccountOpeningBucket.BUCKET_CURRENT] == Decimal("0.0000")
        # ⚠ BR-CUS-077 (PO 2026-08-24) — the OTHER bands are untouched and keep
        # their AGE. This row is the mixed case: a credit in `current` and real
        # aged debt behind it. Netting them would have made the balance
        # 62.10 + 121.00 − 45.00 = 138.10 in one undifferentiated lump, and the
        # age of the 121.00 — the thing collections and disconnection notices
        # key off — would have been lost.
        assert buckets[customers_models.AccountOpeningBucket.BUCKET_31_60] == Decimal("62.1000")
        assert buckets[customers_models.AccountOpeningBucket.BUCKET_90_PLUS] == Decimal("121.0000")
        assert harmon.balance == Decimal("183.10")


def test_w1_e2e__the_value_map_step_resolves_a_LEGACY_account_type(brazos, marcus):
    """★ **TASK 1.20 / DEF-611 — the step S68 specified on 2026-08-08 and the
    product shipped without for two weeks.**

    A1 has specified the account import as `upload → stage → value-map → review
    → commit` since the day EP-CUS-07 was written. What stood on the route was a
    three-step modal: upload, review, commit. A utility whose export said
    `RESIDENTIAL - SINGLE FAM` where our reference data says `residential` had
    no way to reconcile the two, so they could not import accounts AT ALL.

    This is that step, proven rather than assumed. Nothing in `apps.metering`
    knows what an account type is: `KIND_LOOKUP` is one target-agnostic branch
    (BR-MET-096 forbids `if target == "accounts":` here) and the index arrives
    through `seams.account_lookup_indexes`. So the assertion is a round trip —
    the customer's own text goes in, the resolved code comes out, and the raw
    text survives beside it so the review screen can show the operator what it
    matched.
    """
    with tenant_ctx(brazos):
        units = _two_units(marcus, brazos)
        legacy = _csv_for(units).replace(",residential,", ",RESIDENTIAL,")
        run_id = _run(marcus, legacy, options={"cutover_on": CUTOVER})
        staged = metering_models.ImportRunRow.objects.filter(run_id=run_id).order_by("row_no")
        assert staged.exists(), "the run staged no rows to inspect"
        mapped = staged.first().mapped
        # The customer's word is carried, and OUR code is what resolved.
        assert mapped["account_type_raw"] == "RESIDENTIAL"
        assert mapped["account_type"] == "residential"


def test_w1_e2e__an_UNMAPPABLE_account_type_does_not_load_a_typeless_account(brazos, marcus, dana):
    """⛔ The other half of task 1.20, and the one that protects money.

    `_lookup_misses` — the evaluator the premises, units and meter targets all
    share — says a lookup miss *"will load with the field unset"*. For a meter
    type that is a cosmetic gap. For `account_type` it is not: the type is
    `required=True` in the column map and it is what a plan, a deposit rule and
    a tax treatment all key off. An account that loads with no type is a
    customer who cannot be billed correctly, created silently, in bulk.

    So this case pins the behaviour rather than assuming it. Whatever the
    product does here, the ONE thing it must not do is create the account.
    """
    with tenant_ctx(brazos):
        units = _two_units(marcus, brazos)
        # ⚠ count=1 — ROW 1 ONLY. The second row keeps a type it can resolve,
        # which is what makes the "the other 1,246 still load" assertion mean
        # something. Replacing both made this test pass for the wrong reason.
        content = _csv_for(units).replace(",residential,", ",WHOLESALE-XYZ,", 1)
        run_id = _run(marcus, content, options={"cutover_on": CUTOVER})

        # It is REJECTED at stage 3, with its row number, beside every other
        # rejection — not raised out of stage 4, which is the one stage that
        # writes (DEF-618).
        run = metering_models.ImportRun.objects.get(pk=run_id)
        rejects = {row["row_no"]: row["problem"] for row in import_runs.rejects(run)}
        assert 1 in rejects, f"the unmappable type was not rejected: {rejects}"
        assert "WHOLESALE-XYZ" in rejects[1]

        # And the run still LOADS the row that was fine. One bad cell in a
        # 1,247-row migration must not cost the other 1,246.
        #
        # ⚠ **DANA, NOT MARCUS, SINCE 2026-08-30.** This file carries a
        # deliberate reject, so the run crosses BR-MET-098's error bar and the
        # `approved` tick is what lets it through — and BR-MET-098's approver
        # clause is *"the same pair of roles as the rate-change second approval:
        # Owner or Admin"*. `DEF-545` put that refusal in the engine and
        # `DEF-1108` moved it to the door; a Billing Clerk approving their own
        # crossing is exactly what the rule forbids.
        receipt = import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        assert receipt["counts"]["created"] == 1
        assert not customers_models.Account.objects.filter(
            tenant_id=brazos.id, account_type__isnull=True
        ).exists()


#: ⛔ Lookup columns that NO rule in their target's catalogue speaks for, each
#: with the reason it is listed rather than fixed. **This register may only
#: shrink.** A new entry means a new instance of DEF-618 and needs a defect row
#: before it is added here.
LOOKUPS_WITHOUT_A_RULE = {
    # ⛔ **DEF-619 — INVESTIGATED 2026-08-24 AND IT IS COVERED. The convention,
    # not the catalogue, was the gap.** The row read *"`service` … has no
    # `*_in_lookup` rule, so an unrecognised service name is resolved to None at
    # stage 2, unremarked at stage 3, refused inside the load"*. Measured: the
    # middle claim is false. `AST.SERVICE_ENABLED` (`rule_kind=
    # "asset_service_enabled"`, TIER_STRUCTURAL, ERROR, reject_row) is declared
    # on BOTH targets and IS exactly this check — it is what DEF-619's own
    # prevention text asks somebody to declare, under a different name and at a
    # STRICTER tier (a structural rule cannot be switched off by a tenant at
    # all, BR-MET-090).
    # Proved rather than asserted from reading:
    # `tests/test_def616_def619_import_surface.py` sends `ELEC` to a tenant
    # whose list says `electric`, on both targets, and the row is REJECTED AT
    # STAGE 3 with *"This utility does not sell ELEC."* and a fix hint naming
    # both places it can be fixed; a BLANK service gets its own sentence.
    # So these two stay in the register with a REASON, exactly like the devices
    # entry below, rather than being deleted (which would make the guard fail on
    # a naming convention) or the guard widened (which would stop it biting).
    ("assets_meters", "service"): "covered by asset_service_enabled (DEF-619, proved 2026-08-24)",
    (
        "assets_submeters",
        "service",
    ): "covered by asset_service_enabled (DEF-619, proved 2026-08-24)",
    # Covered, but by a rule whose `rule_kind` does not follow the
    # `<column>_in_lookup` convention this guard reads: `AST.DEVICE_TYPE_ON_FILE`
    # (`rule_kind="device_type_on_file"`) is exactly this check for that column.
    # Listed so the guard stays honest about WHY it passes rather than widening
    # its matching until it stops biting.
    ("assets_devices", "type"): "covered by device_type_on_file",
    # ⛔ **DEF-MET-9258 — FOUR MORE OF DEF-619's SHAPE, INVESTIGATED 2026-10-03
    # AND COVERED.** `c51973920` (2026-09-30, asset upload U2–U8) added a
    # `Unit of measure` lookup to all three asset sheets and a `Service` lookup
    # to devices, and the rules it added for them are named for their QUESTION,
    # not their column: `AST.UOM_FOR_SERVICE` (`uom_for_service` — a unit not
    # on the list, or a unit for another service) and, on devices,
    # `AST.SERVICE_ENABLED` (`asset_service_enabled`, the meters' own rule).
    # Both TIER 1, ERROR, reject_row. Proved by RUNNING a file, not by reading
    # the catalogue: `tests/test_def_met_9258_asset_lookup_miss.py` sends one
    # good row and one with `furlongs` / `ELEC` on each, the bad row is
    # rejected at stage 3 by name, the good one loads, and the load writes one
    # asset. With the two evaluators removed those four cases go red.
    ("assets_meters", "unit"): "covered by uom_for_service (DEF-MET-9258, proved 2026-10-03)",
    (
        "assets_submeters",
        "unit",
    ): "covered by uom_for_service (DEF-MET-9258, proved 2026-10-03)",
    ("assets_devices", "unit"): "covered by uom_for_service (DEF-MET-9258, proved 2026-10-03)",
    (
        "assets_devices",
        "service",
    ): "covered by asset_service_enabled (DEF-MET-9258, proved 2026-10-03)",
}


def test_w1_e2e__every_lookup_column_is_spoken_FOR_by_a_rule():
    """⛔ **DEF-618's guard, and it is DEF-614's assertion one level deeper.**

    DEF-614 was fixed with `set(TARGETS) == set(PLATFORM_CATALOG)` — every
    target HAS a catalogue. That assertion passed while accounts' catalogue
    covered none of its four `KIND_LOOKUP` columns, because it cannot ask
    whether a catalogue COVERS the columns its target declares.

    Nothing else relates a column's `kind` to the rules that must exist for it,
    so a target can declare four lookups and zero lookup rules and every check
    in the repo stays green — right up until an operator sends a legacy code and
    the refusal surfaces inside the one stage that writes.

    ⚠ **AND THE FIXTURE LESSON IS HALF THE VALUE.** The happy-path tests all
    seed `account_type=residential`, which is OUR OWN vocabulary and therefore
    always resolves. A lookup column tested with a code the tenant already has
    exercises the one path that cannot fail. The whole point of the value-map
    step is the code that does NOT resolve.
    """
    from apps.metering import import_rules

    uncovered = []
    for target in import_runs.TARGETS:
        columns = import_runs.EXPLICIT_COLUMNS_BY_TARGET.get(target, ())
        rule_kinds = {rule.rule_kind for rule in import_rules.PLATFORM_CATALOG[target]}
        for column in columns:
            if column.get("kind") != import_runs.KIND_LOOKUP:
                continue
            name = column["target"]
            if f"{name}_in_lookup" in rule_kinds:
                continue
            reason = LOOKUPS_WITHOUT_A_RULE.get((target, name))
            if reason is not None:
                # DEF-MET-9258: a "covered by <rule_kind>" entry is a claim
                # about the catalogue, so it is checked against it — remove
                # the covering rule and the column is uncovered again.
                if reason.startswith("covered by "):
                    kind = reason.removeprefix("covered by ").split()[0]
                    if kind not in rule_kinds:
                        uncovered.append(f"{target}.{name} (no {kind} rule)")
                continue
            uncovered.append(f"{target}.{name}")

    assert uncovered == [], (
        "these lookup columns have no rule saying what a miss means, so a "
        "legacy code will be refused inside the LOAD instead of rejected at "
        f"stage 3 (DEF-618): {uncovered}"
    )

# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-001/004 (provisioning) · US-LED-005 (the seed chart) ·
#           US-RAT-008 (charge codes, S12/S13) · US-BIL-005 (issue — the GL
#           stamp)   Screens: S8 (Settings → Accounting) · S30 · S56
# Change:   CR-066 tasks A1, A2, A3, A4, B2 and D2 — every charge code,
#           adjustment reason and discount gets a GL account, because today a
#           fresh tenant cannot issue a bill that carries a fee.
# Rules:    BR-BIL-010 (every line carries a GL account resolved at issue and
#           frozen; *charge codes carry their own GL*) · BR-RAT-117 (PO
#           2026-08-22, *"ruccuring and Autom apply land on bill"*) ·
#           BR-TEN-012 (a tenant-touched row is never overwritten by a seed) ·
#           CLAUDE.md hard rule 7 (every money action writes audit_log) ·
#           CLAUDE.md law 14 (this must be proved on PostgreSQL, not SQLite)
# Tests:    this file
# Impacts:  apps/ledger/chart (the nine new accounts + the three maps) ·
#           apps/ledger/selectors · apps/rating/services.apply_default_gl_accounts
#           · apps/tenancy/services (provisioning + the repair door)
# ───────────────────────────────────────────────────────
"""**CAN A FRESHLY PROVISIONED TENANT ISSUE A BILL THAT CARRIES A FEE?**

Until 2026-09-02 the answer was NO, on every tenant this product has ever
created, and nothing said so. `apps/billing/issue.py` resolves a bill line's GL
account by KIND: a **usage** or **base** line resolves from the SERVICE's
designation and never looks at a charge code, while a **fee** line resolves
`rating.charges.gl_account_id` and **refuses the whole bill** when it is null.
The platform seed had never written that column.

**THAT ASYMMETRY IS WHY NOBODY SAW IT.** The sample estate issues 95 invoices on
a brand-new database with all 28 codes unmapped, because every line it writes is
usage or base — beside a Settings screen correctly reporting that 28 codes can
post nowhere. And two seeded codes (`PAPER`, `HYDRANT`) are `recurring`, which
`BR-RAT-117` puts on the ordinary bill of every tenant that configures one, so
**one unmapped recurring charge refuses a whole run**. `DEF-2386`.

⚠ **`requires_postgres` IS APPLIED TO THE WHOLE MODULE AND IT IS NOT
DECORATION (CLAUDE.md law 14).** `config/settings/test.py` hardcodes in-memory
SQLite. The provisioning path this exercises catches database errors per block
and continues, which on PostgreSQL means a poisoned transaction and on SQLite
means nothing at all — a green SQLite run here would be measuring a database
that cannot express the failure. Run it with:

    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub" \\
    JOBS_EAGER=false pytest tests/test_cr066_gl_defaults_live_pg.py --reuse-db

**NO PRICE MOVES IN THIS FILE.** CR-066 says where an amount POSTS, never what
it is; every assertion below is about an ACCOUNT, and the one money figure that
appears (`$2.00`, the seeded paper-bill fee) is asserted only to prove the fee
line is real and is quoted from the fixture rather than restated.
"""

import pytest

from tests.isolation_helpers import requires_postgres
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import brazosbend_payload, provisioned_tenant, tenant_ctx

pytestmark = [pytest.mark.django_db, requires_postgres]


#: The nine accounts CR-066 adds, exactly as they were put to the PO on screen.
#: Written out rather than imported from `chart` on purpose: a test that reads
#: its expectation out of the code under test asserts that the code equals
#: itself. These are the strings from the CR's own tables.
NINE_NEW_ACCOUNTS = (
    ("4600", "Connection & new-service fees"),
    ("4610", "Disconnection & reconnection fees"),
    ("4630", "Field-service & meter fees"),
    ("4640", "Equipment recovery & penalties"),
    ("4650", "Billing & payment fees"),
    ("4700", "Billing adjustment"),
    ("4710", "Leak adjustment"),
    ("4720", "Rate / meter correction"),
    ("4730", "Customer credit"),
)

#: CR-066 table 1, transcribed from the CR rather than from `chart.py`.
APPROVED_CHARGE_MAPPING = {
    "BULK-WATER": "4110",
    "LATE": "4200",
    "NSF": "4210",
    "CONN": "4600",
    "TAP": "4600",
    "TEMP-SVC": "4600",
    "TRANSFER": "4600",
    "IMPACT": "4600",
    "DISC": "4610",
    "RECON": "4610",
    "SEASONAL": "4610",
    "AFTER-HRS": "4630",
    "RETURN-TRIP": "4630",
    "SAME-DAY": "4630",
    "METER-TEST": "4630",
    "RE-READ": "4630",
    "MOVE-OUT": "4630",
    "INSPECT": "4630",
    "HYDRANT": "4630",
    "DAMAGE": "4640",
    "TAMPER": "4640",
    "PAPER": "4650",
    "CC-CONV": "4650",
}

#: CR-066 table 2, transcribed from the CR.
APPROVED_REASON_MAPPING = {
    "BILLERR": "4700",
    "LEAK": "4710",
    "METERR": "4720",
    "GOODWILL": "4730",
    "DISPUTE": "4700",
}

#: The base-code RULE, not a list — a base charge code posts to its own
#: service's revenue account. These are the pairings `chart.SERVICE_REVENUE_
#: ACCOUNTS` already held before CR-066 and the CR names them one by one.
BASE_CODE_ACCOUNT = {
    "BASE-W": "4115",
    "BASE-W-COM": "4115",
    "BASE-S": "4120",
    "BASE-T": "4130",
    "BASE-FIRE": "4155",
    "BASE-E": "4105",
    "BASE-G": "4140",
    "BASE-TH": "4170",
    "BASE-SOL": "4150",
    "BASE-BAT": "4150",
    "BASE-BB": "4145",
    "BASE-SW": "4160",
}


def _tenant(settings, subdomain, services=("water", "sewer", "trash", "fire")):
    """One tenant provisioned from EMPTY through the real signup entry point.

    ⚠ **`JOBS_EAGER = True` IS LOAD-BEARING.** The sample plant is a QUEUED JOB
    and the suites run with `JOBS_EAGER=false` for speed (`DEF-567`), so without
    this the tenant is provisioned and NO sample data is planted — zero rows and
    zero failing blocks, which reads exactly like the defect under test and is
    not it. `test_cr063_fire_live_pg.py` sets the same flag for the same reason.
    """
    settings.JOBS_EAGER = True
    return provisioned_tenant(
        brazosbend_payload(
            subdomain=subdomain,
            name="Brazos Bend Water & Fire",
            services=list(services),
            owner={
                "full_name": "Ruth Alvarez",
                "email": f"ruth@{subdomain}.example.invalid",
                "password": "S3cure!passw0rd",
                "phone": None,
            },
        )
    )


def _charge_map(tenant):
    """`{charge code: chart code or None}` for every charge the tenant holds."""
    from apps.ledger import models as ledger_models
    from apps.rating import models as rating_models

    codes = {
        str(row.id): row.code
        for row in ledger_models.LedgerAccount.objects.filter(tenant_id=tenant.id)
    }
    return {
        row.code: codes.get(str(row.gl_account_id)) if row.gl_account_id else None
        for row in rating_models.Charge.objects.filter(
            tenant_id=tenant.id, deleted_at__isnull=True
        )
    }


# ══════════════════════════════════════════════════════════════════════════
# A1 — the nine accounts exist, and every one is UNSIGNED
# ══════════════════════════════════════════════════════════════════════════
def test_cr066_a1__the_nine_new_accounts_are_seeded_and_none_is_finance_signed(
    growth_plan, audit_rows, settings
):
    """The accounts CR-066 adds, on a tenant provisioned from empty.

    ⚠ **THE SECOND HALF IS THE ONE THAT MATTERS TO A REVIEWER.** The PO approved
    the MAPPING — which charge code and which adjustment reason posts where —
    having been shown every account's name and number in plain English. A
    finance signature on the chart is a SEPARATE act and has not happened, so
    all nine sit in `chart.PENDING_FINANCE_RE_SIGN` on the 4160/4170 precedent
    and this test is what goes RED if someone quietly drops a flag.
    """
    from apps.ledger import chart
    from apps.ledger import models as ledger_models

    tenant, _result = _tenant(settings, "cr066-a1")
    with tenant_ctx(tenant):
        rows = {
            row.code: row
            for row in ledger_models.LedgerAccount.objects.filter(tenant_id=tenant.id)
        }

    for code, name in NINE_NEW_ACCOUNTS:
        assert code in rows, (
            f"{code} {name!r} is not in a freshly provisioned tenant's chart. CR-066 "
            "task A1 seeds it; without it every charge code the PO mapped to it stays "
            "NULL and a bill carrying that fee refuses at issue (BR-BIL-010)."
        )
        assert rows[code].name == name, (
            f"{code} is named {rows[code].name!r} and the PO was shown {name!r}. A "
            "signature covers only what was shown."
        )
        assert code in chart.PENDING_FINANCE_RE_SIGN, (
            f"{code} is not in PENDING_FINANCE_RE_SIGN. The PO approved the MAPPING, "
            "not the chart — a finance re-sign goes through HUMAN-GUIDE §6 and no "
            "agent may write one. Dropping this flag makes an unsigned account look "
            "signed on every surface that reads the tuple."
        )

    # The four adjustment rows are `contra_revenue`, following CR-061's ruling
    # (*"no, you cannot file discount under revenue"*) and the PO's own
    # reference chart, which gives every Revenue Adjustments row Normal
    # Balance = Debit. The five fee rows are revenue.
    for code in ("4600", "4610", "4630", "4640", "4650"):
        assert rows[code].type == "revenue", code
    for code in ("4700", "4710", "4720", "4730"):
        assert rows[code].type == "contra_revenue", (
            f"{code} is typed {rows[code].type!r}. An adjustment REDUCES revenue and "
            "is debit-normal on the PO's own chart; CR-061 minted `contra_revenue` "
            "for exactly that shape."
        )


# ══════════════════════════════════════════════════════════════════════════
# A2 — THE DELIVERABLE: zero unmapped charge codes on a fresh tenant
# ══════════════════════════════════════════════════════════════════════════
def test_cr066_a2__a_fresh_tenant_has_zero_unmapped_charge_codes(
    growth_plan, audit_rows, settings
):
    """**THE ONE THE PO WILL LOOK AT.** S8 → Settings → Accounting → *Charges
    and fees* reported *"28 charges have no account to post to"* on a tenant the
    PO had just redeployed with a deleted database. This asserts the banner is
    gone, by asserting the fact behind it.

    It counts what the SCREEN counts — every live charge row whose
    `gl_account_id` is NULL — and it does NOT special-case the base codes,
    because the whole point of `DEF-2386` is that the count includes them.
    """
    tenant, _result = _tenant(settings, "cr066-a2")
    with tenant_ctx(tenant):
        mapping = _charge_map(tenant)

    unmapped = sorted(code for code, account in mapping.items() if account is None)
    assert unmapped == [], (
        f"{len(unmapped)} charge code(s) still have no account to post to: "
        f"{', '.join(unmapped[:10])}. That is the banner the PO photographed, and a "
        "bill carrying any one of them refuses at issue (BR-BIL-010). CR-066 task A2."
    )
    assert len(mapping) >= 28, (
        f"only {len(mapping)} charge codes exist; the PO's screen showed 28 (23 "
        "platform codes plus the base codes for the services this tenant sells). A "
        "count that fell means the seed stopped creating rows, which would make the "
        "zero above true for the wrong reason."
    )


def test_cr066_a2__every_code_lands_where_the_po_approved_it(
    growth_plan, audit_rows, settings
):
    """Not merely mapped — mapped to the account the PO was SHOWN.

    A sweep that pointed all 28 codes at one bucket would satisfy the test
    above and would be exactly the failure `issue.py`'s own refusal message
    warns about: *"a fee posted into the electric revenue bucket is
    indistinguishable from electricity sold, on a record that is frozen the
    moment it issues."*
    """
    tenant, _result = _tenant(settings, "cr066-a2b")
    with tenant_ctx(tenant):
        mapping = _charge_map(tenant)

    wrong = {
        code: (mapping[code], expected)
        for code, expected in APPROVED_CHARGE_MAPPING.items()
        if code in mapping and mapping[code] != expected
    }
    assert wrong == {}, (
        "these codes post somewhere other than the account the PO approved in CR-066 "
        f"table 1 — {{code: (actual, approved)}}: {wrong}"
    )

    # THE BASE CODES ARE A RULE, NOT A LIST. Whichever of the twelve this
    # tenant holds must land on its own service's revenue account.
    base_wrong = {
        code: (mapping[code], expected)
        for code, expected in BASE_CODE_ACCOUNT.items()
        if code in mapping and mapping[code] != expected
    }
    assert base_wrong == {}, (
        "a base charge code posts to its own SERVICE's revenue account (CR-066 table "
        f"1's ⚠ note). Wrong — {{code: (actual, expected)}}: {base_wrong}"
    )
    assert any(code.startswith("BASE-") for code in mapping), (
        "this tenant holds no BASE-* code at all, so the base half of the rule was "
        "never exercised. Check the sample plant ran (JOBS_EAGER)."
    )


# ══════════════════════════════════════════════════════════════════════════
# A3 — BR-TEN-012: the backfill fills a NULL and never overwrites a choice
# ══════════════════════════════════════════════════════════════════════════
def test_cr066_a3__the_backfill_never_overwrites_an_account_a_tenant_chose(
    growth_plan, audit_rows, settings
):
    """**`BR-TEN-012`, tested specifically because it is the one way this
    change could destroy a utility's own configuration.**

    A tenant that files its after-hours calls in an account of their own has
    made a decision. A seed that re-ran and overwrote it would be provisioning
    quietly undoing a clerk — silently, on a money path, with the old value
    surviving only in `audit_log`.
    """
    from apps.ledger import models as ledger_models
    from apps.rating import models as rating_models
    from apps.rating import services as rating_services

    tenant, _result = _tenant(settings, "cr066-a3")
    with tenant_ctx(tenant):
        # The tenant's OWN choice: point AFTER-HRS at 4210 rather than the
        # 4630 the platform default gives it.
        their_choice = ledger_models.LedgerAccount.objects.get(
            tenant_id=tenant.id, code="4210"
        )
        charge = rating_models.Charge.objects.get(tenant_id=tenant.id, code="AFTER-HRS")
        charge.gl_account_id = their_choice.id
        charge.save(update_fields=["gl_account_id", "updated_at"])

        # A code they have NOT touched, cleared, to prove the sweep still fills.
        untouched = rating_models.Charge.objects.get(tenant_id=tenant.id, code="TAMPER")
        untouched.gl_account_id = None
        untouched.save(update_fields=["gl_account_id", "updated_at"])

        result = rating_services.apply_default_gl_accounts(actor=None)
        mapping = _charge_map(tenant)

    assert mapping["AFTER-HRS"] == "4210", (
        "the sweep overwrote an account the tenant had set. BR-TEN-012: a "
        "tenant-touched row is never overwritten by a seed, and the value it "
        "replaced would live only in `audit_log`, which is pruned (OQ-1340)."
    )
    assert mapping["TAMPER"] == "4640", (
        "the sweep left a NULL pointer NULL, so the backfill does not work at all"
    )
    assert result["charges_mapped"] == 1, (
        "exactly one row had a NULL account and exactly one should have been "
        f"written; the sweep reported {result['charges_mapped']}"
    )


def test_cr066_a3__a_second_run_writes_nothing(growth_plan, audit_rows, settings):
    """Idempotent, which is what makes the repair door safe to run at will."""
    from apps.rating import services as rating_services

    tenant, _result = _tenant(settings, "cr066-a3b")
    with tenant_ctx(tenant):
        again = rating_services.apply_default_gl_accounts(actor=None)

    assert again["charges_mapped"] == 0, again
    assert again["discounts_mapped"] == 0, again
    assert again["charges_unmapped"] == [], (
        "a code with no platform default is reported rather than guessed, and on a "
        f"stock tenant there should be none: {again['charges_unmapped']}"
    )


# ══════════════════════════════════════════════════════════════════════════
# A4 — the five adjustment reasons
# ══════════════════════════════════════════════════════════════════════════
def test_cr066_a4__every_adjustment_reason_shows_an_account(
    growth_plan, audit_rows, settings
):
    """CR-066 table 2, as approved.

    ⚠ **THIS UNBLOCKS NO BILL AND THE PO WAS TOLD SO** in the same message that
    carried the table. Nothing in the backend reads
    `reason_codes.default_gl_account_id`; an adjustment credit reverses whatever
    account the original bill credited. The mapping is correct to have and it is
    NOT what makes a fee bill issuable — that is the charge codes.
    """
    from apps.ledger import models as ledger_models
    from apps.tenancy import models as tenancy_models

    tenant, _result = _tenant(settings, "cr066-a4")
    with tenant_ctx(tenant):
        codes = {
            str(row.id): row.code
            for row in ledger_models.LedgerAccount.objects.filter(tenant_id=tenant.id)
        }
        mapping = {
            row.code: codes.get(str(row.default_gl_account_id))
            if row.default_gl_account_id
            else None
            for row in tenancy_models.ReasonCode.objects.filter(tenant_id=tenant.id)
        }

    for code, expected in APPROVED_REASON_MAPPING.items():
        assert mapping.get(code) == expected, (
            f"adjustment reason {code} points at {mapping.get(code)!r}; CR-066 table 2 "
            f"puts it on {expected}"
        )


# ══════════════════════════════════════════════════════════════════════════
# B2 — every discount starts at 4760
# ══════════════════════════════════════════════════════════════════════════
def test_cr066_b2__a_seeded_discount_posts_to_4760(growth_plan, audit_rows, settings):
    """CR-066 table 3: *"Please apply these - Table 3 - discounts."*

    `4760 Customer discounts (contra-revenue)` is the row CR-061 already ruled
    into existence — *"no, you cannot file discount under revenue"*. This
    changes no posting: a discount line already resolves that account BY
    DESIGNATION at issue. What it adds is the column, so a tenant can see the
    answer and override it.
    """
    from apps.ledger import models as ledger_models
    from apps.rating import discounts as discount_models

    tenant, _result = _tenant(settings, "cr066-b2")
    with tenant_ctx(tenant):
        codes = {
            str(row.id): row.code
            for row in ledger_models.LedgerAccount.objects.filter(tenant_id=tenant.id)
        }
        mapping = {
            row.code: codes.get(str(row.gl_account_id)) if row.gl_account_id else None
            for row in discount_models.Discount.objects.filter(tenant_id=tenant.id)
        }

    assert mapping, (
        "this tenant has no discounts at all, so nothing was measured. The sample "
        "plant seeds five (SENIOR, CAP, PAPERLESS, AUTOPAY, MILITARY) — check "
        "JOBS_EAGER."
    )
    unmapped = sorted(code for code, account in mapping.items() if account != "4760")
    assert unmapped == [], (
        f"these discounts do not post to 4760: {unmapped} (actual: {mapping})"
    )


# ══════════════════════════════════════════════════════════════════════════
# D2 — THE REGRESSION THAT WOULD HAVE CAUGHT DEF-2386
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **EVERY OTHER TEST IN THIS FILE COUNTS A COLUMN; THESE TWO ISSUE A BILL.**
# That is the difference between checking the fix and checking the DEFECT. The
# sample estate already issues 95 invoices on a tenant whose 28 codes point
# nowhere, so "bills issue" was TRUE throughout the defect and proves nothing —
# every line the estate writes is usage or base, and those resolve from the
# SERVICE's designation. Only a bill carrying a FEE line reaches the branch that
# was broken.
#
# The fee is put on the bill the way `BR-RAT-117` puts one there in production
# (PO 2026-08-22, *"ruccuring and Autom apply land on bill"*): `PAPER`, the
# seeded paper-bill fee, is `recurring`, so setting `auto_apply` is the one act
# a real tenant performs. Nothing else about the tenant is touched.


def _owner_actor(tenant):
    """The tenant's provisioning owner, as the sample plant's own actor.

    Not a shim: `release.authorise_release` records WHO confirmed BR-BIL-058's
    five facts as a real `users` FK, so a stand-in would corrupt the trail this
    test is partly about (hard rule 7).
    """
    from apps.identity import models as identity_models

    membership = (
        identity_models.TenantMembership.objects.filter(
            tenant_id=tenant.id,
            role__code="system_admin",
            status=identity_models.TenantMembership.STATUS_ACTIVE,
        )
        .select_related("user", "role")
        .order_by("created_at")
        .first()
    )
    assert membership is not None, "the tenant has no active System Admin to bill as"
    owner = membership.user
    owner.role = membership.role.code
    return owner


def _a_third_cycle(tenant):
    """A period the sample plant has NOT billed, so this test bills it itself.

    The plant bills June and July (`_periods_to_bill` / `_second_cycle_periods`)
    and seeds August's reads without billing them, so August is the one period
    with meter data and no invoices. Its `bill_on` is `None` in the fixture
    because nobody bills it; a date is supplied here, by the caller, because
    `G6` bans a wall clock from every money path and a run has to be dated by
    the person who asked for it (BR-BIL-070).
    """
    from core import sample_fixture as fixture

    august = next(period for period in fixture.PERIODS if period["key"] == "august")
    return {**august, "key": "august-cr066", "bill_on": august["end"]}


def _bill_the_third_cycle(tenant, *, paper_account):
    """Turn `PAPER` into a recurring auto-apply fee and bill one more period.

    `paper_account` is written to `charges.gl_account_id` before the run —
    the tenant's own value for the GREEN case, and `None` for the RED one,
    which reproduces the pre-CR-066 seed EXACTLY rather than approximating it.
    """
    from apps.billing import sample_data as billing_sample
    from apps.rating import models as rating_models

    actor = _owner_actor(tenant)
    paper = rating_models.Charge.objects.get(tenant_id=tenant.id, code="PAPER")
    before = paper.gl_account_id
    paper.auto_apply = True
    paper.gl_account_id = paper_account if paper_account != "keep" else before
    paper.save(update_fields=["auto_apply", "gl_account_id", "updated_at"])
    cycle_id = billing_sample._preconditions(actor)
    return billing_sample._bill_one_period(actor, _a_third_cycle(tenant), cycle_id), before


def test_cr066_d2__a_bill_carrying_a_fee_line_issues_and_the_fee_is_stamped(
    growth_plan, audit_rows, settings
):
    """**THE CASE THE WHOLE CR EXISTS FOR.** A freshly provisioned tenant turns
    on its paper-bill fee — one checkbox, the thing `BR-RAT-117` is for — and
    its next bill run goes out.

    Before CR-066 this run refused every bill that carried the fee, by name, and
    the tenant could do nothing about it on any screen because the account it
    needed did not exist in their chart. The companion test below is that
    failure, reproduced.
    """
    from apps.billing import models as billing_models
    from apps.ledger import models as ledger_models

    tenant, _result = _tenant(settings, "cr066-d2")
    with tenant_ctx(tenant):
        issued, paper_account = _bill_the_third_cycle(tenant, paper_account="keep")
        assert paper_account is not None, (
            "PAPER has no GL account on a freshly provisioned tenant, so the seed "
            "half of CR-066 did not run and this test would be measuring the defect "
            "rather than the fix"
        )
        fee_lines = list(
            billing_models.InvoiceLine.objects.filter(
                tenant_id=tenant.id, kind="fee", invoice__status="issued"
            )
        )
        codes = {
            str(row.id): row.code
            for row in ledger_models.LedgerAccount.objects.filter(tenant_id=tenant.id)
        }

    assert issued > 0, (
        "a tenant with ONE recurring auto-apply charge code issued NO bills. That is "
        "DEF-2386 exactly: issue.py refuses the whole bill when a fee line's charge "
        "code has no GL account, and BR-RAT-117 puts that code on every ordinary bill"
    )
    assert fee_lines, (
        f"{issued} bill(s) issued and NOT ONE carries a fee line, so the branch this "
        "test exists to exercise was never reached. `PAPER` is `recurring` and was "
        "given `auto_apply`, which is BR-RAT-117's own condition."
    )
    stamped = {codes.get(str(line.gl_account_id)) for line in fee_lines}
    assert stamped == {"4650"}, (
        f"the paper-bill fee posted to {stamped}; CR-066 table 1 puts PAPER on 4650 "
        "Billing & payment fees"
    )


def test_cr066_d2__the_same_run_refuses_when_the_fee_code_has_no_account(
    growth_plan, audit_rows, settings
):
    """**THE RED HALF, RUN AS A TEST RATHER THAN DESCRIBED (law 7).**

    `charges.gl_account_id = NULL` is not an approximation of the pre-CR-066
    state — it IS that state, because the platform seed had never written the
    column. So this is the bill the going-live customer would have got.

    ⚠ **IT ASSERTS THE SENTENCE, NOT ONLY THE FAILURE.** A run that refused for
    any other reason would pass a bare `raises`, and this test would then be
    green for the wrong defect — which is the failure mode `DEF-182` records
    about checks that cannot tell pass from fail.
    """
    from core import sample_fixture as fixture

    tenant, _result = _tenant(settings, "cr066-d2-red")
    with tenant_ctx(tenant):
        with pytest.raises(fixture.BlockCannotRun) as refused:
            _bill_the_third_cycle(tenant, paper_account=None)

    detail = str(refused.value)
    assert "no GL account" in detail, detail
    assert "does not issue" in detail or "BR-BIL-010" in detail, detail

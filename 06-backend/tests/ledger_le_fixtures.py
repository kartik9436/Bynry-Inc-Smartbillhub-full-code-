"""The LE-1 / LE-2 / LE-3 / LE-6 month, posted through the real posting service.

NOT a test module and deliberately not named like one: pytest collects
`tests/test_*.py`, and a helper that defines pytest fixtures AND is imported by
several test modules registers those fixtures twice — which
`tests/test_us_led_001_posting.py` records as making every test in the importing
file error with `assert not self._finalizers` before it runs. So this file holds
PLAIN FUNCTIONS only, in the shape of `tests/isolation_helpers.py`.

════════════════════════════════════════════════════════════════════════════
EVERY FIGURE HERE IS COPIED FROM A SIGNED SOURCE. NONE IS COMPUTED.
════════════════════════════════════════════════════════════════════════════
`04-docs/05-modules/09-ledger/08-worked-examples.md` LE-1..LE-6, allocated GT
numbers GT-51..GT-56 by the ❄️ frozen `05-golden-tests.md` (*"LE-n → GT-(50+n)
… expected values = the machine-computed workbook figures verbatim"*). A
fixture that re-derived a total would agree with a broken implementation.

════════════════════════════════════════════════════════════════════════════
ONE DELIBERATE DEPARTURE FROM LE-1'S TABLE, AND IT IS A RULING, NOT A DRIFT
════════════════════════════════════════════════════════════════════════════
LE-1 books the customer payment to *"1000 Cash (150.00 + 292.87) 442.87"*. The
Product Owner ruled on 2026-08-11 (OQ-143), verbatim:

    "Cash is received but undeposted in such case payment will say csah but
     ledger will say undeposited - until bank record and reconcilaition
     confirm it it is not realised"

`apps/payments/ledger_seam.py` implements it: the RECEIPT leg debits **1010
Undeposited funds** and only `apps/payments/reconciliation.py` moves it to 1000.
So this fixture posts the 292.87 payment to 1010, and LE-1's single cash row
becomes two — **1000 150.00 · 1010 292.87** — summing to the same 442.87.

**The trial balance is untouched: 598.69 = 598.69.** Nothing frozen moved; one
row became two. The payments lane reported the restatement when it made the
ruling real; this is the first fixture that RENDERS it, which is why it is
stated here as well.

The CUSTOMER DEPOSIT's 150.00 still debits 1000 Cash, because that is what the
signed DR/CR contract row says (*"Cash deposit taken (payment purpose=deposit) |
cash | deposit liability"*, EP-LED-01) and what LE-1 books. Whether OQ-143's
two-step applies to a deposit as well is a real fork and is raised as an OQ by
the lane that wrote this file, not answered in a fixture.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal

from apps.customers import models as customer_models
from apps.ledger import models, posting, services as ledger_services
from apps.tenancy import models as tenancy_models

#: BR-TEN-043 / the PO's OQ-107 ruling — the caller names the moment, so every
#: entry in the fixture month stamps the same one and G6's "no clock in a money
#: path" holds in the fixtures too.
POSTED_AT = datetime(2026, 8, 3, 9, 15, tzinfo=dt_timezone.utc)

JULY_START = date(2026, 7, 1)
JULY_END = date(2026, 7, 31)
CUTOVER = date(2026, 6, 30)

# ── LE-1, transcribed ───────────────────────────────────────────────────────
LE1_OPENING_AR = Decimal("45.00")
LE1_DEPOSIT_HELD = Decimal("150.00")
LE1_DEPOSIT_INTEREST = Decimal("3.50")
LE1_WE1_BILL = Decimal("247.87")
LE1_WE3_BILL = Decimal("16.42")
LE1_WE3_REVENUE = Decimal("15.00")
LE1_WE3_TAX = Decimal("1.42")
LE1_WE7B_BILL = Decimal("289.40")
LE1_WE7B_REVENUE = Decimal("264.41")
LE1_WE7B_TAX = Decimal("24.99")
LE1_DEPOSIT_APPLIED = Decimal("153.50")
LE1_MASTER_TRANSFER = Decimal("135.90")
LE1_PAYMENT = Decimal("292.87")

#: LE-1's trial-balance table, verbatim — with the OQ-143 restatement splitting
#: the cash row in two (see the module docstring).
LE1_CASH_REALISED = Decimal("150.00")
LE1_CASH_UNDEPOSITED = Decimal("292.87")
LE1_CASH_TOTAL = Decimal("442.87")  # "1000 Cash (150.00 + 292.87) | 442.87"
LE1_AR = Decimal("152.32")  # "1200 AR | 152.32"
LE1_INTEREST_EXPENSE = Decimal("3.50")
LE1_REVENUE = Decimal("506.31")  # "(226.90 + 15.00 + 264.41)"
LE1_TAX_PAYABLE = Decimal("47.38")  # "(20.97 + 1.42 + 24.99)"
LE1_DEPOSIT_LIABILITY = Decimal("0.00")  # "(150.00 + 3.50 - 153.50)"
LE1_OPENING_EQUITY = Decimal("45.00")
LE1_FOOTING = Decimal("598.69")  # "Totals | 598.69 | 598.69 ✔"

#: US-LED-007 §7 (CONFIRMED) and LE-6's KPI strip.
BILLED_IN_PERIOD = Decimal("553.69")  # "247.87 + 16.42 + 289.40"
COLLECTED_COLUMN = Decimal("446.37")  # LE-6 KPI strip: "292.87 + 153.50"
COLLECTION_PCT_NUMERATOR = Decimal("401.37")  # US-LED-007 §7 — NOT derivable
COLLECTION_PCT = Decimal("72.49")  # US-LED-007 §7 — NOT derivable

#: US-LED-001 TC-2 verbatim — WE-1's nine credit buckets. The tax is shown here
#: as ONE 2200-03 line because that is exactly how LE-1's own trial balance
#: states it (*"2200-03 Tax payable (20.97 + 1.42 + 24.99) | 47.38"*). The
#: four-way per-authority split is LE-3's and lives in `post_le3_authorities`.
WE1_TAX = Decimal("20.97")
WE1_REVENUE_BUCKETS = (
    # (code, amount, service_code) — LE-2: *"Electric 100.60 (usage 88.60 +
    # base 12.00) · Water 47.50 · Sewer 15.80 · Trash 18.00 · Solar capacity
    # 40.00 · Late fee 5.00 = 226.90 ✔"*. The late fee carries NO service: a fee
    # is charged to an ACCOUNT, which is also why `apps/ledger/chart.py` keeps
    # 4200 out of the per-service revenue rows.
    ("4100", Decimal("88.60"), "electric"),
    ("4105", Decimal("12.00"), "electric"),
    ("4110", Decimal("39.50"), "water"),
    ("4115", Decimal("8.00"), "water"),
    ("4120", Decimal("15.80"), "sewer"),
    ("4130", Decimal("18.00"), "trash"),
    ("4150", Decimal("40.00"), "solar"),
    ("4200", Decimal("5.00"), None),
)
WE1_REVENUE = Decimal("226.90")

#: LE-2's per-service totals, transcribed — the assertion target of
#: `revenue_by_service`.
LE2_BY_SERVICE = {
    "electric": Decimal("100.60"),
    "water": Decimal("47.50"),
    "sewer": Decimal("15.80"),
    "trash": Decimal("18.00"),
    "solar": Decimal("40.00"),
}

#: LE-3 / US-LED-014 §4 verbatim: *"per-authority billed split: State 13.87 ·
#: County 2.22 · City 4.44 · PUC 0.44"* — WE-1's 20.97 tax, and the reason
#: BR-BIL-069 (*"For each atheority have separate account and tagging"*) makes
#: the remittance report possible with no `tax_authority_id` dimension at all.
LE3_AUTHORITIES = (
    ("2200-01", "TX Comptroller — state sales tax", Decimal("13.87")),
    ("2200-02", "Travis County", Decimal("2.22")),
    ("2200-03", "City of Austin franchise", Decimal("4.44")),
    ("2200-04", "TX PUC", Decimal("0.44")),
)
LE3_BILLED_BASIS_JULY = Decimal("47.38")  # all three bills
LE3_COLLECTED_BASIS_JULY = Decimal("20.97")  # WE-1's cleared payment only
LE3_STATE_REMIT_NOW = Decimal("13.87")


def uuid_for(seed: str):
    """A stable uuid per fixture string, so a replayed fixture keys the same."""
    return _uuid.uuid5(_uuid.NAMESPACE_URL, f"smartbillhub-test/{seed}")


def gl(tenant, code, type_="revenue", name=None):
    """The tenant's account for `code`, seeded or created.

    Provisioning seeds the shared chart (B5 line 74 ❄️) and — since the PO's
    OQ-115 ruling — only the revenue accounts for services the tenant sells.
    Brazos Bend sells Electric and Water, so 4100/4105/4110/4115 are already
    there and 4120/4130/4150 are minted here. The 2200 series is seeded to
    NOBODY by design and is minted through the real service call in
    `ensure_authority_accounts`.
    """
    row, _made = models.LedgerAccount.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": name or f"GL {code}", "type": type_}
    )
    return row


def service_id(code: str):
    return tenancy_models.Service.objects.get(code=code).id


def line(account, side, amount, **overrides):
    """One posting line with BR-LED-001's two mandatory dimensions filled in."""
    values = {"source_type": "invoice_line", "source_id": uuid_for(account.code)}
    values.update(overrides)
    return posting.PostingLine(
        ledger_account_id=account.id, side=side, amount=Decimal(amount), **values
    )


def a_request(lines, *, key, entry_date=JULY_END, **overrides):
    values = {
        "posting_key": key,
        "entry_date": entry_date,
        "posted_at": POSTED_AT,
        "currency": "USD",
        "lines": tuple(lines),
        "source_type": "invoice",
        "source_id": uuid_for(key),
        "memo": "fixture",
    }
    values.update(overrides)
    return posting.PostingRequest(**values)


def make_accounts(actor, tenant, world, service="electric"):
    """Four customer accounts on three premises — LE-6's own cast.

    They exist so the `account_id` dimension on every journal line is a REAL
    account, and so US-LED-010's refusal is provable rather than vacuous: the
    premises rows exist, the units exist, the accounts point at them, and the
    journal STILL carries `premises_id = NULL` on every line because nothing
    stamps it (US-LED-002, unbuilt).

    `service` is a parameter because a unit may only offer a service its tenant
    has ENABLED (BR-MET-*): Brazos Bend sells Electric and Water, Lone Star
    Ridge sells Water only, and the isolation cases build their cast in the
    second tenant. Defaulting it silently to electric made those cases fail with
    `metering.service_not_enabled` — a real rule, correctly refusing.
    """
    from tests.test_us_met_helpers import make_premises, make_unit

    status = customer_models.AccountStatus.objects.get(tenant=tenant, code="active")
    account_type = customer_models.AccountType.objects.first()
    made = {}
    for key, address, label, account_no in (
        ("ACC-1042", "500 Main St", "200", "ACC-1042"),
        ("ACC-1051", "Oak Grove", "12", "ACC-1051"),
        ("ACC-1055", "Marina Bay", "3B", "ACC-1055"),
        ("ACC-0009", "Marina Bay", "MASTER", "ACC-0009"),
    ):
        premises = world.setdefault("premises", {}).get(address)
        if premises is None:
            premises = make_premises(actor, address_line=address, services_available=[service])
            world["premises"][address] = premises
        unit = make_unit(actor, premises["id"], label=label, services=[service])
        made[key] = customer_models.Account.objects.create(
            tenant=tenant,
            unit_id=unit["id"],
            account_no=account_no,
            status=status,
            account_type=account_type,
        )
    return made


def post_le1_month(tenant, accounts):
    """Every posting LE-1 names, through `post()`, with the account dimension.

    LE-1 §Postings verbatim: *"opening AR 45.00 · deposit held 150.00 (cash DR /
    liability CR) · interest accrual 3.50 (DR interest exp / CR liability) ·
    three bills (AR DR 553.69 / revenue CR 506.31 / tax CR 47.38) · deposit
    application (liability DR 153.50 / AR CR) · master transfer (AR ACC-1055 CR
    135.90 / AR ACC-0009 DR 135.90 — AR total unchanged) · payment (cash DR
    292.87 / AR CR)."*

    Bill dates are spread across the month (WE-1 on the 15th, WE-3 on the 20th,
    WE-7B on the 25th) so a test can window ONE bill and assert LE-2's slice.
    LE-1 fixes the MONTH and no bill date, so nothing signed is being chosen.
    """
    cash = gl(tenant, "1000", "asset")
    undeposited = gl(tenant, "1010", "asset")
    ar = gl(tenant, "1200", "asset")
    tax = gl(tenant, "2200-03", "liability", name="Tax payable")
    deposit = gl(tenant, "2300", "liability")
    opening = gl(tenant, "3000", "equity")
    interest = gl(tenant, "6950", "expense")
    generic_revenue = gl(tenant, "4100", "revenue")

    def pair(key, debit_gl, credit_gl, amount, source_type, entry_date, **dims):
        return posting.post(
            a_request(
                [
                    line(debit_gl, models.SIDE_DEBIT, amount, source_type=source_type, **dims),
                    line(credit_gl, models.SIDE_CREDIT, amount, source_type=source_type, **dims),
                ],
                key=key,
                entry_date=entry_date,
                source_type=source_type,
            )
        )

    # Opening balance (BR-CUS-049), dated BEFORE the month so the account
    # ledger's opening row has something to be.
    pair(
        "opening_balance|ACC-1042|cutover",
        ar,
        opening,
        LE1_OPENING_AR,
        "opening_balance",
        CUTOVER,
        account_id=accounts["ACC-1042"].id,
    )
    # Cash deposit taken — DR 1000 Cash per the signed contract row. See the
    # module docstring: whether OQ-143's two-step applies here too is an OQ.
    pair(
        "payment|DEP-1042|deposit_taken",
        cash,
        deposit,
        LE1_DEPOSIT_HELD,
        "deposit",
        date(2026, 7, 1),
        account_id=accounts["ACC-1042"].id,
    )
    pair(
        "deposit|DEP-1042|interest_accrued",
        interest,
        deposit,
        LE1_DEPOSIT_INTEREST,
        "deposit",
        JULY_END,
        account_id=accounts["ACC-1042"].id,
    )

    # WE-1 — the only bill LE-2 splits by service, so it is the only one posted
    # with service dimensions. WE-3 and WE-7B are stated by LE-1 as revenue +
    # tax TOTALS, and a per-service split for them would be invented.
    we1_lines = [
        line(
            ar,
            models.SIDE_DEBIT,
            LE1_WE1_BILL,
            source_type="invoice",
            account_id=accounts["ACC-1042"].id,
        )
    ]
    for code, amount, service_code in WE1_REVENUE_BUCKETS:
        we1_lines.append(
            line(
                gl(tenant, code, "revenue"),
                models.SIDE_CREDIT,
                amount,
                account_id=accounts["ACC-1042"].id,
                service_id=service_id(service_code) if service_code else None,
            )
        )
    we1_lines.append(line(tax, models.SIDE_CREDIT, WE1_TAX, account_id=accounts["ACC-1042"].id))
    posting.post(a_request(we1_lines, key="invoice|WE-1|issued", entry_date=date(2026, 7, 15)))

    posting.post(
        a_request(
            [
                line(
                    ar,
                    models.SIDE_DEBIT,
                    LE1_WE3_BILL,
                    source_type="invoice",
                    account_id=accounts["ACC-1051"].id,
                ),
                line(
                    generic_revenue,
                    models.SIDE_CREDIT,
                    LE1_WE3_REVENUE,
                    account_id=accounts["ACC-1051"].id,
                ),
                line(tax, models.SIDE_CREDIT, LE1_WE3_TAX, account_id=accounts["ACC-1051"].id),
            ],
            key="invoice|WE-3|issued",
            entry_date=date(2026, 7, 20),
        )
    )
    posting.post(
        a_request(
            [
                line(
                    ar,
                    models.SIDE_DEBIT,
                    LE1_WE7B_BILL,
                    source_type="invoice",
                    account_id=accounts["ACC-1055"].id,
                ),
                line(
                    generic_revenue,
                    models.SIDE_CREDIT,
                    LE1_WE7B_REVENUE,
                    account_id=accounts["ACC-1055"].id,
                ),
                line(tax, models.SIDE_CREDIT, LE1_WE7B_TAX, account_id=accounts["ACC-1055"].id),
            ],
            key="invoice|WE-7B|issued",
            entry_date=date(2026, 7, 25),
        )
    )
    # Deposit application at final bill (BR-BIL-013). BR-REP-009: *applied
    # deposits count as collected* — and this entry is identifiable ONLY by its
    # deposit-liability debit leg, which is what `revenue_and_ar` looks for.
    pair(
        "invoice|WE-7B|deposit_applied",
        deposit,
        ar,
        LE1_DEPOSIT_APPLIED,
        "invoice",
        JULY_END,
        account_id=accounts["ACC-1055"].id,
    )
    # Master transfer — two AR lines on ONE account, two different customer
    # accounts. AR total unchanged; the DIMENSION is what moves.
    posting.post(
        a_request(
            [
                line(
                    ar,
                    models.SIDE_DEBIT,
                    LE1_MASTER_TRANSFER,
                    source_type="transfer",
                    source_id=uuid_for("ACC-0009"),
                    account_id=accounts["ACC-0009"].id,
                ),
                line(
                    ar,
                    models.SIDE_CREDIT,
                    LE1_MASTER_TRANSFER,
                    source_type="transfer",
                    source_id=uuid_for("ACC-1055"),
                    account_id=accounts["ACC-1055"].id,
                ),
            ],
            key="transfer|ACC-1055|to_master",
            source_type="transfer",
        )
    )
    # Payment cleared — DR 1010 UNDEPOSITED (PO 2026-08-11, OQ-143), not cash.
    pair(
        "payment|PAY-1042|cleared",
        undeposited,
        ar,
        LE1_PAYMENT,
        "payment",
        JULY_END,
        account_id=accounts["ACC-1042"].id,
    )


def reconcile_the_payment(tenant, accounts):
    """The SECOND step of the OQ-143 ruling: the bank confirms it.

    `DR 1000 Cash 292.87 / CR 1010 Undeposited 292.87` — the shape
    `apps/payments/ledger_seam.post_batch_reconciled` posts. Called only by the
    tests that need realised cash to MOVE, so the default fixture month leaves
    the money undeposited and a cash-basis figure that counted it goes red.
    """
    cash = gl(tenant, "1000", "asset")
    undeposited = gl(tenant, "1010", "asset")
    posting.post(
        a_request(
            [
                line(
                    cash,
                    models.SIDE_DEBIT,
                    LE1_PAYMENT,
                    source_type="deposit_batch",
                    source_id=uuid_for("DEP-0731"),
                    account_id=accounts["ACC-1042"].id,
                ),
                line(
                    undeposited,
                    models.SIDE_CREDIT,
                    LE1_PAYMENT,
                    source_type="deposit_batch",
                    source_id=uuid_for("DEP-0731"),
                    account_id=accounts["ACC-1042"].id,
                ),
            ],
            key="deposit_batch|DEP-0731|reconciled",
            source_type="deposit_batch",
        )
    )


def ensure_authority_accounts(tenant, actor=None):
    """Mint LE-3's four authorities through the REAL service call.

    `apps.ledger.services.create_tax_authority_account` is the only path that
    exists — B5 line 74 ❄️ says *tenant authorities mint their own*, so the seed
    chart carries no 2200 row and a fixture that created one with
    `objects.create` would be testing a path the product does not have.
    """
    return {
        code: ledger_services.create_tax_authority_account(code=code, name=name, actor=actor)
        for code, name, _amount in LE3_AUTHORITIES
    }


def post_le3_authorities(tenant, accounts, authority_accounts):
    """WE-1's 20.97 tax, split four ways per LE-3 — the BR-BIL-069 shape.

    *"billed basis (tax on issued bills: July 20.97 = State 13.87 · County 2.22
    · City 4.44 · PUC 0.44)"* (ledger pre-session model §5, PO-confirmed as
    BR-LED-002). One line per authority, each to that authority's OWN
    2200-nn account — which is what makes `remittance_by_authority` a group-by
    over accounts and needs no `tax_authority_id` dimension at all.
    """
    ar = gl(tenant, "1200", "asset")
    revenue = gl(tenant, "4100", "revenue")
    lines = [
        line(
            ar,
            models.SIDE_DEBIT,
            LE1_WE1_BILL,
            source_type="invoice",
            account_id=accounts["ACC-1042"].id,
        ),
        line(
            revenue,
            models.SIDE_CREDIT,
            WE1_REVENUE,
            account_id=accounts["ACC-1042"].id,
        ),
    ]
    for code, _name, amount in LE3_AUTHORITIES:
        lines.append(
            line(
                authority_accounts[code],
                models.SIDE_CREDIT,
                amount,
                account_id=accounts["ACC-1042"].id,
            )
        )
    posting.post(
        a_request(lines, key="invoice|WE-1-authorities|issued", entry_date=date(2026, 7, 15))
    )

# ── Trace ──────────────────────────────────────────────
# Story:   US-CWP-037 (EP-CWP-07) — *your final bill, where the deposit comes
#          back*. Screen CWP-032. (Wave J's other two stories, US-CWP-042 and
#          US-CWP-068, have no screen to seed for — see the walkthrough.)
# Rules:   BR-CWP-048 (a negative final balance is a REFUND, never a carried
#          credit) · BR-CWP-049 (the deposit and its interest settle here) ·
#          BR-CUS-056 (the outgoing account pays the move DAY, so `period_end`
#          IS `moved_out_on`) · BR-CUS-057 (the accrual) · hard rule 1 (every
#          filter names its tenant) · hard rule 4 (financial immutability — this
#          file only ever CREATES rows; it updates no issued invoice)
# Tests:   fixture prep for
#          10-scripts/render-checks/cr068-j-self-read-and-final-bill.mjs
# ───────────────────────────────────────────────────────
"""TWO PEOPLE MOVING OUT, BECAUSE ONE OF THEM CANNOT SHOW THE WHOLE SCREEN.

WHY THIS FILE EXISTS
--------------------
`seed_portal_demo` plants **no final bill at all** — measured on a freshly
seeded clone, not one account on the tenant carries `moved_out_on` and no
invoice is typed `final`. So `/final-bill` draws *"When your service ends, your
last bill will be here."* for every customer in the estate, and a walkthrough
that opened it would assert happily over the one state the screen is NEVER in
when it matters. That is `DEF-WRK-4121`'s lesson — **assert in the state the
screen is normally in, not the fixture's default** — and on this screen the
fixture's default is a blank page.

⚠ **AND ONE MOVE-OUT IS NOT ENOUGH, WHICH IS THE FINDING THAT SHAPED THIS
FILE.** `CWP-032` has two halves and they are mutually exclusive:

  * **we owe you** — the deposit exceeds the charges. `settle_account` picks
    the path itself (*"nobody chooses whether to give back money that is not
    theirs"*), so `Settlement.path` is `refund` …
  * … and `Settlement.settled` is `path is not None or remainder == 0`.

**So a refund bill is `settled` from the instant it is first read**, which
means `query_reading_open` (`not settled`) is FALSE and the *Query this
reading* control never draws on it. The only bill that shows that control is
one where the customer still OWES — where a staff choice is outstanding and
`path` is None. A fixture holding one move-out can therefore only ever see one
of the two, and whichever it picked would read as a clean run.

So: **two leaving customers, one of each shape.**

    elm@example.test      $63.40 charges, $150.00 deposit  → we owe you, refund
    leaving@example.test  $289.10 charges, $150.00 deposit → you owe us, pending

THE INTEREST RATE IS SET HERE, DELIBERATELY
-------------------------------------------
The seeded tenant pays **0%**, so `deposit_interest_accrued` returns a real
`$0.00` and the settlement short-circuits past the accrual entirely. The
decision-log row of 2026-09-04 (`DEF-CWP-3842`) says so in as many words and
records the fixture's answer as `−$86.60` rather than the story's `−$89.80`.
**That is the branch that had no test through the door the product uses** — the
same row records that billing's own suite covered `settle_account` only on
accounts holding NO deposit. Setting the rate to 2% makes the accrual actually
run, which is the point of walking it in a browser.

⚠ **AND THE WALKTHROUGH STILL ASSERTS THE ARITHMETIC RATHER THAN THE LITERAL.**
`US-CWP-037` carries `golden_tests: []`, so `$3.20` and `$89.80` are a story's
illustration and not a ❄️ frozen B4/B5 figure; the engine's answer for this
tenant, this principal and this many days is whatever it is. What must hold is
that the lines on the screen ADD UP to the total on the screen. A literal would
be the walkthrough asserting the engine's answer back at it — the reason
`test_us_cwp_037_final_bill.py` refuses to type `$3.20` too.

RUN IT
------
    10-scripts/proof-db.sh clone cwpj --export      # then export what it prints
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    (cd 06-backend && python3 manage.py seed_portal_demo)
    (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-j-fixture.py)

Idempotent: every write is guarded by a lookup, so a second run re-uses what it
finds and creates nothing twice.
"""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from decimal import Decimal

from apps.billing import models as billing_models
from apps.customers import models as customers_models
from apps.identity import models as identity_models
from apps.metering import models as metering_models
from apps.portal import credentials
from apps.portal import models as portal_models
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from apps.tenancy.models import Tenant
from core.tenancy import tenant_context

PASSWORD = "Pine-Hill-2026!"
STAFF_EMAIL = "sarah@pinehillwp.test"
ELM_EMAIL = "elm@example.test"
LEAVING_EMAIL = "leaving@example.test"
ELM_ST = "1408 Elm St"

#: `US-CWP-037` §4 and the wave J demo script, step 6.
MOVED_OUT_ON = date(2026, 9, 17)
PERIOD_START = date(2026, 9, 1)
REFUND_CHARGES = Decimal("63.4000")
OWED_CHARGES = Decimal("289.1000")
DEPOSIT_HELD = Decimal("150.0000")
DEPOSIT_TAKEN_ON = date(2021, 3, 4)
#: The drawing's closing reading. 154,310 − 153,040 = 1,270 gal since 1 Sep,
#: which is the figure the CLOSING READING panel puts beside it.
CLOSING_VALUE = Decimal("154310")
PRIOR_VALUE = Decimal("153040")

tenant = Tenant.objects.filter(subdomain="pine-hill").first()
if tenant is None:  # pragma: no cover — a run against an unseeded database
    raise SystemExit("no Pine Hill tenant — run `manage.py seed_portal_demo` first")


def a_final_bill(account, *, total, number):
    """One ISSUED bill typed `final`, in the shape the settlement meets it.

    ⚠ **CREATED, NEVER UPDATED** (hard rule 4). A second run finds the row by
    its number and leaves it exactly as it is — an issued invoice is immutable
    and a fixture is not an exception to that.

    Through the ORM rather than the bill run, the shape
    `test_us_cwp_037_final_bill.py` already established and states its reason
    for: the issue path drags the rating engine, the GL stamp and the release
    gate into a fixture about what happens to a bill AFTER it exists.
    """
    # ⚠ **KEYED ON THE ACCOUNT, NOT ON THE NUMBER.** `final_bill_for` looks a
    # bill up BY ACCOUNT, so "does BL-2609-0164 exist" is the wrong question: a
    # re-run that picked a different second account would find the number
    # taken, skip the create, and leave the new account with no final bill and
    # the old one holding a bill nobody can sign in to see.
    found = billing_models.Invoice.objects.filter(
        tenant_id=tenant.pk, account_id=account.pk, bill_type="final"
    ).first()
    if found is not None:
        return found, False
    # ⚠ **AND THE NUMBER IS TAKEN IF AN EARLIER RUN CHOSE A DIFFERENT ACCOUNT.**
    # `uq_invoices_no` is (tenant, invoice_no), so a half-finished run leaves a
    # bill nobody reaches AND a number nobody can reuse — an issued invoice may
    # not be deleted to tidy it up (hard rule 4). Walk to the next free one
    # rather than making the fixture depend on a pristine clone.
    stem, _, tail = number.rpartition("-")
    seq = int(tail)
    while billing_models.Invoice.objects.filter(
        tenant_id=tenant.pk, invoice_no=f"{stem}-{seq:04d}"
    ).exists():
        seq += 1
    number = f"{stem}-{seq:04d}"
    return (
        billing_models.Invoice.objects.create(
            tenant=tenant,
            account=account,
            invoice_no=number,
            status=billing_models.INVOICE_ISSUED,
            bill_type="final",
            service_date=MOVED_OUT_ON,
            period_start=PERIOD_START,
            # BR-CUS-056 — the outgoing account pays the move DAY.
            period_end=MOVED_OUT_ON,
            due_date=date(2026, 10, 2),
            subtotal=total,
            tax_total=Decimal("0"),
            total=total,
            currency="USD",
            issued_at=datetime(2026, 9, 18, 9, 0, tzinfo=UTC),
        ),
        True,
    )


def hold_a_deposit(account):
    """Put the deposit on the account and hand back a FRESH row.

    ⚠ **THE REFRESH IS LOAD-BEARING.** `account_summary` reads
    `deposit_on_file` off the row it is PASSED while `final_bill` re-queries
    through `deposit_credit_for`, so a stale object makes the settlement find a
    deposit and `CWP-065` find none — which looks exactly like the two screens
    disagreeing, the very defect `US-CWP-037` TC-5 exists to catch, and is not.
    """
    customers_models.Account.objects.filter(tenant_id=tenant.pk, pk=account.pk).update(
        deposit_on_file=DEPOSIT_HELD, deposit_received_on=DEPOSIT_TAKEN_ON
    )
    return customers_models.Account.objects.get(tenant_id=tenant.pk, pk=account.pk)


def enrol(account, email):
    existing = credentials.credential_by_email(tenant.pk, email)
    if existing is not None:
        return False
    credentials.create_credential(
        tenant.pk,
        account=account,
        email=email,
        password=PASSWORD,
        otp_channel=portal_models.CHANNEL_SMS,
    )
    return True


with tenant_context(tenant.pk):
    # ⚠ **EVERY FILTER NAMES `tenant_id`** (`DEF-CWP-4173`). This process runs as
    # `smartbillhub`, which is `rolsuper=t`, so FORCE RLS is skipped for every
    # query here and three tenants are seeded in the same database.

    # ── 1 · the tenant pays interest on deposits ──────────────────────────
    #
    # The rate lives on the S66 Billing-defaults page and is read through
    # tenancy's OWN selector, never its models (B1 / DB-16) — which is the same
    # route `deposit_interest._tenant_rate` takes to find it.
    family = tenancy_selectors.settings_family("billing-defaults")
    rate_before = family.get("deposit_interest_rate_annual")
    # ⚠ **COMPARED AS A NUMBER, NOT AS A STRING.** The seeded value is the
    # string `'0.000000'` — six places, because a percentage is stored to six
    # (hard rule 2) — so a guard written as `in ("", "0", "0.00")` reads it as
    # already-set and silently leaves the accrual short-circuiting at zero,
    # which is the exact branch this fixture exists to open.
    def _is_zero(value):
        try:
            return Decimal(str(value or "0")) == 0
        except ArithmeticError:
            return True

    if _is_zero(rate_before):
        # ⚠ **THROUGH THE SERVICE, WITH A REAL ACTOR** — a settings write is a
        # permissioned action (`AUTH-002` on `actor=None`) and it writes an
        # audit row. Reaching past it into `TenantSettings.objects.update` would
        # set the same value and skip both, which is a fixture teaching the next
        # lane the wrong way in.
        staff = identity_models.User.objects.filter(
            tenant_id=tenant.pk, email__iexact=STAFF_EMAIL
        ).first()
        if staff is None:
            raise SystemExit(f"no {STAFF_EMAIL} on this tenant — seed_portal_demo did not run")
        # ⚠ **THE ROLE IS ON THE ACTOR, NOT ON THE `users` ROW.**
        # `@require_role(SYSTEM_ADMIN)` reads `actor.role`, and `User` carries
        # no such column — the role travels with the caller, which is why every
        # test builds this same `SimpleNamespace` around a REAL user row rather
        # than passing the model. Passing the model gives `role=None` and the
        # save refuses with `AUTH-002`, which reads like a broken fixture.
        actor = SimpleNamespace(id=staff.id, pk=staff.id, role="system_admin", user=staff)
        tenancy_services.save_settings_family(
            actor, "billing-defaults", {"deposit_interest_rate_annual": "2"}
        )
        rate_after = tenancy_selectors.settings_family("billing-defaults").get(
            "deposit_interest_rate_annual"
        )
        print(f"  deposit interest  {rate_before!r} → {rate_after!r} (percent, annual)")
    else:
        print(f"  deposit interest  already {rate_before!r} — left alone")

    # ── 2 · the customer who is owed money ────────────────────────────────
    unit = (
        metering_models.Unit.objects.filter(
            tenant_id=tenant.pk, premises__address_line=ELM_ST, label="A"
        )
        .select_related("premises")
        .first()
    )
    if unit is None:
        raise SystemExit(f"no {ELM_ST} · A on this tenant — seed_portal_demo did not run")
    elm = customers_models.Account.objects.filter(
        tenant_id=tenant.pk, unit_id=unit.id
    ).first()
    if elm is None:
        raise SystemExit(f"nobody holds an account at {ELM_ST} · A")
    elm = hold_a_deposit(elm)
    refund_bill, made = a_final_bill(elm, total=REFUND_CHARGES, number="BL-2609-0163")
    print(
        f"  refund bill       {refund_bill.invoice_no} ${refund_bill.total} on "
        f"{elm.account_no} ({ELM_ST} · {unit.label}) {'created' if made else 'already there'}"
    )

    # ── 3 · the closing reading the drawing puts on the screen ────────────
    #
    # ⚠ **ON the move-out day, not after it.** `closing_reading_for` walks the
    # readings newest-first and takes the first one taken on or before
    # `moved_out_on`; a read dated 18 September would belong to whoever moves
    # in, and the panel would quietly show the 31 August figure instead.
    meter = (
        metering_models.MeterRead.objects.filter(
            tenant_id=tenant.pk, account_id=elm.pk, superseded_by_id__isnull=True
        )
        .order_by("-read_at")
        .first()
    )
    if meter is None:
        raise SystemExit(
            "no readings on the Elm St account — seed_portal_demo should have printed a "
            "`wave H:` line. The CLOSING READING panel would honestly draw its empty "
            "sentence, which reads exactly like a broken screen."
        )
    closing = metering_models.MeterRead.objects.filter(
        tenant_id=tenant.pk,
        account_id=elm.pk,
        read_at__date=MOVED_OUT_ON,
        superseded_by_id__isnull=True,
    ).first()
    if closing is None:
        closing = metering_models.MeterRead.objects.create(
            tenant=tenant,
            account=elm,
            asset=meter.asset,
            read_at=datetime(2026, 9, 17, 10, 30, tzinfo=UTC),
            period_start=PERIOD_START,
            period_end=MOVED_OUT_ON,
            prior_value=PRIOR_VALUE,
            current_value=CLOSING_VALUE,
            multiplier=meter.multiplier,
            consumption=CLOSING_VALUE - PRIOR_VALUE,
            unit=meter.unit,
            # ⚠ The drawing says *"17 Sep, by a reader"* — a person the utility
            # SENT. Not `self_read`: there is no way in this product for a
            # customer to have taken it, which is this wave's whole finding.
            source="manual",
            read_method=meter.read_method,
            status=meter.status,
            lifecycle=meter.lifecycle,
        )
        print(
            f"  closing reading   {CLOSING_VALUE} on {MOVED_OUT_ON} "
            f"({CLOSING_VALUE - PRIOR_VALUE} {closing.unit} since {PERIOD_START}) created"
        )
    else:
        print(f"  closing reading   {closing.current_value} on {MOVED_OUT_ON} already there")

    # ── 4 · the customer who still owes ───────────────────────────────────
    #
    # A SECOND deposit-holding account, so the walk can open the half of
    # `CWP-032` the refund can never show. Found by holding a deposit rather
    # than by account number, which a counter mints and which moves whenever
    # the estate ahead of it changes size (`DEF-CWP-4174`).
    # ⚠ **AND IT MUST BE LINKED TO A CUSTOMER, WHICH NOT EVERY SEEDED ACCOUNT
    # IS.** `create_credential` refuses an account with no `CustomerAccount`
    # row — *"there is nobody to enrol"* — and the first deposit-holding
    # account on this tenant by number, `A-10432`, is exactly that. Choosing by
    # deposit alone put the fixture one step from a login that cannot exist.
    enrollable = customers_models.CustomerAccount.objects.filter(
        tenant_id=tenant.pk
    ).values_list("account_id", flat=True)
    owing = (
        customers_models.Account.objects.filter(
            tenant_id=tenant.pk,
            unit_id__isnull=False,
            pk__in=list(enrollable),
        )
        .exclude(pk=elm.pk)
        .order_by("account_no")
        .first()
    )
    if owing is None:
        raise SystemExit("no second deposit-holding account with a customer on this tenant")
    owing = hold_a_deposit(owing)
    owed_bill, made = a_final_bill(owing, total=OWED_CHARGES, number="BL-2609-0164")
    print(
        f"  owed bill         {owed_bill.invoice_no} ${owed_bill.total} on "
        f"{owing.account_no} {'created' if made else 'already there'}"
    )

    # ── 5 · two logins ────────────────────────────────────────────────────
    print(f"  {ELM_EMAIL:22s}{'enrolled' if enrol(elm, ELM_EMAIL) else 'already enrolled'} on {elm.account_no}")
    print(
        f"  {LEAVING_EMAIL:22s}"
        f"{'enrolled' if enrol(owing, LEAVING_EMAIL) else 'already enrolled'} on {owing.account_no}"
    )

    print()
    print(f"  sign in as {ELM_EMAIL} or {LEAVING_EMAIL}, password {PASSWORD}")

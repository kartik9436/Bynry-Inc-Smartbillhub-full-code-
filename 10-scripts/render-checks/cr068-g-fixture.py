# ── Trace ──────────────────────────────────────────────
# Story:   US-CWP-048 (EP-CWP-07) — the money list. Screen: CWP-041.
# Rules:   BR-CWP-061 (a bounce is TWO rows — the reversal above the payment it
#          undoes) · hard rule 4 (nothing edits a payment; a reversal is a NEW
#          row) · hard rule 1 (every read and write names its tenant —
#          `DEF-CWP-4130`, RLS is OFF where this runs)
# Tests:   fixture prep for
#          10-scripts/render-checks/cr068-g-bills-and-money-list.mjs
# ───────────────────────────────────────────────────────
"""A BOUNCED CHEQUE ON THE DEMO TENANT, SO WAVE G's STEP 5 HAS SOMETHING TO SEE.

WHY THIS FILE EXISTS
--------------------
`10-execution-plan.md` wave G task **G3** names the fixture this wave needs —
*"the four bills, the corrected pair, the bounce, the adjustment, the write-off,
41 documents, the intents"* — and **none of it is written.** `seed_portal_demo`
plants the generic sample estate: real bills, real payments, real allocations,
and **every payment cleared**. So `GET /portal/payments` answers a list in which
`returned_by_the_bank` is `false` on every row, and the walkthrough's assertions
about the bounce would be made against a list that cannot contain one.

That is the failure this repository calls *a check that cannot fail*: on an
all-cleared list, "no reversal is drawn as an ordinary payment" is vacuously
true, `[].every(...)` is `true`, and the run goes green having proved nothing
about `BR-CWP-061` at all. Wave H recorded the same class of blocker in its own
words — *"a browser pointed at the demo tenant today would open `CWP-033` and
honestly draw nothing"* — and the answer there was the same as the answer here:
extend the seed before writing the assertions, not after.

WHAT IT PLANTS, AND WHAT IT DELIBERATELY DOES NOT
-------------------------------------------------
**It bounces one cheque, through the real service.** `payments.reversal.
reverse_payment` is the function the staff screen calls; it writes the reversing
payment row, its reversing allocations, the ledger mirror and the audit row in
one transaction. A fixture that INSERTed a row with `reverses_payment_id` set
would put the two rows on screen and prove nothing about the path that produces
them — `cr070-b-fixture.py` makes the same argument about its own tables.

⚠ **IT DOES NOT MANUFACTURE THE CORRECTED PAIR** (`BR-CWP-042`), and that is a
refusal rather than an omission. A correction runs through
`billing/single_correction.py`, which is **HUMAN-OWNED and 🔒 sensitive** — its
own header says *"rating math, money rounding and the ledger handoff all meet in
the path this composes, and every executed branch writes money"*. Driving it
from a walkthrough fixture to make a screenshot look complete would be a lane
inventing money math, which the prime directive forbids. The walkthrough
therefore SKIPS its corrected-pair assertions **by name and out loud**, and says
in its own output that the pair was never planted, rather than reporting a
silent pass over an absence.

⚠ **AND IT IS THE LANDLORD'S ACCOUNTS THIS TOUCHES**, because the householder
`ana@example.test` has no payments at all — she owes every bill she has been
sent. `maria@example.test` holds three accounts, six bills and five cleared
payments, including a genuinely **part-paid** bill, which is the third state
`BR-CWP-043` exists for. The walkthrough signs in as her for that reason and
says so.

IDEMPOTENT
----------
Run it twice and the second run finds the reversal it already wrote and writes
nothing new — the reversing row carries an idempotency reference, and this
script checks for an existing reversal before asking for one.

RUN IT
------
    eval "$(10-scripts/proof-db.sh clone <label> --export)"
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    (cd 06-backend && python3 manage.py seed_portal_demo)
    (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/def-cwp-3965-fixture.py)
    (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr068-g-fixture.py)
"""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

from apps.customers import models as customers_models
from apps.payments import models as payments_models
from apps.payments import reversal
from apps.portal import credentials
from apps.tenancy.models import Tenant
from core.tenancy import tenant_context

LANDLORD = "maria@example.test"


def _actor(tenant_id):
    """A staff actor for the reversal — the bank told the utility, not the customer.

    ⚠ A BOUNCE IS A STAFF ACTION AND THE PORTAL CANNOT RAISE ONE. `BR-CWP-001`
    names four kinds of row the portal may create and a reversal is none of
    them, so this fixture stands in for the clerk who keys the returned item,
    which is the only way one is ever recorded.
    """
    from apps.identity import models as identity_models

    user = (
        identity_models.User.objects.filter(tenant_id=tenant_id, deleted_at__isnull=True)
        .order_by("created_at")
        .first()
    )
    if user is None:
        raise SystemExit("no user on this tenant — run `manage.py seed_portal_demo` first")
    #: ⚠ **THE ROLE IS WHAT THE GUARD READS, NOT THE ROW.** `core.permissions`
    #: refuses on `actor.role`, so handing it a bare `User` raises
    #: `AUTH-002 permission denied` — which reads as "this fixture is not
    #: allowed to do that" rather than "this actor has no role attached".
    #: Same shape the suite's own `staff_actor` returns.
    return SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)


def _landlord_accounts(tenant_id):
    """Maria's accounts, named by her credential rather than by number.

    ⚠ **EVERY QUERYSET NAMES ITS TENANT** (`DEF-CWP-4130`). RLS is bypassed for
    the superuser role every walkthrough runs as, so `.objects.all()` inside a
    `tenant_context` returns the OTHER tenant's rows too — 51 of them on a
    two-tenant seed. The filter is what scopes this, not the context.
    """
    credential = credentials.credential_by_email(tenant_id, LANDLORD)
    if credential is None:
        raise SystemExit(
            f"no portal login for {LANDLORD} — run def-cwp-3965-fixture.py first"
        )
    customer_id = credential.customer_id
    links = customers_models.CustomerAccount.objects.filter(
        tenant_id=tenant_id, customer_id=customer_id
    )
    return [
        account
        for link in links
        if (
            account := customers_models.Account.objects.filter(
                pk=link.account_id, tenant_id=tenant_id
            ).first()
        )
        is not None
    ]


tenant = Tenant.objects.filter(name__icontains="Pine Hill").first()
if tenant is None:  # pragma: no cover — a run against an unseeded database
    raise SystemExit("no Pine Hill tenant — run `manage.py seed_portal_demo` first")

with tenant_context(tenant.pk):
    accounts = _landlord_accounts(tenant.pk)
    account_ids = [a.pk for a in accounts]
    print(f"landlord holds {len(accounts)} account(s): {', '.join(a.account_no for a in accounts)}")

    #: The cheque to bounce: a CLEARED cheque, because a bounce is a cheque
    #: coming back and the demo should show the tender a person recognises.
    #: Picked by QUERY rather than by number — the sample estate is generated
    #: and its references move (`def-cwp-3965-fixture.py` makes the same point).
    candidates = [
        p
        for p in payments_models.Payment.objects.filter(
            tenant_id=tenant.pk, account_id__in=account_ids
        ).order_by("-posted_at")
        if p.reverses_payment_id is None
    ]
    #: ⚠ **A CHEQUE FIRST, BUT NOT ONLY A CHEQUE.** The demo script's bounce is
    #: a cheque because that is the tender a person pictures being returned;
    #: a card chargeback and a failed ACH are the same two rows on this screen.
    #: So the cheque is PREFERRED and anything else is accepted, and the script
    #: prints which tender it actually took — a fixture that silently picked a
    #: different one would leave the walkthrough's reader comparing a screen
    #: against a sentence describing another payment.
    def _tender_name(payment):
        tender = getattr(payment, "tender", None) or getattr(payment, "method", None)
        return str(getattr(tender, "name", "") or getattr(tender, "code", "") or "")

    def _settles_its_bill_in_full(payment):
        """Would bouncing this payment leave every bill it touched fully unpaid?

        ⚠ **THIS IS THE RULE, AND THE FIRST DRAFT GOT IT WRONG IN A WAY THAT
        DESTROYED THE THING THE WAVE EXISTS TO SHOW.** That draft preferred a
        CHEQUE, on the reasoning that a returned cheque is what a person
        pictures. It picked the card payment instead — the cheque rows on this
        estate carry no `method` at all, so the tender name came back `''` and
        the filter matched nothing — and the card payment was **the part
        payment that made `BL-2608-000097` part-paid.** Reversing it put that
        bill back to owing its full amount, and `CWP-027` lost the only row
        where `owing` and `amount` differ. The walkthrough then reported, quite
        correctly, that *"every row owes all or nothing, so this fixture cannot
        prove `BR-CWP-043`"* — the wave's own headline rule, destroyed by its
        own fixture.

        So the tender is cosmetic and THIS is the constraint: bounce a payment
        that settles its bills **completely**, and the part-paid bill survives.
        A bounce and a part payment are two different demonstrations and the
        fixture must not spend one to buy the other.
        """
        allocations = list(payment.allocations.all())
        if not allocations:
            return False
        for allocation in allocations:
            invoice = getattr(allocation, "invoice", None)
            if invoice is None:
                return False
            if Decimal(str(allocation.amount)) != Decimal(str(invoice.total)):
                return False
        return True

    full_settlements = [p for p in candidates if _settles_its_bill_in_full(p)]
    cheques = full_settlements or candidates
    if not full_settlements:
        print(
            "  ⚠ no payment settles its bill in full — bouncing a PART payment, "
            "which costs this fixture its part-paid bill (BR-CWP-043)"
        )
    if not cheques:
        raise SystemExit(
            "the landlord holds no payment to bounce — the money list would be "
            "empty and every assertion about it would pass vacuously"
        )

    already = payments_models.Payment.objects.filter(
        tenant_id=tenant.pk, reverses_payment_id__in=[p.pk for p in cheques]
    ).first()
    if already is not None:
        original = payments_models.Payment.objects.get(pk=already.reverses_payment_id)
        print(
            f"already bounced: {original.confirmation or original.pk} "
            f"{original.amount} → reversal {already.amount}"
        )
    else:
        #: The LAST cheque, so the bounce sits at the top of the money list
        #: where the drawing puts it and a reader can see both rows without
        #: paging. `returned_on` is the BANK's date and the service reads no
        #: clock of its own (BR-PAY-021).
        target = cheques[0]
        done = reversal.reverse_payment(
            _actor(tenant.pk),
            payment_id=target.pk,
            returned_on=datetime(2026, 8, 21, 10, 30, tzinfo=UTC),
            reason=payments_models.REVERSAL_REASON_NSF,
            idempotency_reference="CWP-G-WALKTHROUGH-BOUNCE",
        )
        print(
            f"bounced {_tender_name(target) or 'payment'} "
            f"{target.confirmation or target.pk}: "
            f"{target.amount} {target.currency} returned by the bank "
            f"→ reversal {getattr(done, 'amount', '?')}"
        )

    #: ⚠ **STATE WHAT IS AND IS NOT ON THE TENANT**, so the walkthrough can say
    #: which of its steps are real and which are skipped, rather than reporting
    #: a green run over an absent shape (hard-won law 7: a declared blind spot
    #: with no NUMBER attached is indistinguishable from an empty one).
    from apps.billing import models as billing_models

    corrected = billing_models.Invoice.objects.filter(
        tenant_id=tenant.pk, account_id__in=account_ids, corrects_invoice__isnull=False
    ).count()
    reversals = payments_models.Payment.objects.filter(
        tenant_id=tenant.pk,
        account_id__in=account_ids,
        reverses_payment_id__isnull=False,
    ).count()
    bills = billing_models.Invoice.objects.filter(
        tenant_id=tenant.pk, account_id__in=account_ids
    ).count()
    payments = payments_models.Payment.objects.filter(
        tenant_id=tenant.pk, account_id__in=account_ids
    ).count()
    print(
        f"\nwave G fixture on this tenant: {bills} bill(s), {payments} payment(s), "
        f"{reversals} reversal(s), {corrected} corrected bill(s)"
    )
    if corrected == 0:
        print(
            "  ⚠ NO CORRECTED PAIR — single_correction.py is human-owned money "
            "math and this fixture will not drive it. The walkthrough SKIPS "
            "BR-CWP-042 by name rather than passing over an absence."
        )
    print(f"\nsign in as {LANDLORD}, password Pine-Hill-2026!")

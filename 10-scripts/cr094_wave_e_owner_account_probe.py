"""CR-094-BRC01 step 2 wave E — `DEF-MET-5081` / `DEF-MET-5093`, PROVED BY CALLING IT.

WHY THIS EXISTS
---------------
Ten live surfaces asserted that `metering.connections.create_owner_account()`
raises `NotImplementedError("OQ-373")`. `OQ-373` closed on **2026-08-25 →
`BR-MET-116`** and the function has been implemented since. Reading the code is
not proof that it runs, and the whole point of `DEF-MET-5081` is that ten
readings of the code said the opposite of the truth — so this CALLS it, on the
drawn build, with four payload shapes, and prints what comes back.

WHAT IT ESTABLISHES, and both halves matter
-------------------------------------------
1. **`create_owner_account` does not raise.** Not on the wizard's own payload,
   not on an empty one, not on a contact-only one. With a full `contact` +
   `customer.identity` block it runs to `BIZ-STATE
   customers.account.unit_already_occupied` — ie all the way through its own
   logic, refused only by `BR-CUS-1011` because the fixture's common-area unit
   already carries a master account.
2. **`DEF-MET-5093` — the wizard's `owner` block reaches none of it.**
   `NewConnectWizard.tsx` sends `owner: {name, kind, sub_category, email,
   phone}`; `commit_connection` hands that dict straight to this function,
   which reads `contact` and `customer` off it and finds neither. So the owner's
   NAME never reaches the account either, not only the identifier — and
   `BIZ-COMPLETENESS customers.account.identity_kind_required` is what a clerk
   would meet at step 9 today.

⚠ **IT WRITES NOTHING.** Every call is inside a `transaction.atomic()` that is
rolled back by raising, so the demo fixture is not moved: the proof is that the
account was created, not that it survives. The final two lines re-read the
connection and the master-account count to show that.

⚠ **THE ACTOR IS THE PRODUCTION SHAPE, NOT A TEST FIXTURE'S.** It is
`SimpleNamespace(id=…, role=…)`, copied from `metering/api._actor` — with NO
`pk`. A fixture actor wider than the production one is what hid `DEF-BIL-5090`
for weeks (`tests/test_us_met_helpers.staff_actor` returns
`SimpleNamespace(id=, pk=, role=, user=)`), and a probe that used the wide shape
would be proving something no request can do.

HOW TO RUN IT
-------------
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
      DATABASE_URL=postgres://smartbillhub:smartbillhub@localhost:5432/smartbillhub \
      python3 manage.py shell < ../10-scripts/cr094_wave_e_owner_account_probe.py

Measured output on `brazosbend` at 2026-09-12, product 2.239.0:

    CON-26-0117: state=activated common_areas=1 owner_account_id=None
    1 the WIZARD's own owner block  -> BizError BIZ-COMPLETENESS customers.account.identity_kind_required
    2 empty payload                 -> BizError BIZ-COMPLETENESS customers.account.identity_kind_required
    3 contact only                  -> BizError BIZ-COMPLETENESS customers.account.identity_kind_required
    4 contact + customer identity   -> BizError BIZ-STATE customers.account.unit_already_occupied
    owner_account_id final : None   (all four rolled back)
    master accounts final  : 1
"""
from types import SimpleNamespace

from django.db import transaction

from apps.customers import models as cus
from apps.identity import models as ident
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as met
from apps.tenancy import models as ten
from core import errors, tenancy

#: The tenant is named by its SUBDOMAIN and its id is looked up, because an id
#: hardcoded into a script is the first thing to rot when a fixture is reseeded.
TENANT = "brazosbend"
CONNECTION_NO = "CON-26-0117"


class Rollback(Exception):
    """Raised to abort the atomic block once the result has been printed."""


def attempt(label: str, payload: dict, actor: object, connection_id: object) -> None:
    try:
        with transaction.atomic():
            out = w6.create_owner_account(actor, connection_id, payload)
            print(
                f"{label:38s} -> CREATED {out['account_no']} kind={out['kind']} "
                f"commons={out['common_areas_covered']}"
            )
            raise Rollback
    except Rollback:
        pass
    except NotImplementedError as exc:  # what ten surfaces claimed, until 2026-09-12
        print(f"{label:38s} -> NotImplementedError({exc})   <-- DEF-MET-5081's false claim")
    except (errors.BizError, errors.ValidationError) as exc:
        print(
            f"{label:38s} -> {type(exc).__name__} {getattr(exc, 'code', '')} "
            f"{getattr(exc, 'message_key', '')}"
        )


tenant_id = str(ten.Tenant.objects.get(subdomain=TENANT).id)
with tenancy.tenant_context(tenant_id):
    con = work_tables.Connection.objects.get(connection_no=CONNECTION_NO)
    commons = met.Unit.objects.filter(premises_id=con.premises_id, is_common_area=True).count()
    print(
        f"{CONNECTION_NO}: state={con.state} common_areas={commons} "
        f"owner_account_id={con.owner_account_id}"
    )
    print()
    user = ident.User.objects.order_by("email").first()
    actor = SimpleNamespace(id=user.id, role="system_admin")

    #: 1 — EXACTLY what `NewConnectWizard.tsx` sends as `owner`, and what
    #: `commit_connection` step 4 forwards. This is the live path.
    attempt(
        "1 the WIZARD's own owner block",
        {
            "name": "Balcones Holdings LLC",
            "kind": "company",
            "sub_category": "",
            "email": "dev@example.com",
            "phone": "(512) 555-0142",
        },
        actor,
        con.id,
    )
    attempt("2 empty payload", {}, actor, con.id)
    attempt("3 contact only", {"contact": {"full_name": "Balcones Holdings LLC"}}, actor, con.id)
    #: 4 — the shape the door actually wants: `CONTACT_FIELDS` plus
    #: `CUSTOMER_BLOCK_FIELDS` with `IDENTITY_BLOCK_FIELDS_BY_KIND`'s company
    #: evidence. This is what `DEF-MET-5093`'s mapping half has to produce.
    attempt(
        "4 contact + customer identity",
        {
            "contact": {"full_name": "Balcones Holdings LLC", "email": "dev@example.com"},
            "customer": {
                "kind": "company",
                "display_name": "Balcones Holdings LLC",
                "identity": {"tax_id": "74-1234567"},
            },
        },
        actor,
        con.id,
    )

    con.refresh_from_db()
    print()
    print(f"owner_account_id final : {con.owner_account_id}   (all four rolled back)")
    print(f"master accounts final  : {cus.Account.objects.filter(kind='master').count()}")

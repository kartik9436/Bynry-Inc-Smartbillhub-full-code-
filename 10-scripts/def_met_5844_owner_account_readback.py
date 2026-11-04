"""`DEF-MET-5844` — the Add Premises form's owner account, READ BACK from the
database on real PostgreSQL.

WHY THIS EXISTS BESIDE THE SUITE
--------------------------------
`06-backend/tests/test_def_met_5844_add_premises_owner_account.py` runs on
**in-memory SQLite** (`config/settings/test.py` hardcodes it), and two of the
things this defect turns on cannot be observed there at all:

1. **The savepoint (CLAUDE.md hard-won law 14).** SQLite has no aborted-
   transaction state, so the version WITHOUT the nested `transaction.atomic()`
   passes the whole suite and loses the address the first time a real account is
   refused. Section 2 below runs the identical refusal twice, with and without,
   and prints both answers.
2. **The DELTA and the LINK on real data.** *"An account exists on this
   premises"* passes on an account that was already there — the beta holds one
   orphaned master account, `AC-2026-00051` on `P-00059`. Every count here is a
   BEFORE→AFTER on a property created inside the run.

⚠ **IT WRITES NOTHING.** Every section runs inside a `transaction.atomic()` that
is aborted by raising, so the beta is exactly as it was found. The last lines
re-read the counts to show it.

HOW TO RUN IT
-------------
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
      DATABASE_URL=postgres://<user>:<pass>@127.0.0.1:5432/<db> \
      python3 manage.py shell < ../10-scripts/def_met_5844_owner_account_readback.py

Measured on `brazosbend`, 2026-09-19, product 2.308.9, PostgreSQL 16:

    owner Ridge Property LLC  phone=None  customer_id=None  master_account_id=None
    ── 1 · THE FIVE BEHAVIOUR ROWS ──
    owner + type              -> masters 1->1  on premises None  link None  warnings ['refused/customers.account.identity_kind_required']
    owner, no type            -> masters 1->1  on premises None  link None  warnings ['no_account_type']
    free-text name only       -> masters 1->1  on premises None  link None  warnings ['no_typed_owner']
    no owner at all           -> masters 1->1  on premises None  link None  warnings ['no_typed_owner']
    saved twice               -> masters 1->1  second answer == first: True
    ── 2 · LAW 14, THE SAVEPOINT ──
    WITH savepoint            -> the address SURVIVED the refusal: True
    WITHOUT savepoint         -> InternalError: current transaction is aborted, ...
    ── 3 · THE DOOR CREATES AND LINKS WHEN THE PARTY IS IDENTIFIED ──
    identified owner          -> masters 1->2  account AC-2026-00058  link WRITTEN
    ── 4 · THE FOURTH DOOR (Common Areas tab) ──
    POST /accounts/master     -> BizError BIZ-COMPLETENESS customers.account.identity_kind_required
    ── 5 · SAVED TWICE, ON THE BRANCH THAT ACTUALLY CREATES ──
    first address             -> masters 1->2
    second address            -> masters 2->2  same account back: True  link held
    ── LEFT AS FOUND ──
    masters 1 -> 1   premises 79 -> 79   owner link None

**Read rows 1 and 3 together, because that is the finding.** The form now
REACHES the door — before this defect was fixed `warnings` was empty and nothing
was called — and the door creates the account and writes
`premises_owners.master_account_id` the moment the party can be identified.
What stands between the two is `BR-CUS-1024`, which is `OQ-MET-12472` and is the
PO's to settle: `premises_owners` carries no person/company kind and no
identifier, and `premises_owners.customer_id` is ruled out as the path by
`BR-MET-1020`. **Nothing here invents one to get a greener line.**

⚠ **SECTION 4 IS A FINDING ABOUT SOMEBODY ELSE'S SCREEN AND IS NOT THIS LANE'S
TO FIX.** `CommonAreasTab.tsx` — the manual *Create master account* modal on the
property page — posts the same payload shape and meets the same refusal, so the
gate is the product's and not this form's. Filed rather than worked.
"""

from types import SimpleNamespace

from django.db import transaction

from apps.customers import models as cus
from apps.identity import models as ident
from apps.metering import models as met
from apps.metering import premises_owners, seams
from apps.metering import services as S
from apps.tenancy import models as ten
from core import errors, tenancy

TENANT = "brazosbend"
OWNER = "Ridge Property LLC"


class Rollback(Exception):
    """Raised to abort an atomic block once its answer has been printed."""


def _reasons(created):
    out = []
    for warning in created["warnings"]:
        reason = warning.get("reason")
        if reason == S.OWNER_ACCOUNT_REFUSED:
            out.append(f"refused/{warning.get('message_key')}")
        elif reason:
            out.append(reason)
        elif warning.get("code") in (S.OWNER_ACCOUNT_CREATED, S.OWNER_ACCOUNT_ALREADY_LINKED):
            out.append(warning["code"])
    return out


def _snapshot(tenant, owner):
    owner.refresh_from_db()
    return (
        cus.Account.objects.filter(tenant=tenant, kind="master").count(),
        owner.master_account_id,
    )


def row(label, payload, actor, owner, tenant, address):
    """One behaviour row: create through the form's own service, read back, roll
    back. The BEFORE/AFTER is the whole point — see the module docstring."""
    before_masters, _ = _snapshot(tenant, owner)
    try:
        with transaction.atomic():
            created = S.create_premises(actor, {**payload, "address_line": address})
            after_masters, link = _snapshot(tenant, owner)
            on_premises = (
                cus.Account.objects.filter(tenant=tenant, premises_id=created["id"])
                .values_list("account_no", flat=True)
                .first()
            )
            print(
                f"{label:26s}-> masters {before_masters}->{after_masters}  "
                f"on premises {on_premises}  link {link}  warnings {_reasons(created)}"
            )
            raise Rollback()
    except Rollback:
        pass


tenant = ten.Tenant.objects.get(subdomain=TENANT)
with tenancy.tenant_context(str(tenant.id)):
    user = ident.User.objects.filter(tenant=tenant).order_by("created_at").first()
    actor = SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)
    owner = met.PremisesOwner.objects.filter(tenant=tenant, name=OWNER).first()
    start_masters = cus.Account.objects.filter(tenant=tenant, kind="master").count()
    start_premises = met.Premises.objects.filter(tenant=tenant).count()
    print(
        f"owner {owner.name}  phone={owner.phone}  customer_id={owner.customer_id}  "
        f"master_account_id={owner.master_account_id}"
    )

    print("── 1 · THE FIVE BEHAVIOUR ROWS ──")
    typed = {"premises_type": "single_family", "owner_id": str(owner.id),
             "owner_manager": OWNER}
    row("owner + type", {**typed, "owner_account_type": "residential"},
        actor, owner, tenant, "9501 Readback Way")
    row("owner, no type", typed, actor, owner, tenant, "9503 Readback Way")
    row("free-text name only",
        {"premises_type": "single_family", "owner_manager": OWNER,
         "owner_account_type": "residential"},
        actor, owner, tenant, "9505 Readback Way")
    row("no owner at all", {"premises_type": "single_family"},
        actor, owner, tenant, "9507 Readback Way")

    # ── saved twice — the idempotency claim nobody ever walks ────────────────
    try:
        with transaction.atomic():
            before_masters, _ = _snapshot(tenant, owner)
            first = S.create_premises(
                actor, {**typed, "owner_account_type": "residential",
                        "address_line": "9509 Readback Way"})
            second = S.create_premises(
                actor, {**typed, "owner_account_type": "residential",
                        "address_line": "9509 Readback Way"})
            after_masters, _ = _snapshot(tenant, owner)
            print(f"{'saved twice':26s}-> masters {before_masters}->{after_masters}  "
                  f"second answer == first: "
                  f"{first['owner_master_account'] == second['owner_master_account']}")
            raise Rollback()
    except Rollback:
        pass

    # ── 2 · LAW 14 ──────────────────────────────────────────────────────────
    print("── 2 · LAW 14, THE SAVEPOINT ──")

    def door_that_names_a_duplicate(actor, owner_id, premises_id, payload=None):
        """A refusal raised AFTER a failed statement — the shape every
        catch-the-IntegrityError-and-name-it refusal in this repo takes."""
        from django.db import connection

        try:
            with connection.cursor() as cur:
                cur.execute("INSERT INTO premises (id) VALUES (NULL)")
        except Exception:
            raise errors.BizError(
                errors.BIZ_STATE, br_ref="BR-CUS-1011",
                message_key="customers.account.premises_already_has_master",
            ) from None

    def without_savepoint(actor, row_, data, warnings):
        try:
            return premises_owners.ensure_owner_master_account(
                actor, row_.owner_id, row_.pk,
                {"account_type": "residential", "opened_at": str(seams.tenant_today())},
            )
        except (errors.ApiError, errors.NotFoundError) as refusal:
            warnings.append({"code": "refused",
                             "message_key": getattr(refusal, "message_key", None)})
            return None

    real_door = premises_owners.ensure_owner_master_account
    premises_owners.ensure_owner_master_account = door_that_names_a_duplicate
    try:
        for label, fn in (("WITH savepoint", S._ensure_owner_master_account),
                          ("WITHOUT savepoint", without_savepoint)):
            keep = S._ensure_owner_master_account
            S._ensure_owner_master_account = fn
            try:
                with transaction.atomic():
                    created = S.create_premises(
                        actor, {**typed, "owner_account_type": "residential",
                                "address_line": "9511 Readback Way"})
                    alive = met.Premises.objects.filter(pk=created["id"]).exists()
                    print(f"{label:26s}-> the address SURVIVED the refusal: {alive}")
                    raise Rollback()
            except Rollback:
                pass
            except Exception as blew_up:
                first_line = str(blew_up).strip().splitlines()[0][:96]
                print(f"{label:26s}-> {type(blew_up).__name__}: {first_line}")
            finally:
                S._ensure_owner_master_account = keep
    finally:
        premises_owners.ensure_owner_master_account = real_door

    # ── 3 · THE DOOR, WITH THE PARTY IDENTIFIED ─────────────────────────────
    # ⚠ **THIS CALLS THE DOOR DIRECTLY AND SAYS SO.** The form cannot reach this
    # branch — it collects no identity, which is `OQ-MET-12472` — so this proves
    # the PLUMBING rather than the screen: given an identified party, the door
    # creates the account and writes the declared link. Read it beside row 1.
    print("── 3 · THE DOOR CREATES AND LINKS WHEN THE PARTY IS IDENTIFIED ──")
    try:
        with transaction.atomic():
            before_masters, _ = _snapshot(tenant, owner)
            made = S.create_premises(
                actor, {**typed, "address_line": "9513 Readback Way"})
            answer = premises_owners.ensure_owner_master_account(
                actor, owner.id, made["id"],
                {
                    "account_type": "commercial",
                    "opened_at": str(seams.tenant_today()),
                    "customer": {"display_name": OWNER, "kind": "company",
                                 "identity": {"tax_id": "74-3182640"}},
                },
            )
            after_masters, link = _snapshot(tenant, owner)
            account_no = (
                cus.Account.objects.filter(tenant=tenant, premises_id=made["id"])
                .values_list("account_no", flat=True)
                .first()
            )
            print(f"{'identified owner':26s}-> masters {before_masters}->{after_masters}  "
                  f"account {account_no}  link "
                  f"{'WRITTEN' if link and str(link) == str(answer['master_account_id']) else link}")
            raise Rollback()
    except Rollback:
        pass

    # ── 4 · THE FOURTH DOOR ─────────────────────────────────────────────────
    # `CommonAreasTab.tsx` posts to `POST /accounts/master`, which is
    # `customers.create_master_account` with `require_identity` at its default.
    # Asked here with that screen's own payload shape.
    print("── 4 · THE FOURTH DOOR (Common Areas tab) ──")
    from apps.customers import services as cus_services

    try:
        with transaction.atomic():
            made = S.create_premises(
                actor, {**typed, "address_line": "9515 Readback Way"})
            try:
                cus_services.create_master_account(
                    actor,
                    {"premises_id": made["id"], "account_type": "residential",
                     "opened_at": str(seams.tenant_today())},
                )
            except errors.ApiError as refusal:
                print(f"{'POST /accounts/master':26s}-> {type(refusal).__name__} "
                      f"{getattr(refusal, 'code', '')} "
                      f"{getattr(refusal, 'message_key', '')}")
            else:
                print(f"{'POST /accounts/master':26s}-> created")
            raise Rollback()
    except Rollback:
        pass

    # ── 5 · IDEMPOTENCY ON THE BRANCH THE SCREEN CANNOT REACH ──────────────
    # ⚠ **THE WALKTHROUGH CANNOT PROVE THIS AND SAYS SO.** On beta data both
    # saves refuse, so *the second opened no second account* is true of two
    # nulls — a check that passes wrongly (law 7). Here the party IS identified,
    # so the first address really does open an account, and the SECOND address
    # for the same owner must hand back that same account and write nothing.
    print("── 5 · SAVED TWICE, ON THE BRANCH THAT ACTUALLY CREATES ──")
    try:
        with transaction.atomic():
            before_masters, _ = _snapshot(tenant, owner)
            identified = {
                "account_type": "commercial",
                "opened_at": str(seams.tenant_today()),
                "customer": {"display_name": OWNER, "kind": "company",
                             "identity": {"tax_id": "74-3182640"}},
            }
            one = S.create_premises(actor, {**typed, "address_line": "9517 Readback Way"})
            first_answer = premises_owners.ensure_owner_master_account(
                actor, owner.id, one["id"], identified)
            mid_masters, _ = _snapshot(tenant, owner)
            two = S.create_premises(actor, {**typed, "address_line": "9519 Readback Way"})
            second_answer = premises_owners.ensure_owner_master_account(
                actor, owner.id, two["id"], identified)
            end_masters, link = _snapshot(tenant, owner)
            same = first_answer["master_account_id"] == second_answer["master_account_id"]
            print(f"{'first address':26s}-> masters {before_masters}->{mid_masters}")
            print(f"{'second address':26s}-> masters {mid_masters}->{end_masters}  "
                  f"same account back: {same}  link {'held' if link else 'MISSING'}")
            raise Rollback()
    except Rollback:
        pass

    print("── LEFT AS FOUND ──")
    owner.refresh_from_db()
    print(f"masters {start_masters} -> "
          f"{cus.Account.objects.filter(tenant=tenant, kind='master').count()}")
    print(f"premises {start_premises} -> "
          f"{met.Premises.objects.filter(tenant=tenant).count()}")
    print(f"owner link {owner.master_account_id}")

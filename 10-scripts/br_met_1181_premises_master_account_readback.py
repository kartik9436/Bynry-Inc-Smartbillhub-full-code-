"""`BR-MET-1181` / `DEF-MET-6139` — a premises names its master account, READ BACK
from a real PostgreSQL database.

WHY THIS EXISTS BESIDE THE SUITE
--------------------------------
`06-backend/tests/test_br_met_1181_premises_master_account.py` runs on **in-memory
SQLite** (`config/settings/test.py` hardcodes it), and three of the things this
change turns on cannot be observed there at all:

1. **The savepoint (CLAUDE.md hard-won law 14).** SQLite has no aborted-
   transaction state, so the version WITHOUT the nested `transaction.atomic()`
   passes the whole suite and loses the address the first time a real account is
   refused. Section 3 below runs the identical refusal twice, with and without,
   and prints both answers.
2. **That the migration reaches a real column.** A migration that applies on
   SQLite is not a migration that applied on PostgreSQL 16 with a live FK.
3. **The BEFORE, on real data.** *"An account exists on this premises"* passes
   on an account that was already there. Every count here is a BEFORE→AFTER on a
   property created inside the run.

⚠ **IT WRITES NOTHING.** Every section runs inside a `transaction.atomic()` that
is aborted by raising, so the database is exactly as it was found. The last lines
re-read the counts to show it.

HOW TO RUN IT
-------------
    10-scripts/proof-db.sh clone c1owner
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
      DATABASE_URL=postgres://<user>:<pass>@127.0.0.1:5432/sbh_clone_c1owner \
      python3 manage.py migrate metering
    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
      DATABASE_URL=... python3 manage.py shell \
        < ../10-scripts/br_met_1181_premises_master_account_readback.py

⚠ **RUN IT AGAINST A DATABASE NOBODY ELSE IS SEEDING** — a mid-run reseed looks
exactly like a broken screen. `proof-db.sh clone` gives you a private one.

MEASURED 2026-09-22 ON A CLONE OF `brazosbend`, POSTGRESQL 16, PRODUCT 2.324.0
------------------------------------------------------------------------------

    FOUND  premises 79  master accounts 1  owner records 5
           properties with an owner account the money path can find: 0
    -- 1 . THE REPORTED CASE, BOTH KINDS --
      person + SSN      -> masters 1->2  account AC-2026-00052  source premises
                           column WRITTEN  owner records 5  [owner_account_created]
      company + Tax ID  -> masters 1->2  account AC-2026-00052  source premises
                           column WRITTEN  owner records 5  [owner_account_created]
    -- 2 . THE PRECEDENCE, ON REAL ROWS --
      both columns set      -> source premises      (premises wins: True)
      pre-ruling row only   -> source owner_record  (owner record answers: True)
      only accounts.premises_id (1 account) -> answer None   <- never promoted
    -- 3 . LAW 14, THE SAVEPOINT --
      WITH savepoint    -> the address SURVIVED the refusal: True
      WITHOUT savepoint -> InternalError: current transaction is aborted,
                           commands ignored until end of transaction block
    -- 4 . ATTACHING AN ACCOUNT THAT ALREADY EXISTS --
      attach an existing -> masters 2->2  [owner_account_attached]
      attach an ORDINARY -> [refused/metering.premises.master_account_unknown]
    -- 5 . WHAT THE LIST COSTS --
      6 rows on one page -> 1 account read, 6 numbers drawn, expanded False
    -- LEFT AS FOUND --
      premises 79   master accounts 1   owner records 5   declared links 0

**Read lines 1 and 3 together, because that is the finding.** The form now opens
the account from what a clerk actually typed, with **no owner record created**
(5 -> 5) — and the savepoint is the reason a refusal on that path costs the
address nothing. Section 5 is the other one worth reading: **six rows, one
account read.** A per-row expansion would have been six, and on a page of fifty
it would be fifty — which is `DEF-324` exactly.
"""

from types import SimpleNamespace

from django.db import transaction

from apps.customers import models as cus
from apps.identity import models as ident
from apps.metering import models as met
from apps.metering import premises_owners
from apps.metering import services as S
from apps.tenancy import models as ten
from core import errors, tenancy

TENANT = "brazosbend"

PERSON = {
    "owner_manager": "Harriet Vane",
    "owner_kind": "person",
    "owner_ssn": "412558899",
    "owner_account_type": "residential",
}
COMPANY = {
    "owner_manager": "Ridge Property LLC",
    "owner_kind": "company",
    "owner_tax_id": "74-3182640",
    "owner_account_type": "commercial",
}


class Rollback(Exception):
    """Raised to abort an atomic block once its answer has been printed."""


def _reasons(created):
    out = []
    for warning in created.get("warnings") or []:
        reason = warning.get("reason")
        if reason == S.OWNER_ACCOUNT_REFUSED:
            out.append(f"refused/{warning.get('message_key')}")
        elif reason:
            out.append(f"{reason}/{warning.get('message_key')}")
        elif warning.get("code"):
            out.append(f"{warning['code']}/{warning.get('message_key')}")
    return out


tenant = ten.Tenant.objects.get(subdomain=TENANT)
with tenancy.tenant_context(str(tenant.id)):
    user = ident.User.objects.filter(tenant=tenant).order_by("created_at").first()
    actor = SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)

    premises_qs = met.Premises.objects.filter(tenant=tenant, deleted_at__isnull=True)
    masters = cus.Account.objects.filter(tenant=tenant, kind="master")
    start_masters = masters.count()
    start_premises = premises_qs.count()
    declared = premises_qs.filter(master_account__isnull=False).count()
    via_owner = premises_qs.filter(
        master_account__isnull=True, owner__master_account__isnull=False
    ).count()
    print(
        f"FOUND  premises {start_premises}  master accounts {start_masters}  "
        f"owner records {met.PremisesOwner.objects.filter(tenant=tenant).count()}"
    )
    print(
        f"       properties with an owner account the money path can find: "
        f"{declared + via_owner}  (premises {declared} · owner record {via_owner})"
    )

    print("── 1 · THE REPORTED CASE, BOTH KINDS ──")
    for label, payload, address in (
        ("person + SSN", PERSON, "9601 Readback Row"),
        ("company + Tax ID", COMPANY, "9603 Readback Row"),
    ):
        try:
            with transaction.atomic():
                before = masters.count()
                created = S.create_premises(actor, {**payload, "address_line": address})
                row = met.Premises.objects.get(pk=created["id"])
                print(
                    f"  {label:20s}-> masters {before}->{masters.count()}  "
                    f"account {created['master_account_no']}  "
                    f"source {created['master_account_source']}  "
                    f"column {'WRITTEN' if row.master_account_id else 'NULL'}  "
                    f"owner records {met.PremisesOwner.objects.filter(tenant=tenant).count()}  "
                    f"{_reasons(created)}"
                )
                raise Rollback()
        except Rollback:
            pass

    print("── 2 · THE PRECEDENCE, ON REAL ROWS ──")
    try:
        with transaction.atomic():
            first = S.create_premises(
                actor, {**PERSON, "address_line": "9605 Readback Row"}
            )
            other = S.create_premises(
                actor, {**COMPANY, "address_line": "9607 Readback Row"}
            )
            owner = premises_owners.create_premises_owner(
                actor, {"name": "Vane Estates (readback)", "category": "landlord"}
            )
            met.PremisesOwner.objects.filter(pk=owner["id"]).update(
                master_account_id=other["master_account_id"]
            )
            met.Premises.objects.filter(pk=first["id"]).update(owner_id=owner["id"])
            answer, source = premises_owners.premises_master_account_link(first["id"])
            print(
                f"  both columns set     -> answer {str(answer)[:8]}  source {source}  "
                f"(premises wins: {str(answer) == first['master_account_id']})"
            )
            met.Premises.objects.filter(pk=first["id"]).update(master_account_id=None)
            answer, source = premises_owners.premises_master_account_link(first["id"])
            print(
                f"  pre-ruling row only  -> answer {str(answer)[:8]}  source {source}  "
                f"(owner record answers: {str(answer) == other['master_account_id']})"
            )
            # `accounts.premises_id` is STILL set on `first` — precedence 3 —
            # and must not answer once both declarations are gone.
            met.Premises.objects.filter(pk=first["id"]).update(owner_id=None)
            covers = cus.Account.objects.filter(
                tenant=tenant, premises_id=first["id"]
            ).count()
            answer, source = premises_owners.premises_master_account_link(first["id"])
            print(
                f"  only accounts.premises_id ({covers} account(s)) -> answer {answer}  "
                f"source {source}   <- never promoted"
            )
            raise Rollback()
    except Rollback:
        pass

    print("── 3 · LAW 14, THE SAVEPOINT ──")

    def refusing_door(actor_, premises_id, payload=None):
        """A refusal raised AFTER a failed statement — the shape every
        catch-the-IntegrityError-and-name-it refusal in this repo takes."""
        from django.db import connection

        try:
            with connection.cursor() as cur:
                cur.execute("INSERT INTO premises (id) VALUES (NULL)")
        except Exception:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-CUS-1011",
                message_key="customers.account.premises_already_has_master",
            ) from None

    def without_savepoint(actor_, row, data, warnings):
        try:
            return refusing_door(actor_, row.pk, {})
        except (errors.ApiError, errors.NotFoundError) as refusal:
            warnings.append(
                {"code": "refused", "message_key": getattr(refusal, "message_key", None)}
            )
            return None

    def with_savepoint(actor_, row, data, warnings):
        try:
            with transaction.atomic():
                return refusing_door(actor_, row.pk, {})
        except (errors.ApiError, errors.NotFoundError) as refusal:
            warnings.append(
                {"code": "refused", "message_key": getattr(refusal, "message_key", None)}
            )
            return None

    for label, stand_in in (("WITH savepoint", with_savepoint), ("WITHOUT savepoint", without_savepoint)):
        real = S._ensure_owner_master_account
        S._ensure_owner_master_account = stand_in
        try:
            with transaction.atomic():
                created = S.create_premises(
                    actor, {**PERSON, "address_line": f"9609 Readback Row {label[:4]}"}
                )
                survived = met.Premises.objects.filter(pk=created["id"]).exists()
                print(f"  {label:20s}-> the address SURVIVED the refusal: {survived}")
                raise Rollback()
        except Rollback:
            pass
        except Exception as exc:  # noqa: BLE001 — the point of the section
            print(f"  {label:20s}-> {type(exc).__name__}: {str(exc).splitlines()[0][:90]}")
        finally:
            S._ensure_owner_master_account = real

    print("── 4 · ATTACHING AN ACCOUNT THAT ALREADY EXISTS ──")
    try:
        with transaction.atomic():
            holder = S.create_premises(actor, {**COMPANY, "address_line": "9611 Readback Row"})
            plain = S.create_premises(actor, {"address_line": "9613 Readback Row"})
            before = masters.count()
            attached = S.update_premises(
                actor, plain["id"], {"master_account_id": holder["master_account_id"]}
            )
            print(
                f"  attach an existing   -> masters {before}->{masters.count()}  "
                f"account {attached['master_account_no']}  "
                f"source {attached['master_account_source']}  {_reasons(attached)}"
            )
            ordinary = (
                cus.Account.objects.filter(tenant=tenant).exclude(kind="master").first()
            )
            refused = S.update_premises(
                actor, plain["id"], {"master_account_id": str(ordinary.id)}
            )
            print(
                f"  attach an ORDINARY   -> declared {refused['master_account_id']}  "
                f"{_reasons(refused)}"
            )
            raise Rollback()
    except Rollback:
        pass

    print("── 5 · WHAT THE LIST COSTS ──")
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from apps.metering import selectors

    try:
        with transaction.atomic():
            for n in range(6):
                S.create_premises(
                    actor, {**PERSON, "address_line": f"96{20 + n} Readback Row"}
                )
            rows = list(
                met.Premises.objects.filter(
                    tenant=tenant, address_line__startswith="962"
                ).select_related("owner")
            )
            with CaptureQueriesContext(connection) as captured:
                numbers = selectors.premises_master_account_numbers(rows)
                served = [
                    selectors.premises_detail_dict(
                        row, with_owner_account=False, master_account_numbers=numbers
                    )
                    for row in rows
                ]
            account_reads = [
                q for q in captured.captured_queries if " FROM \"accounts\"" in q["sql"]
            ]
            drawn = [s["master_account_no"] for s in served if s["master_account_no"]]
            print(
                f"  {len(rows)} rows on one page -> {len(account_reads)} account read(s), "
                f"{len(drawn)} number(s) drawn, expanded "
                f"{served[0]['master_account_expanded'] if served else 'n/a'}"
            )
            raise Rollback()
    except Rollback:
        pass

    print("── LEFT AS FOUND ──")
    print(
        f"  premises {premises_qs.count()}   master accounts {masters.count()}   "
        f"owner records {met.PremisesOwner.objects.filter(tenant=tenant).count()}   "
        f"declared links {premises_qs.filter(master_account__isnull=False).count()}"
    )

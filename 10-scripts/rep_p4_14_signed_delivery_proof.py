"""`P4.14` END TO END ON REAL PostgreSQL: a file goes out by signed link, and
an expired one and another tenant's one are both refused.

`CR-142-BRC07` `P4.14`. Run against a PROOF CLONE — it writes a destination, a
schedule and a delivery row, so never point it at a database anybody is using.

    ./10-scripts/proof-db.sh clone p414
    DATABASE_URL=... PYTHONPATH=06-backend \\
      06-backend/.venv/bin/python 10-scripts/rep_p4_14_signed_delivery_proof.py

⚠ **CHECK 8 IS THE ONE THAT NEEDS A REAL SERVER.** It calls `deliver` twice for
one `(schedule, job, destination)` and asserts the second writes nothing —
which exercises the `except IntegrityError` inside a nested `atomic()`.
CLAUDE.md hard-won law 14 is exactly this case: on SQLite there is no aborted-
transaction state, so the version WITHOUT the savepoint passes the whole suite
green and loses the work at COMMIT the first time two beats overlap in
production. It cannot be proved anywhere but here.

⚠ **THE HTTP HALF IS A SEPARATE ARTEFACT** — `scratchpad/po-shots/p4-last/
03-p414-signed-link-over-http.txt` — because fetching the link needs a running
server and this script needs none.
"""
import os, django, json, uuid
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings.local"); django.setup()
from datetime import UTC, datetime, timedelta
from apps.reports import destinations, models as rm, signed_links
from apps.tenancy.models import Tenant
from core import errors
from core.tenancy import tenant_context

fails = 0
def check(label, ok, detail=""):
    global fails
    if not ok: fails += 1
    print(f"{'PASS' if ok else 'FAIL'}  {label}{' — '+detail if detail else ''}")

t = Tenant.objects.order_by("created_at").first()
other = Tenant.objects.order_by("created_at")[1]
NOW = datetime(2026, 9, 27, 9, 0, tzinfo=UTC)

with tenant_context(t.id):
    # 1 · an administrator sets a destination up
    # ⚠ **NOT DELETED AND RE-CREATED, BECAUSE `PROTECT` CORRECTLY REFUSES.**
    # The first draft of this script deleted the destination each run and the
    # second run died on `ProtectedError` — a destination that has DELIVERED
    # something may not be removed out from under its own record. That is the
    # model doing its job (`on_delete=PROTECT` on `ReportDelivery.destination`),
    # so the script re-uses the row instead of fighting it.
    dest = rm.ReportDestination.objects.filter(
        tenant_id=t.id, name="BI collector", kind=rm.DESTINATION_LINK
    ).first() or destinations.create(
        t.id, name="BI collector", kind=rm.DESTINATION_LINK, actor_user_id=None
    )
    check("1 · an administrator's destination exists", dest.pk is not None,
          f"kind={dest.kind}")

    # 2 · SFTP is refused BY NAME with the open question
    try:
        destinations.create(t.id, name="SFTP drop", kind=rm.DESTINATION_SFTP,
                            actor_user_id=None)
        check("2 · SFTP is refused at create", False, "it was ACCEPTED")
    except errors.BizError as e:
        check("2 · SFTP is refused at create, naming the open question",
              e.params.get("question") == "OQ-REP-12767", str(e.params))

    # 3 · a link (since 2026-10-02 the file itself is an S3 object, found through
    #     its `job_artifacts` row — this proof is about the TOKEN, not the bytes)
    job_id = uuid.uuid4()
    token, expires = signed_links.mint(tenant_id=t.id, job_id=job_id, now=NOW)
    check("3 · a link was minted", token.startswith("sbhrd1."),
          f"expires {expires.isoformat()} — {int((expires-NOW).total_seconds())}s")

    # 4 · it verifies to THIS tenant and THIS job, and nothing else
    claim = signed_links.verify(token, now=NOW)
    check("4 · it resolves to one tenant and one job",
          claim == {"tenant_id": str(t.id), "job_id": str(job_id)}, json.dumps(claim))

    # 5 · FOUR HOURS, and the number is the PO's, read from where it lives
    from apps.tenancy import document_storage
    check("5 · the TTL is document_storage's ruled figure, not a copy",
          signed_links.ttl_seconds() == document_storage.url_ttl_seconds()
          and (expires - NOW) == timedelta(seconds=document_storage.url_ttl_seconds()),
          f"{document_storage.url_ttl_seconds()}s = {document_storage.url_ttl_seconds()//3600}h")

    # 6 · EXPIRED is refused
    try:
        signed_links.verify(token, now=expires + timedelta(seconds=1))
        check("6 · an expired link is refused", False, "it was ACCEPTED")
    except errors.NotFoundError:
        check("6 · an expired link is refused", True,
              "one second past its own expiry")

    # 7 · ANOTHER TENANT's link is refused — the tenant is inside the signature
    foreign, _ = signed_links.mint(tenant_id=other.id, job_id=job_id, now=NOW)
    fc = signed_links.verify(foreign, now=NOW)
    check("7 · a link minted for another tenant resolves to THAT tenant",
          fc["tenant_id"] == str(other.id) != str(t.id), fc["tenant_id"])
    # and editing ours to name theirs breaks the signature
    import base64
    prefix, body, sig = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(body + "="*(-len(body)%4)))
    payload["t"] = str(other.id)
    nb = base64.urlsafe_b64encode(json.dumps(payload, separators=(",",":"),
        sort_keys=True).encode()).decode().rstrip("=")
    try:
        signed_links.verify(f"{prefix}.{nb}.{sig}", now=NOW)
        check("7 · a link RE-POINTED at another tenant is refused", False, "ACCEPTED")
    except errors.NotFoundError:
        check("7 · a link RE-POINTED at another tenant is refused", True,
              "the tenant is inside the signature")

    # 8 · the delivery is RECORDED, and a second beat does not send it twice
    sched = rm.ReportSchedule.objects.filter(tenant_id=t.id).first()
    if sched is None:
        # The seeded fixture holds no schedule. Create one through the model so
        # the idempotency half is PROVED rather than claimed in a docstring —
        # a FIXTURE gap must not become an untested assertion.
        definition = rm.ReportDefinition.objects.filter(key="statement").first() \
                     or rm.ReportDefinition.objects.first()
        sched = rm.ReportSchedule.objects.create(
            tenant_id=t.id, definition=definition, cadence="monthly",
            params={}, format="csv", recipients=[],
        )
        print(f"   (created a schedule for the proof: {sched.pk})")
    if False:
        pass
    else:
        # a FRESH job id each run, so nothing has to be deleted
        rm.ReportDelivery.objects.filter(schedule=sched, job_id=job_id).delete()
        sched.destination = dest; sched.save(update_fields=["destination"])
        first = destinations.deliver(sched, job_id=job_id, now=NOW)
        second = destinations.deliver(sched, job_id=job_id, now=NOW)
        rows = rm.ReportDelivery.objects.filter(schedule=sched, job_id=job_id).count()
        check("8 · delivered once, and the second beat writes nothing",
              first is not None and second is None and rows == 1,
              f"rows={rows} (hard rule 6 — the DATABASE refuses the second, not a memory of it)")
        check("8 · the delivery row records when the link dies",
              first.expires_at == expires, str(first.expires_at))

print()
print(f"{fails} FAILURE(S)" if fails else "all checks passed")
raise SystemExit(1 if fails else 0)

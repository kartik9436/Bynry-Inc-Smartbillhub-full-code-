"""Purge the drafts `po20260919_request_steps_1_and_3_walkthrough.mjs` saved.

⚠ **A WALK THAT LEAVES ROWS BEHIND MAKES THE NEXT PERSON'S BETA LIE TO THEM.**
The browser walk goes through HTTP, so every save really commits and it cannot
roll itself back. Proving that `units_on_property` reaches the COLUMN cannot be
done from the screen — the screen is where a wrong answer looks right — so the
walk saves exactly one draft per run and this removes it.

**It deletes by the run's own tag and nothing else.** Every request the walk
saves carries an applicant name beginning `W1AND3-` followed by that run's
timestamp, so this cannot reach a row a person made: no clerk types that prefix.
It refuses to run without one.

    cd 06-backend && DJANGO_SETTINGS_MODULE=config.settings.local \
      DATABASE_URL=postgres://<user>:<pass>@127.0.0.1:5432/<db> \
      REQ_PURGE=W1AND3- \
      python3 manage.py shell < ../10-scripts/po20260919_request_steps_purge.py

`REQ_PURGE=W1AND3-` purges every run's leftovers at once; a fuller tag purges
one run.

⚠ **IT ONLY EVER TOUCHES A `draft`, AND IT SAYS SO IF IT FINDS ANYTHING ELSE.**
`CLAUDE.md` hard rule 4 freezes issued invoices, invoice lines, payments and
journal entries; a service request that was never submitted has none of those,
and the walk never presses Submit. A tagged row in any other state means
somebody carried the walk's draft forward by hand — that is a real request now,
so this prints it and leaves it.

⚠ **IT PRINTS WHAT IT FOUND BEFORE IT REMOVES ANYTHING**, so a surprise is
visible rather than silent.
"""
import os
import sys

from django.db import connection

from apps.customers import models
from apps.tenancy.models import Tenant

TAG = os.environ.get("REQ_PURGE", "").strip()
if not TAG:
    sys.exit("REFUSED: set REQ_PURGE to the walk's tag (e.g. REQ_PURGE=W1AND3-).")
if not TAG.startswith("W1AND3-"):
    sys.exit(f"REFUSED: {TAG!r} is not one of this walk's tags; it must begin W1AND3-.")

removed = 0
for tenant in Tenant.objects.all():
    with connection.cursor() as cur:
        cur.execute("SET app.tenant_id = %s", [str(tenant.id)])
    rows = list(models.ServiceRequest.objects.filter(applicant_name__startswith=TAG))
    for row in rows:
        print(f"  {tenant.name}: {row.request_no} · {row.state} · {row.applicant_name}")
    keep = [r for r in rows if r.state != "draft"]
    for row in keep:
        print(f"  LEFT ALONE (not a draft, so somebody took it forward): {row.request_no}")
    drafts = [r for r in rows if r.state == "draft"]
    for row in drafts:
        # ⚠ **EVERY CHILD IS `PROTECT`ED, SO EACH ONE IS NAMED HERE RATHER
        # THAN CASCADED.** A first draft deleted only the services and the
        # documents and raised on `ServiceRequestEvent` — which is the right
        # behaviour from the model: a request's own history is not something a
        # cascade should quietly take. These are a walk-made draft's own rows
        # and go with it; if a new child table is added, this raises by name
        # rather than leaving an orphan.
        models.ServiceRequestService.objects.filter(request=row).delete()
        models.ServiceRequestDocument.objects.filter(request=row).delete()
        models.ServiceRequestFee.objects.filter(request=row).delete()
        models.ServiceRequestEvent.objects.filter(request=row).delete()
        row.delete()
        removed += 1

print(f"removed {removed} draft(s) tagged {TAG}")
with connection.cursor() as cur:
    for tenant in Tenant.objects.all():
        cur.execute("SET app.tenant_id = %s", [str(tenant.id)])
        cur.execute("SELECT count(*) FROM service_requests")
        print(f"{tenant.name}: {cur.fetchone()[0]} service request(s) remain")

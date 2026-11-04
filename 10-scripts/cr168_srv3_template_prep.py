"""CR-168-BRC10 round 4, lane SRV-3 — give the demo's templates an instruction
and a link, so the recorded answers carry the shapes the TEMPLATES lane draws.

Run inside `manage.py shell` against a SCRATCH database seeded with `seed_demo`
+ `load_sample_data --tenant brazosbend`, BEFORE `cr168_order_page_seed.py`
(so the job it raises copies the instruction onto its checklist):

    python manage.py shell < ../10-scripts/cr168_srv3_template_prep.py

On *Meter exchange — residential* (the job the drawings were captured on) and
on the first published template in the list's order, through the builder's own
write (`templates_svc.replace_collection`, audited):

  * the FIRST task gains *Isolate at the main before touching.* (PO answer 3's
    worked example) — the other tasks are kept exactly as they were;
  * the help pack gains a LINK row, *How to fit a meter (video)*,
    `https://www.youtube.com/watch?v=dQw4w9WgXcQ` (ruling 6) — kept rows stay.

Writes nothing else. Prints what it changed.
"""
from apps.identity.models import User
from apps.tenancy.models import Tenant
from apps.work import selectors, templates_svc
from core import tenancy as ct

INSTRUCTION = "Isolate at the main before touching."
LINK = {"kind": "link", "label": "How to fit a meter (video)",
        "link": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}

tenant = Tenant.objects.get(subdomain="brazosbend")
with ct.tenant_context(tenant.id):
    dana = User.objects.filter(email__startswith="dana").first()
    listed = selectors.templates_page(per=1000)["rows"]
    chosen = [r for r in listed if r["name"].startswith("Meter exchange")][:1]
    chosen += [r for r in listed if r["status"] == "published"][:1]
    seen = set()
    for row in chosen:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        bundle = selectors.template(row["id"])["bundle"]
        tasks = [dict(t) for t in bundle["tasks"]]
        if tasks:
            tasks[0]["instruction"] = INSTRUCTION
            templates_svc.replace_collection(dana, row["id"], "tasks", tasks)
        help_rows = [
            {"kind": h["kind"], "label": h["label"], "ref": h["ref"]} for h in bundle["help"]
        ]
        if not any(h["kind"] == "link" for h in help_rows):
            help_rows.append(LINK)
            templates_svc.replace_collection(dana, row["id"], "help", help_rows)
        print(f"{row['name']}: {len(tasks)} task(s), first instructed; {len(help_rows)} help row(s) incl. a link")

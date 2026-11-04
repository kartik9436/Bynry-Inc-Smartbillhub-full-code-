"""Demo script C, step 6's fixture — the TERMINAL half of the CR-070 wave C
walkthrough, run before `cr070-c-settings-tell-the-truth.mjs` clicks the screen.

⚠ **WHY THIS FILE EXISTS, AND WHAT IT IS STANDING IN FOR.** `10-execution-plan.md`
task C3 names a parts fixture — *`MTR-E1P` `96.0000` · `SEAL-01` `0.2200` ·
`MTR-W58` `92.4000` · `GSKT-STD`* — and **no seeder in this repository plants
it.** `apps/tenancy/sample_data.py`'s `SAMPLE_MODULES` has no `work` entry, so
`load_sample_data` leaves the register empty. The five LOOKUP lists (job types,
priorities, skills, safety kits, parts categories) do seed, through
`apps/work/services.seed_reference_list` at provisioning; `parts` is a REGISTER
and not a lookup list, so nothing seeds it.

This file is the same answer wave A gave to the same problem
(`cr070-a-terminal.py`, `DEF-WRK-3633`): a fixture the walkthrough needs, IN THE
REPOSITORY, so the proof is reproducible by somebody who is not its author.
**The proper home is a `work` sample module**, which would seed these four for
every lane and every demo; that is recorded as owed rather than done here,
because `SAMPLE_MODULES` is a shared registry whose prose count three other
gates already read, and a lane adding a twentieth entry in passing is how that
file's count goes wrong (G72 is RED on it today).

⚠ **RUN IT, OR THE WALKTHROUGH FAILS CHECKS THAT READ LIKE A BROKEN SCREEN** —
an empty register, no `$96.00`, and no answer for the four-decimals-stored
assertion. That is exactly the trap wave A's header warns about in capitals.

HOW TO RUN IT
-------------
    DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL="postgres://…/sbh_clone_cr070c" \
      python 06-backend/manage.py shell -c "$(cat 10-scripts/render-checks/cr070-c-terminal.py)"

It is IDEMPOTENT, and that covers BOTH directions: every part number it plants
is deleted first, AND the `Backflow` skill the walkthrough itself adds is
removed. Running it before every walkthrough leaves exactly four parts and
eight skills, so the browser reads the same numbers on the first run and the
fiftieth.

WHAT IT PRINTS WHEN IT IS RIGHT
-------------------------------
    tenant: Brazos Bend Utilities
    lists : types=8 priorities=4 skills=8 kits=4 categories=4
    PLANTED MTR-E1P  96.0000
    PLANTED MTR-W58  92.4000
    PLANTED SEAL-01  0.2200
    PLANTED GSKT-STD 4.1500
    register: 4 part(s)
"""

from decimal import Decimal

from apps.tenancy.models import Tenant
from apps.work import models as work_models, services as work_services
from core import tenancy as core_tenancy

tenant = Tenant.objects.get(subdomain="brazosbend")
print(f"tenant: {tenant.name}")

# The five lookup lists seed at provisioning. A tenant provisioned BEFORE
# work/0001 existed has none, and the walkthrough's first check would then fail
# on an empty Work group rather than on anything this wave built — so say what
# is there before planting anything.
with core_tenancy.tenant_context(tenant.id):
    print(
        "lists : "
        f"types={work_models.WorkOrderType.objects.filter(tenant=tenant).count()} "
        f"priorities={work_models.WorkPriority.objects.filter(tenant=tenant).count()} "
        f"skills={work_models.WorkSkill.objects.filter(tenant=tenant).count()} "
        f"kits={work_models.WorkSafetyKit.objects.filter(tenant=tenant).count()} "
        f"categories={work_models.PartCategory.objects.filter(tenant=tenant).count()}"
    )

    #: C3's fixture. The three prices are the ones the story and the card quote, and
    #: they are quoted at FOUR decimals on purpose: hard rule 2 stores 4 and shows
    #: 2, and the walkthrough asserts both ends of that (`96.0000` on the wire,
    #: `$96.00` on the screen). `GSKT-STD` deliberately carries NO category, so the
    #: register's dash-not-blank rule has something to draw.
    FIXTURE = (
        ("MTR-E1P", "Electric meter · 1φ AMI", "Meters", "each", "96.0000"),
        ("MTR-W58", 'Water meter 5/8" · AMI', "Meters", "each", "92.4000"),
        ("SEAL-01", "Wire seal", "Consumables", "each", "0.2200"),
        ("GSKT-STD", "Gasket set", None, "each", "4.1500"),
    )

    # ⚠ THE WALKTHROUGH ADDS A SKILL, SO THE FIXTURE MUST TAKE IT BACK OUT.
    # Demo step 3 types *Backflow* into the Skills card and asserts the list
    # grew by one. Run the walkthrough twice without this and BOTH the count
    # check (8 → 9 skills) and the growth check fail, because the add is
    # correctly refused as a duplicate — a walkthrough that only passes on a
    # virgin database reads as a broken screen on its second run, which is the
    # whole reason wave A's terminal script says "it is idempotent" in its own
    # header. The starting state is this script's job, not the browser's.
    removed = work_models.WorkSkill.objects.filter(tenant=tenant, code="BACKFLOW").delete()[0]
    if removed:
        print(f"reset  : removed {removed} leftover Backflow skill from an earlier run")

    work_models.Part.objects.filter(
        tenant=tenant, part_no__in=[row[0] for row in FIXTURE]
    ).delete()

    for part_no, name, category, unit, cost in FIXTURE:
        payload = {
            "part_no": part_no,
            "name": name,
            "unit_of_measure": unit,
            "unit_cost": cost,
        }
        if category is not None:
            payload["category"] = category
        work_services.create_part(None, payload)
        stored = work_models.Part.objects.get(tenant=tenant, part_no=part_no).unit_cost
        # Printed at four decimals because that is what is being asserted: the
        # column keeps the working figure and only the screen rounds.
        assert stored == Decimal(cost), f"{part_no}: stored {stored}, expected {cost}"
        print(f"PLANTED {part_no:9s} {stored:.4f}")

    print(f"register: {work_models.Part.objects.filter(tenant=tenant).count()} part(s)")

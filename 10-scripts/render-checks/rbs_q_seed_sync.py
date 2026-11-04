#!/usr/bin/env python3
"""Run the two INTEGRATION runbooks for real, store their runs, and prove nothing moved.

CR-075 wave Q′ (`US-RBS-032` · `US-RBS-034`), the half a browser cannot do.

WHY THIS IS A SEPARATE SCRIPT AND NOT A MANAGEMENT COMMAND
-----------------------------------------------------------
It would be refused by `G115`, correctly. Staging a parcel file needs
`apps.metering` and `apps.identity`; marking a letter returned needs
`apps.notifications`; and **nothing under `06-backend/apps/runbooks/` may import
another module outside `seams/*_seam.py` and `ports/*_ports.py`**
(`BR-RBS-039`). A fixture is not an exception to a boundary; it lives outside
the module instead, exactly as `rbs_c_seed_run.py` and `rbs_p_seed_money.py` do.

WHAT IT SEEDS, AND THE FIRST ONE IS THE ONE THAT MATTERS
----------------------------------------------------------
1. **A STOPPED run of each runbook, with nothing to work on.** No GIS
   connection, no delivery provider, no uploaded parcel file, no returned
   letters — which is the screen a real utility meets on day one. The Product
   Owner ruled on 2026-09-06 that this is *"a valid case and state for us"*, so
   it must read as a **designed answer** rather than a failure, and only a
   browser can tell you whether it does.
2. **A parcel file, staged through `metering`'s OWN import path**
   (`extract` → `transform` → `validate`, never `load`), and a second run of GIS
   reconciliation over it. Nine parcels against six real premises: one that
   agrees outright, two whose postcode differs, an owner name, a premise type,
   an owner the county has left blank, a city that is never touched, one
   premises the file names twice, and two parcels this utility does not serve.
3. **Returned letters, marked through `notifications`' own `mark_returned`**
   (`US-NOT-014` TC-1 — only PAPER can be returned; a bounce is a provider fact
   on a webhook), and a second run of undeliverable contacts over them.

⚠ **THE RUNS ARE EXECUTED, NOT INSERTED**, and the reports are composed by
`report()` at close and frozen by `services.close_run`. A fixture that typed a
block list would let the walkthrough pass over a broken runbook — `DEF-RBS-4291`
exactly, where `started_at` was never stamped and every run's *Started* and
*Took* column was blank for ever with nothing red.

⚠ **WHAT THIS FIXTURE CANNOT DO, SAID OUT LOUD RATHER THAN LEFT AS A THIN
RESULT.** **No adapter on this deployment writes `bounced` or `failed` on any
channel** — `notifications.delivery_ops.queue_health` records the reason in as
many words, *"delivery is out of this release by PO ruling (2026-08-15)"* — so
the only feedback a person can produce here is a returned letter. Runbook 22's
*nothing left* branch therefore cannot be reached on real data: every account
with print traffic on the seeded tenant also has an email and a phone on file,
so every suppression falls back. That branch is proved in
`tests/test_us_rbs_034_undeliverable_contacts.py` with the seams replaced, and
**both numbers are quoted in the lane report; neither is quoted alone.**

⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY** (hard-won law 7's second habit):

  * **counting outside the tenant context**, where RLS `FORCE` shows a session
    with the default marker NOTHING — so every table reads 0 before and 0 after
    and *"nothing moved"* is true of an empty view rather than of the database.
    That fired on `rbs_c_seed_run.py` and is why `counts()` sets the GUC.
  * **counting only the tables I remember** — so it counts EVERY table in the
    schema and derives the runbooks seven by name.
  * **a fixture too thin to conclude from** — a table empty before and after
    proves nothing, so the summary prints how many tables outside this module
    carry any rows at all.
  * **reporting the stop when the stop is a MISTAKE** — a run that stopped
    because the batch id was mistyped looks exactly like a run that stopped
    because nothing was uploaded. So the working runs assert a NON-empty subject
    list and the script fails if what it just staged resolves to nothing.

USAGE
-----
    DJANGO_SETTINGS_MODULE=config.settings.local \\
    DATABASE_URL="postgres://…/smartbillhub" \\
      python3.12 10-scripts/render-checks/rbs_q_seed_sync.py --tenant brazosbend

It prints `SMOKE_GIS_STOPPED_RUN_ID`, `SMOKE_FEEDBACK_STOPPED_RUN_ID`,
`SMOKE_GIS_RUN_ID` and `SMOKE_FEEDBACK_RUN_ID` for the browser check.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import os
import pathlib
import sys
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "06-backend"
sys.path.insert(0, str(BACKEND))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.identity import models as identity_models  # noqa: E402
from apps.metering import import_runs  # noqa: E402
from apps.metering import models as metering_models  # noqa: E402
from apps.notifications import delivery_ops  # noqa: E402
from apps.notifications import models as notification_models  # noqa: E402
from apps.runbooks import models as runbook_models  # noqa: E402
from apps.runbooks import services  # noqa: E402
from apps.runbooks.definitions import gis_reconciliation, undeliverable_contacts  # noqa: E402
from apps.runbooks.engine import executor  # noqa: E402
from apps.tenancy import models as tenancy_models  # noqa: E402
from core import tenancy as core_tenancy  # noqa: E402

#: The seven tables this module owns. Everything else in the schema belongs to
#: another module, and an Action with no writer bound may not touch any of it.
RUNBOOKS_TABLES = {
    "runbooks",
    "runbook_versions",
    "runbook_runs",
    "runbook_run_records",
    "work_items",
    "cutover_plans",
    "cutover_plan_items",
}


#: The county's own column names, mapped explicitly at stage 2. The header is
#: NAMED and never positional: a file whose columns cannot be named is refused
#: rather than half-understood.
PARCEL_MAPPING = {
    "PARCEL": "external_ref",
    "SITE ADDRESS": "address_line",
    "CITY": "city",
    "STATE": "state",
    "ZIP": "postal_code",
    "OWNER": "owner_manager",
    "USE": "premises_type",
}

#: Nine parcels over six real premises. Every class the runbook can reach with
#: the data this product actually holds is represented once, so a reader of the
#: result screen can see each one rather than infer it.
PARCEL_ROWS = (
    # agrees outright — nothing to do, and the run must SAY nothing rather than
    # leaving the premises out of the counts
    ("88214", "1408 Bluestem Ln", "Katy", "TX", "77494", "Whitfield Rentals LLC", "Single-family"),
    # postcode differs — applies automatically
    ("88215", "2201 Cane Island Pkwy", "Katy", "TX", "77493", "Chen, David", "Single-family"),
    # owner name differs — queued, with Ours · Theirs
    ("88301", "500 Mason Rd Plaza", "Katy", "TX", "77450", "Mason Road Holdings LLC", "Commercial building"),
    # premise type differs — queued
    ("88302", "2200 Riverbend Ct", "Katy", "TX", "77494", "Riverbend Apts LP", "Mixed-use"),
    # city differs (NEVER touched, listed) · postcode differs (auto) · owner
    # blank there (queued)
    ("88303", "3450 Pin Oak Dr", "Fulshear", "TX", "77441", "", "Single-family"),
    # the same premises named by two parcels — a person decides
    ("88304", "77 Gulf Fwy Industrial", "Katy", "TX", "77494", "Northwind Mfg.", "Commercial building"),
    ("88305", "77 Gulf Fwy Industrial", "Katy", "TX", "77494", "Northwind Mfg.", "Commercial building"),
    # parcels this utility does not serve — listed, never created
    ("88999", "77 Nowhere Rd", "Katy", "TX", "77494", "Somebody Else", "Single-family"),
    ("89001", "12 Prairie Bend Ct", "Katy", "TX", "77494", "New Owner LLC", "Single-family"),
)

#: How many paper letters a person marks returned.
RETURNED_LETTERS = 5

#: How long ago the clerk stamped them. ⚠ **DELIBERATELY OUTSIDE THE RUNBOOK'S
#: DEFAULT ONE-DAY WINDOW**, so this fixture produces BOTH screens on every run
#: and not only on the first: a run at the default window finds nothing and
#: STOPS — the day-one screen a real utility meets — and a run with a wider
#: window finds all five and plans. A fixture that could only ever show one of
#: the two would leave the more important screen unwalked.
RETURNED_DAYS_AGO = 2

#: The wider window the working run uses.
WORKING_WINDOW_DAYS = 30

#: A batch id no import run carries. ⚠ **IT PRODUCES A NAMED STOP AND NOT AN
#: ERROR** — *"That parcel file is not here."* — which is the screen a clerk
#: meets when the file they chose has since been loaded or rolled back.
MISSING_BATCH = "00000000-0000-0000-0000-000000000000"


def parcel_csv() -> str:
    """The county's file, QUOTED — a fixture written with `csv` and not with `join`.

    ⚠ **THE FIRST DRAFT JOINED THE FIELDS WITH COMMAS AND THE FIXTURE LIED.**
    An owner recorded as `Rodriguez, M.` carries a comma, so an unquoted line put
    `M.` in the next column: the importer read the owner as `Chen` and the
    premise type as `David`, the runbook reported a difference on both, and every
    figure downstream was wrong in a way that looked like a finding. `csv.writer`
    is the right tool for a file being GENERATED — which is a different job from
    editing a shared register, where a `csv` writer re-serialises every row and
    is exactly the wrong tool (CLAUDE.md hard-won law 11).
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["PARCEL", "SITE ADDRESS", "CITY", "STATE", "ZIP", "OWNER", "USE"])
    for row in PARCEL_ROWS:
        writer.writerow(list(row))
    return buffer.getvalue()


def parcel_file_name() -> str:
    """`county-parcels-2026-09-<digest>.csv` — the CONTENT decides the name.

    ⚠ **A FIXTURE THAT WILL NOT RE-STAGE WHEN ITS DATA CHANGES IS A FIXTURE THAT
    PROVES YESTERDAY.** The staged run is looked up by file name, so a fixed name
    means an edited `PARCEL_ROWS` is silently ignored on every run after the
    first and the walkthrough reads figures from the old file. Naming the file
    for a digest of its own rows makes editing the fixture and re-staging it one
    act instead of two.
    """
    digest = hashlib.sha256(parcel_csv().encode("utf-8")).hexdigest()[:8]
    return f"county-parcels-2026-09-{digest}.csv"


def every_table() -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "ORDER BY table_name"
        )
        return [row[0] for row in cursor.fetchall()]


def counts(tables: list[str], tenant_id) -> dict[str, int]:
    """Row counts AS THE TENANT, which is the only way they are real."""
    out: dict[str, int] = {}
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config('app.tenant_id', %s, false)", [str(tenant_id)])
        for table in tables:
            cursor.execute(f'SELECT count(*) FROM "{table}"')  # noqa: S608 — from the catalog
            out[table] = cursor.fetchone()[0]
    return out


def adopt(tenant, definition) -> runbook_models.Runbook:
    """The runbook row `POST /runbooks` will write, from the SHIPPED definition.

    Nothing here invents a name, a kind or a category — every field is the
    definition's own. `cap` is typed because `runbooks.cap` still has NO column
    default: `OQ-RBS-1731` closed on 2026-09-06 at **100** and wave `L4` carries
    that change, so a fixture that pre-empted it would hide the gap.
    """
    runbook = runbook_models.Runbook.objects.filter(tenant=tenant, key=definition.key).first()
    if runbook is None:
        print(f"── no runbook row for {definition.key!r}; adding the shipped one")
        runbook = runbook_models.Runbook.objects.create(
            tenant=tenant,
            key=definition.key,
            name=definition.name,
            kind=definition.kind,
            category=definition.category,
            subject_type=definition.subject_type,
            unit_of_work=definition.unit_of_work,
            tags=list(definition.tags),
            origin=runbook_models.ORIGIN_SHIPPED,
            # ⚠ **`template_key` IS WHAT MAKES *Accept the update* POSSIBLE, AND
            # A ROW WITHOUT IT IS STUCK.** `open_run` refuses a run whose stored
            # version the code has moved past (`BR-RBS-038`), and the only thing
            # that clears it is `accept_template_update` — which returns `None`
            # for a row carrying no template key. A fixture that omitted it
            # would work once and then refuse every run for ever, with a message
            # about a template it does not claim to have.
            template_key=definition.key,
            trigger_kind=runbook_models.TRIGGER_MANUAL,
            enabled=True,
            cap=100,
        )
    if not runbook.template_key:
        # A row an earlier version of this fixture added without one. A SHIPPED
        # runbook always carries its template key — that is what *shipped* means
        # — and without it the accept below is a silent no-op and every later
        # run is refused for ever.
        runbook_models.Runbook.objects.filter(pk=runbook.pk).update(
            template_key=definition.key
        )
        runbook.template_key = definition.key
        print(f"── backfilled the template key on {definition.key!r}")
    # ⚠ **THE PERSON PRESSING *Review → Accept*, WHICH IS THE ONLY THING THAT
    # APPLIES A SHIPPED CHANGE** (`BR-RBS-038`, wave `E3`: *changing nothing
    # until pressed*). A lane editing the definition moves the code past this
    # tenant's stored version, and `open_run` then refuses in five words. The
    # fixture accepts it deliberately rather than routing round the refusal,
    # because routing round it would hide the day the refusal is the right
    # answer.
    accepted = services.accept_template_update(runbook)
    if accepted is not None:
        print(f"── accepted the template update for {definition.key!r} → version {accepted.version}")
    return runbook


def run_it(tenant, definition, params) -> tuple[str, str, dict, object]:
    """Open, execute, close — and close STOPPED when a step stopped it.

    ⚠ **`services.close_run` TAKES THE STATUS AND `run_to_completion` DOES
    NOT.** A stopped run closed as `done` would be a lie in the one column the
    run history sorts and filters on, so the status is decided here from what the
    steps actually returned rather than defaulted.
    """
    runbook = adopt(tenant, definition)
    run = services.open_run(runbook, definition)
    result = executor.execute(definition, tenant_id=tenant.id, run_id=run.pk, params=params)
    stop = {}
    for step in definition.steps:
        candidate = (result.set_results.get(step.key) or {})
        if isinstance(candidate, dict) and candidate.get("stop"):
            stop = candidate["stop"]
            break
    closed = services.close_run(
        run,
        result,
        status=(
            runbook_models.RUN_STATUS_STOPPED
            if stop
            else runbook_models.RUN_STATUS_AWAITING_APPROVAL
        ),
    )
    return str(closed.pk), closed.status, stop, result


def stopped_run(tenant, definition, params) -> tuple[str, str, dict]:
    """A run that STOPPED — freshly made, or the newest one this tenant already has.

    ⚠ **THE DESIGNED NO-CONNECTION SCREEN IS THE MOST IMPORTANT THING THIS
    FIXTURE PRODUCES AND IT IS THE ONE A SEEDED TENANT MAKES HARDEST TO REACH.**
    Once a parcel file is staged or a letter is marked returned, the tenant HAS
    work and the run correctly does not stop — so a fixture that only ever made
    a fresh run would show the day-one screen on its first execution and never
    again, and the browser check would silently start reading a working screen
    while believing it was reading the stop.

    So: make one, and if it does not stop, fall back to the newest run of this
    runbook that DID — naming it and its date out loud, because a reused run was
    composed by the code of the day it ran and a reader must know that.
    **Fail when there is neither**; a walkthrough with no stop to read should
    say so rather than pass.
    """
    run_id, status, stop, _ = run_it(tenant, definition, params)
    if status == runbook_models.RUN_STATUS_STOPPED:
        return run_id, status, stop
    older = (
        runbook_models.RunbookRun.objects.filter(
            tenant=tenant,
            runbook__key=definition.key,
            status=runbook_models.RUN_STATUS_STOPPED,
        )
        .order_by("-created_at")
        .first()
    )
    if older is None:
        return run_id, status, stop
    print(
        f"── \u26a0 {definition.key!r} no longer stops on this tenant — it now has work. "
        f"Reusing the stopped run of {older.created_at:%Y-%m-%d %H:%M}, composed by the "
        "code of that day."
    )
    verdict = next(
        (block for block in (older.report or []) if block.get("block") == "verdict"), {}
    )
    payload = verdict.get("payload") or {}
    return (
        str(older.pk),
        older.status,
        {"headline": payload.get("count"), "detail": payload.get("detail")},
    )


def an_admin(tenant):
    """A `SimpleNamespace(id, role, user)` — the B12 §6a actor shape.

    `import_runs.extract` and its two later stages are `@require_role`-guarded,
    and a `User` row carries no `role` attribute of its own: the role a route may
    read is a property OF the login, which the API layer composes. A fixture that
    passed the model would meet `AUTH-002` and read like a broken permission.
    """
    user = identity_models.User.objects.filter(tenant=tenant).order_by("created_at").first()
    if user is None:
        raise SystemExit("⛔ this tenant has no users — run seed_demo first")
    return SimpleNamespace(id=user.id, pk=user.id, role="system_admin", user=user)


def stage_the_parcels(tenant) -> str:
    """The county's file, through `metering`'s OWN staging — and never loaded.

    ⚠ **`validate` AND NOT `load`.** A loaded run's rows are premises by then,
    and reconciling one would compare the estate with itself. The runbook reads
    a run at `validated`, which has been read, mapped and judged and has written
    no premises at all.
    """
    file_name = parcel_file_name()
    existing = (
        metering_models.ImportRun.objects.filter(
            tenant=tenant, target="premises", file_name=file_name, status="validated"
        )
        .order_by("-created_at")
        .first()
    )
    if existing is not None:
        print(f"── the parcel file is already staged as run {existing.run_no}")
        return str(existing.id)

    actor = an_admin(tenant)
    staged = import_runs.extract(
        actor,
        {
            "target": "premises",
            "source_kind": "file",
            "file_name": file_name,
            "content": parcel_csv(),
            "batch_label": "County parcels · September",
        },
    )
    run_id = staged["id"]
    import_runs.transform(actor, run_id, {"mapping": PARCEL_MAPPING})
    validated = import_runs.validate(actor, run_id, "upsert")
    print(
        f"── staged {len(PARCEL_ROWS)} parcels as run {staged['run_no']} "
        f"({validated.get('status')}) — nothing written to premises"
    )
    return str(run_id)


def mark_some_letters_returned(tenant) -> int:
    """A clerk stamps the envelopes that came back (`US-NOT-014` TC-1).

    ⚠ **THIS IS THE ONLY FEEDBACK A PERSON CAN PRODUCE ON THIS DEPLOYMENT**, and
    it is deliberately the whole of the fixture's second door. `bounced` and
    `failed` are PROVIDER facts and no adapter writes them on any channel, so a
    fixture that inserted one would be seeding a state the product cannot reach
    — and the runbook would then be proved against a world that does not exist.
    """
    already = notification_models.OutboundMessage.objects.filter(
        tenant=tenant, returned_at__isnull=False
    ).count()
    if already:
        print(f"── {already} letters are already marked returned")
        return already

    rows = list(
        notification_models.OutboundMessage.objects.filter(
            tenant=tenant,
            channel=notification_models.CHANNEL_PRINT,
            returned_at__isnull=True,
        )
        .exclude(account=None)
        .order_by("created_at")[:RETURNED_LETTERS]
    )
    if not rows:
        print("── ⚠ no paper letters on this tenant, so runbook 22 will stop. The run is valid.")
        return 0
    events, refused = delivery_ops.mark_returned(
        message_ids=tuple(row.pk for row in rows),
        at=timezone.now() - dt.timedelta(hours=6),
        actor=an_admin(tenant),
    )
    print(f"── marked {len(events)} letters returned ({len(refused)} refused)")
    return len(events)


def figures(result, definition) -> dict:
    """The `checked` mapping of every step, for the lane report's own numbers."""
    out = {}
    for step in definition.steps:
        value = result.set_results.get(step.key)
        if isinstance(value, dict) and value.get("checked"):
            out[step.key] = value["checked"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default="brazosbend", help="the tenant's subdomain")
    args = parser.parse_args()

    if connection.vendor != "postgresql":
        print(
            f"⛔ REFUSED: this is running on {connection.vendor!r}.\n"
            "   The tenant policies these runbooks read under do not exist on SQLite, so a\n"
            "   green result here would mean nothing (hard-won law 7 — G5 called 192 skips\n"
            "   a pass).",
            file=sys.stderr,
        )
        return 2

    tenant = tenancy_models.Tenant.objects.filter(subdomain=args.tenant).first()
    if tenant is None:
        print(f"⛔ no tenant with subdomain {args.tenant!r} — seed_demo first", file=sys.stderr)
        return 2

    tables = every_table()
    others = [t for t in tables if t not in RUNBOOKS_TABLES]
    print(f"── {len(tables)} tables in the schema · {len(others)} outside this module")
    before = counts(tables, tenant.id)

    with core_tenancy.tenant_context(tenant.id):
        # ── 1 · nothing connected and nothing uploaded ──────────────────────
        gis_stopped_id, gis_stopped_status, gis_stop = stopped_run(
            tenant, gis_reconciliation.RUNBOOK, {"batch": MISSING_BATCH}
        )
        print(
            f"── GIS, the file is not here      : {gis_stopped_status} — "
            f"{gis_stop.get('headline')}"
        )
        feedback_stopped_id, feedback_stopped_status, feedback_stop = stopped_run(
            tenant, undeliverable_contacts.RUNBOOK, {"window": 1}
        )
        print(
            f"── feedback, nothing came back    : {feedback_stopped_status} — "
            f"{feedback_stop.get('headline')}"
        )

        # ── 2 · the parcel file ─────────────────────────────────────────────
        batch_id = stage_the_parcels(tenant)
        gis_id, gis_status, gis_run_stop, gis_result = run_it(
            tenant, gis_reconciliation.RUNBOOK, {"batch": batch_id}
        )
        print(f"── GIS over the parcel file       : {gis_status}")

        # ── 3 · the returned letters ────────────────────────────────────────
        returned = mark_some_letters_returned(tenant)
        feedback_id, feedback_status, feedback_run_stop, feedback_result = run_it(
            tenant, undeliverable_contacts.RUNBOOK, {"window": WORKING_WINDOW_DAYS}
        )
        print(f"── feedback over returned letters : {feedback_status}")

    after = counts(tables, tenant.id)

    # A person uploading a file and a clerk stamping an envelope are PEOPLE's
    # writes, not the runbook's, so their tables are excluded BY NAME and the
    # exclusion is printed beside the result.
    #
    # ⚠ **`audit_log` IS PARTITIONED AND A LIST NAMING ONLY THE PARENT MISSES
    # THE WRITE** (`rbs_p_seed_money.py` learned this the hard way — the check
    # cried wolf over a row `stage_import` had every right to write). Prefixes,
    # not exact names.
    PERSON_PREFIXES = (
        "import_runs",
        "import_run_rows",
        "import_run_progress",
        "import_rule_results",
        "outbound_messages",
        "audit_log",
        "number_series",
    )
    moved_outside = {
        t: (before[t], after[t])
        for t in others
        if before[t] != after[t] and not t.startswith(PERSON_PREFIXES)
    }
    moved_inside = {
        t: (before.get(t), after.get(t)) for t in RUNBOOKS_TABLES if before.get(t) != after.get(t)
    }
    populated = sum(1 for t in others if before[t] > 0)

    print(f"── runbooks tables that moved : {sorted(moved_inside)}")
    print(f"── other tables that moved    : {sorted(moved_outside)}")
    print(f"── excluded, a person's write : {sorted(PERSON_PREFIXES)} (and partitions)")
    print(f"── other tables with any rows : {populated} of {len(others)}")

    print("\n── GIS reconciliation, step by step")
    for step, checked in figures(gis_result, gis_reconciliation.RUNBOOK).items():
        print(f"   · {step}: {checked}")
    print("── Undeliverable contacts, step by step")
    for step, checked in figures(feedback_result, undeliverable_contacts.RUNBOOK).items():
        print(f"   · {step}: {checked}")

    # ⚠ **A STOPPED RUN THAT DID NOT STOP IS THE WORST THING THIS FIXTURE COULD
    # PUBLISH**, because the browser check would read a working screen while
    # believing it was reading the designed stop, and report a pass. Asserted by
    # STATUS rather than by the presence of a headline.
    for name, status in (
        ("GIS", gis_stopped_status),
        ("feedback", feedback_stopped_status),
    ):
        if status != runbook_models.RUN_STATUS_STOPPED:
            print(
                f"\n\u26d4 THE {name.upper()} 'STOPPED' RUN CLOSED AS {status!r}, AND THIS\n"
                "   TENANT HOLDS NO EARLIER STOPPED RUN EITHER. This fixture exists to produce\n"
                "   the designed no-connection screen; a walkthrough reading this run would\n"
                "   pass over the wrong screen entirely.",
                file=sys.stderr,
            )
            return 1

    if gis_run_stop:
        print(
            "\n⛔ THE PARCEL RUN STOPPED. The file was staged one line earlier, so this is a\n"
            "   mistyped id or a broken seam rather than the designed 'nothing to compare'.\n"
            "   A stop that is a MISTAKE reads exactly like a stop that is an ANSWER, which\n"
            "   is why this is asserted rather than eyeballed.",
            file=sys.stderr,
        )
        return 1

    if returned and feedback_run_stop:
        print(
            f"\n⛔ THE FEEDBACK RUN STOPPED over {returned} returned letters. Same shape as\n"
            "   above: a stop that is a MISTAKE reads exactly like a stop that is an ANSWER.",
            file=sys.stderr,
        )
        return 1

    if moved_outside:
        print(
            "\n⛔ AN ACTION WROTE OUTSIDE ITS MODULE WITH NO WRITER BOUND. Every runbook in\n"
            "   the catalogue is handed writer-less ports until wave N turns one on, so this\n"
            "   is not a permission bug: it is a write that reached the database by some\n"
            "   other path.",
            file=sys.stderr,
        )
        for table, (was, now) in sorted(moved_outside.items()):
            print(f"   · {table}: {was} → {now}", file=sys.stderr)
        return 1

    if not moved_inside:
        print(
            "\n⛔ THE RUNS WROTE NOTHING IN THEIR OWN MODULE EITHER. A run that stored no row\n"
            "   is a broken fixture, not a clean Action. Nothing is concluded.",
            file=sys.stderr,
        )
        return 1

    if populated < 10:
        print(
            f"\n⚠ ONLY {populated} TABLES OUTSIDE THIS MODULE HAVE ANY ROWS AT ALL.\n"
            "   'nothing changed' over an empty database is not evidence. Seed a real\n"
            "   utility before reading this as a pass.",
            file=sys.stderr,
        )

    print()
    print(f"SMOKE_GIS_STOPPED_RUN_ID={gis_stopped_id}")
    print(f"SMOKE_FEEDBACK_STOPPED_RUN_ID={feedback_stopped_id}")
    print(f"SMOKE_GIS_RUN_ID={gis_id}")
    print(f"SMOKE_FEEDBACK_RUN_ID={feedback_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

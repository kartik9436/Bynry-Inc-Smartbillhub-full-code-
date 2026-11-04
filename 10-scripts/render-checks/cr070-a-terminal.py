"""Demo script A, steps 4 and 6 — the TERMINAL half of the CR-070 wave A
walkthrough, run before `cr070-a-work-shell-and-anchor.mjs` clicks the screen.

⚠ **WHY THIS FILE IS IN THE REPOSITORY AND NOT IN SOMEBODY'S SCRATCH DIRECTORY
(`DEF-WRK-3633`).** The walkthrough's header used to say

    python manage.py shell -c "$(cat <scratch>/cr070a_terminal.py)"

and that file was in nobody's repository. Run the walkthrough without it and it
fails FIVE checks — 0 rows drawn, no order on `CON-26-0122`, 0 connections
spanned, the leak investigation absent, an empty column list — **every one of
which reads as a broken product rather than as missing setup.** A proof that
only its author can reproduce is not a proof (hard-won law 1: a comment
claiming a procedure is not the procedure).

WHAT IT DOES
------------
**Step 4** raises a *Leak investigation* on `77 Cedar Ct` with a premises and
NO connection. Until `metering/0044` the database refused this outright, which
is `CR-070`'s one structural blocker: a leak investigation on a meter that has
been in the ground for years could not be written down anywhere.

**Step 6** raises one with no anchor at all, twice — once through the service,
which refuses it in a sentence before the database ever sees it, and once
straight at the database with every other NOT NULL satisfied, so that
`ck_work_orders_has_anchor` is the constraint that actually speaks. That second
half is the point: **SQLite cannot express this CHECK**, so the test suite can
never prove it (hard-won law 14) and only a real PostgreSQL can.

HOW TO RUN IT
-------------
    DJANGO_SETTINGS_MODULE=config.settings.local \
    DATABASE_URL="postgres://…/sbh_cr070a" \
      python 06-backend/manage.py shell -c "$(cat 10-scripts/render-checks/cr070-a-terminal.py)"

It is idempotent: it deletes every anchorless order already standing on
`77 Cedar Ct` before it raises, so running it twice leaves ONE leak
investigation and the walkthrough reads the same row count either way.

WHAT IT PRINTS WHEN IT IS RIGHT
-------------------------------
    STEP 4 ACCEPTED: <order id> connection=None
    STEP 6 SERVICE REFUSED: ValidationError: VAL-001 (work.order.anchor_required)
    STEP 6 DATABASE REFUSED: new row for relation "work_orders" violates check
                             constraint "ck_work_orders_has_anchor"
"""
from django.db import connection as db, transaction

from apps.identity.models import User
from apps.metering import connections as w6, models as met
from apps.work import connection_models as work_tables
from apps.tenancy.models import Tenant
from core import tenancy as core_tenancy

tenant = Tenant.objects.get(subdomain="brazosbend")
with core_tenancy.tenant_context(tenant.id):
    actor = User.objects.order_by("created_at").first()
    print(f"actor: {actor.email}")

    prem = met.Premises.objects.filter(address_line="77 Cedar Ct").first()
    if prem is None:
        raise SystemExit(
            "77 Cedar Ct is not seeded — run `manage.py load_sample_data "
            "--tenant brazosbend` first; it is US-WRK-006's phase-0 slice and "
            "the whole point is a house with no build to raise a job on."
        )
    print(f"77 Cedar Ct: {prem.id}")

    # ── step 4 · a premises and no connection ────────────────────────────
    #
    # ⚠ THE PAYLOAD KEY IS `type`, NOT `order_type`. Anything the service does
    # not recognise lands the row as the literal word "unspecified", the screen
    # shows that word, and the walkthrough's TYPE assertion fails while
    # everything else passes — which reads as a rendering bug and is not one.
    # ⚠ CLEAR BY ANCHOR, NOT BY TYPE. A first draft deleted only rows typed
    # "unspecified" and claimed in this docstring to be idempotent; running it
    # twice then left TWO leak investigations and the walkthrough read 19 rows
    # where it had read 18. The claim was wrong before the code was — law 1.
    work_tables.WorkOrder.objects.filter(premises_id=prem.id, connection_id=None).delete()
    made = w6.create_work_order(actor, None, {
        "premises_id": str(prem.id),
        "type": "Leak investigation",
        "service": "water",
    })
    print(f"STEP 4 ACCEPTED: {made.get('work_order_no') or made.get('id')} "
          f"connection={made.get('connection_id')!r}")

    # ── step 6 · no anchor at all, through the service ───────────────────
    try:
        w6.create_work_order(actor, None, {"type": "Leak investigation",
                                           "service": "water"})
        print("STEP 6 SERVICE: ⛔ ACCEPTED — the refusal is missing")
    except Exception as exc:  # noqa: BLE001 — the class name is the evidence
        print(f"STEP 6 SERVICE REFUSED: {type(exc).__name__}: {exc}")

    # ── step 6b · no anchor at all, straight at the database ─────────────
    #
    # Every other NOT NULL is satisfied on purpose. An insert missing `type`
    # is refused by THAT column and never reaches the anchor CHECK, so it
    # proves nothing — the first draft of this script made exactly that
    # mistake and printed a refusal that looked like the right one.
    try:
        with transaction.atomic():      # a SAVEPOINT: law 14, or the failed
            with db.cursor() as cur:    # statement poisons the whole transaction
                cur.execute(
                    "insert into work_orders "
                    "(id, tenant_id, type, scope, state, mode, is_gate, is_sample, "
                    " created_at, updated_at) "
                    "values (gen_random_uuid(), %s, 'Leak investigation', 'premise', "
                    "        'draft', 'our_crew', false, false, now(), now())",
                    [str(tenant.id)],
                )
        print("STEP 6 DATABASE: ⛔ ACCEPTED — the CHECK is missing")
    except Exception as exc:  # noqa: BLE001
        print(f"STEP 6 DATABASE REFUSED: {str(exc).strip().splitlines()[0]}")

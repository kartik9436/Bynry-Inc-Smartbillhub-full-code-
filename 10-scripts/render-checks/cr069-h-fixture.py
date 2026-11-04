# ── Trace ──────────────────────────────────────────────
# Story:  US-INT-027 (EP-INT-07) — Silver Creek's Microsoft mailbox, eleven
#         days from lapsing, with a run history behind it. CR-069 wave H, H5.
# Rules:  BR-INT-042 (a dated warning days ahead; a renewal path that keeps the
#         connection's WHOLE run history)
# ───────────────────────────────────────────────────────
"""The state the wave H demo script opens in, written straight into a clone.

    eval "$(10-scripts/proof-db.sh clone int_h --export)"
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false
    (cd 06-backend && python3 manage.py shell < ../10-scripts/render-checks/cr069-h-fixture.py)

⚠ **THE DATES ARE RELATIVE TO NOW, NOT THE STORY'S 2026-09-12.** The story
fixes the case at *expires_at = 2026-09-12 seen on 2026-09-01*; a walkthrough
run on any other day against a hardcoded date would show *lapsed* and prove the
wrong half. So the credential is placed ELEVEN DAYS FROM THE MOMENT THIS RUNS,
which is the figure frame 54.1 prints and the one the demo reads aloud. The
walkthrough computes the same eleven days and asserts the screen agrees.

⚠ **TWENTY RUNS, BECAUSE THE EXIT TEST IS ABOUT THEM.** `BR-INT-042` asks that
re-authorising keep the connection's whole run history, and the demo's step 7
says *"the twenty runs from before are still on the screen"*. A fixture with
three would let a subtle history loss through.
"""

import json
from datetime import timedelta

from django.utils import timezone

from types import SimpleNamespace

from apps.integrations import models, services
from apps.identity.models import User
from apps.tenancy.models import Tenant
from core import tenancy as core_tenancy

PROVIDER = "email_microsoft"
SEND_FROM = "billing@brazosbend.example"
#: The consent this fixture stores. Obviously synthetic — nobody can mistake it
#: for a live token in a log or a grep.
CONSENT = "1.RECORDED-CONSENT-NOT-REAL-A17C"

tenant = Tenant.objects.get(subdomain="brazosbend")
#: ⚠ THE ROLE IS ON THE ACTOR, NOT IN THE CONTEXT. `@require_role` reads
#: `actor.role` and nothing else (`core/permissions.py`), and a `User` row does
#: not carry one — role is a MEMBERSHIP of a tenant. `seed_partner_morning.py`
#: makes the same object for the same reason. The real user's id travels so the
#: audit rows name a person rather than nobody.
_user = User.objects.get(email="dana@brazosbendutilities.com")
actor = SimpleNamespace(id=_user.id, role="system_admin", full_name=_user.full_name)

with core_tenancy.tenant_context(tenant.id):
    existing = services.connection_for(tenant.id, PROVIDER)
    if existing is not None:
        # ⚠ THIS FIXTURE IS NOT IDEMPOTENT, AND IT CANNOT BE — THE DATABASE SAYS
        # SO. The first draft tried to tidy up by deleting the old runs and
        # starting again, and PostgreSQL refused it by name:
        #
        #     BR-INT-039: integration_run is append-only — a run is never
        #     deleted (attempted delete)
        #
        # That is `integration_run_append_only()`, a trigger doing exactly its
        # job. A run record is a record; a fixture is not entitled to a clean
        # slate on top of one. So this refuses instead, and the answer is a
        # fresh clone — which takes about a second (`proof-db.sh clone`).
        raise SystemExit(
            f"cr069-h fixture: {PROVIDER} is already connected for "
            f"{tenant.subdomain}, with "
            f"{models.IntegrationRun.objects.filter(connection=existing).count()} run(s).\n"
            "  Runs are append-only (BR-INT-039), so this fixture cannot start over on\n"
            "  top of them — a second run would seed twenty MORE and the walkthrough's\n"
            "  count would be forty. Take a fresh clone:\n"
            "      ./10-scripts/proof-db.sh clone int_h --stale-ok --export"
        )

    connection = services.connect(
        actor=actor,
        tenant_id=tenant.id,
        provider_key=PROVIDER,
        environment="production",
        cadence="nightly",
        # `config` and not `fields`: this is the SERVICE, and the split into
        # secret and non-secret belongs to the API layer above it. `send_from`
        # is declared `email` in the manifest and so is non-secret by
        # construction — `connect` refuses a secret-kind field here by name.
        config={"send_from": SEND_FROM},
        label=None,
    )

    now = timezone.now()
    services.record_credential(
        actor=actor,
        connection=connection,
        payload=json.dumps({"refresh_token": CONSENT}),
        masked_hint="••••A17C",
        # ⚠ ELEVEN DAYS **AND TWELVE HOURS**, AND THE HALF-DAY IS THE WHOLE
        # POINT. `expiry.view_for` floors `days_left` — deliberately, because
        # "eleven days" should mean eleven WHOLE days rather than ten and a
        # half dressed up. So a fixture that writes exactly `now + 11 days`
        # reads **10** the moment any time passes, and the walkthrough that ran
        # four minutes later failed on `got 10`. That was the fixture being
        # wrong, not the engine.
        #
        # The half-day margin means a walkthrough run any time within twelve
        # hours of seeding still reads the eleven that frame 54.1 prints and
        # the demo script reads aloud.
        expires_at=now + timedelta(days=11, hours=12),
    )

    # The connection has been working: twenty nightly sends, all clean. These
    # are what step 7 counts again after re-authorising.
    for index in range(20):
        run = services.start_run(
            connection=connection,
            operation="send_message",
            direction="outbound",
            trigger="dispatcher",
        )
        services.finish_run(
            run, attempted=93, succeeded=93, failed=0, skipped=0, confirmed=True
        )

    connection.status = models.STATUS_WORKING
    connection.last_test_ok = True
    connection.last_test_text = None
    connection.save(
        update_fields=["status", "last_test_ok", "last_test_text", "updated_at"]
    )

    runs = models.IntegrationRun.objects.filter(connection=connection).count()
    credential = models.IntegrationCredential.objects.get(connection=connection, is_active=True)

print(f"cr069-h fixture: {PROVIDER} connected for {tenant.subdomain}")
print(f"  send_from   {SEND_FROM}")
print(f"  credential  v{credential.version} · {credential.masked_hint}")
print(f"  expires_at  {credential.expires_at.isoformat()}  (11 days + 12h out)")
print(f"  runs        {runs}")

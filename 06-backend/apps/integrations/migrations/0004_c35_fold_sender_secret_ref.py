# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-026 (EP-INT-07) — *"a mail password typed into the product,
#           not the name of an environment variable"* (`C35`). TC-1 the present
#           secret · TC-2 the absent one · TC-4 the retirement · TC-6 two
#           tenants. Screens: S8 Notifications (the card that becomes a read) ·
#           S141
# Rules:    BR-INT-042 (a real credential with a lifecycle replaces a name in a
#           store) · BR-INT-005 (the tenant connects its OWN mailbox) ·
#           BR-INT-026 (production and sandbox are two rows) · BR-INT-025
#           (a credential is versioned — this writes v1 and nothing else) ·
#           CLAUDE.md hard rule 1 (every write is stamped with its tenant) ·
#           hard-won law 3 (an absent secret is a stated state, never a guess)
# Tests:    06-backend/tests/test_us_int_026_fold.py
# Impacts:  apps/notifications/models.py (`smtp_secret_ref`, NULLed and left in
#           the schema) · apps/notifications/sender_config.py (its reader,
#           retired in the same commit) · apps/integrations/models.py
# ───────────────────────────────────────────────────────
"""integrations 0004 — the mail password stops being the NAME of a secret.

HUMAN-OWNED (migration ordering is a 🔒 sensitive path, CLAUDE.md — and this
one reads a real credential out of the deployment's environment, which puts it
in the credentials class too).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-04 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*), with a row in
`12-governance/09-human-review-ledger.md` stating in plain English, with a
worked figure, what a reviewer is shown.

WHAT THIS DOES, ONCE, IN THE DEPLOYMENT THAT HOLDS THE SECRET
---------------------------------------------------------------
`notifications.NotificationSettings` has carried `smtp_secret_ref` since
2026-08-18 — *"holds the NAME of a secret in the deployment's own store"* —
on the stated grounds that this repo had no crypto kernel. **It has had one
since 24 August.** So for every tenant that named a secret:

  * an `email_smtp` connection is created from the columns beside it (host,
    port, username, from-address) — production, cadence `manual`;
  * the named environment variable is read **HERE, at migration time, in the
    process that has it**, and becomes credential v1, encrypted;
  * `smtp_secret_ref` is set to NULL, for every row, whether or not anything
    was found.

⚠ **AN ABSENT SECRET IS A STATED STATE, NOT A GUESS (TC-2).** If the named
variable is not in the environment, the connection is still created — so the
utility can see it — with `status = not_set_up` and no credential row at all.
There is no empty credential, no placeholder, and no invented value. The
screen says *Mail password needs entering*, which is true and actionable;
writing an empty ciphertext would have produced a connection that looked ready
and failed on the first bill run.

⚠ **THIS MIGRATION IS THE ONE PLACE `smtp_secret_ref` IS EVER READ AGAIN.**
`US-INT-026` TC-4 is the standing form of that: a grep over `06-backend/apps`
finds this file and a `# retired` comment, and nothing else.

⚠ **IT IS RE-RUNNABLE AND IT IS NOT AN UPDATE.** A tenant that already has an
`email_smtp` connection is SKIPPED entirely — the connection is the newer
truth and a migration may not overwrite what a person has since typed.

⚠ **NO SAVEPOINT DANCE, AND THE REASON IS WORTH WRITING DOWN (hard-won law
14).** Nothing here catches a database error and continues: every row is
either created or the whole migration fails, which is what a migration should
do. The law bites where a loop *skips a bad row and carries on*; this loop has
no such branch, so it needs no nested `atomic()` and would be wrong to have
one.
"""

from __future__ import annotations

import json
import os
import uuid

from django.db import migrations
from django.utils import timezone

PROVIDER_KEY = "email_smtp"


def _mask(secret: str) -> str:
    """`••••kbox` — the mask plus at most the last four characters. The same
    rule `services._hint` applies, restated here because a migration may not
    import a service (it would bind to today's code, not to this moment's)."""
    return "••••" + secret[-4:]


def fold(apps, schema_editor):
    from core import crypto

    Settings = apps.get_model("notifications", "NotificationSettings")
    Connection = apps.get_model("integrations", "IntegrationConnection")
    Credential = apps.get_model("integrations", "IntegrationCredential")

    now = timezone.now()
    for row in Settings.objects.exclude(smtp_secret_ref__isnull=True).exclude(smtp_secret_ref=""):
        if Connection.objects.filter(
            tenant_id=row.tenant_id, provider_key=PROVIDER_KEY, environment="production"
        ).exists():
            continue  # a person has already connected it — that is the newer truth
        secret = os.environ.get(str(row.smtp_secret_ref).strip())
        config = {
            "host": row.smtp_host or "",
            "port": str(row.smtp_port) if row.smtp_port else "587",
            "username": row.smtp_username or "",
            "send_from": row.sender_from_address or "",
        }
        connection = Connection.objects.create(
            id=uuid.uuid4(),
            tenant_id=row.tenant_id,
            provider_key=PROVIDER_KEY,
            label=None,
            environment="production",
            # An absent secret is `not_set_up`, and the card says why (TC-2).
            status="untested" if secret else "not_set_up",
            enabled=bool(secret),
            cadence="manual",
            next_run_at=None,
            config=config,
            connected_at=now if secret else None,
        )
        if secret:
            Credential.objects.create(
                id=uuid.uuid4(),
                tenant_id=row.tenant_id,
                connection=connection,
                version=1,
                is_active=True,
                # The ONE read of the environment, and the value is encrypted
                # before it is handed to the ORM — `payload_enc` on the
                # historical model is a plain TextField, so the envelope is
                # built here rather than by the field.
                payload_enc=crypto.encrypt(
                    json.dumps({"password": secret}),
                    context="integration_credential.payload_enc",
                ),
                masked_hint=_mask(secret),
            )
    # Every row, including the ones with no connection made: the column stops
    # holding anything from this migration onward.
    Settings.objects.exclude(smtp_secret_ref__isnull=True).update(smtp_secret_ref=None)


def unfold(apps, schema_editor):
    """Deliberately empty, and the emptiness is the honest answer.

    The name of the environment variable is gone and cannot be reconstructed
    from a connection; the password itself was never in the column to put
    back. A migration that invented a plausible name would be worse than one
    that does nothing. Rolling this back means restoring the column's values
    from a backup — which is what CR-069 §16 says about phase 2: it rolls back
    cleanly because no partner holds anything of ours, and this is the one
    thing in it that a person has to do by hand.
    """


class Migration(migrations.Migration):
    dependencies = [
        ("integrations", "0003_run_items"),
        ("notifications", "0017_def2496_notification_version_pin_lock"),
    ]

    operations = [migrations.RunPython(fold, unfold)]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-026@c05e4dd4 (EP-INT-07 story + BR-INT-042 snapshot)
# generated: 2026-09-04 by the CR-069 wave E build lane
# checklist: A✔ B✔ C✔ D=n/a(a migration has no route) E✔(S8's sender card reads the connection this creates) F✔ G✔ H=PENDING(🔒 — human sign-off owed, row in 09-human-review-ledger.md)
# gates: makemigrations --check · pytest tests/test_us_int_026_fold.py (present secret · absent secret · two tenants · re-run) · G7
# exceptions: (1) the four sender columns are COPIED and NOT dropped — dropping a column in the same commit that stops reading it leaves no way back if the copy was wrong; a later wave drops them once nothing has read them for a release. (2) `unfold` is empty on purpose, see its docstring.
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────

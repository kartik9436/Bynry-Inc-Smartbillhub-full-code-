# ── Trace ──────────────────────────────────────────────
# Change:   CR-060 · C21 — "Gateway payment webhooks", new in `CR-060 · 0d.1`
#           and labelled there *"new — was an undecided absence"*. What done
#           looks like: *"a card payment from the portal appears on Record
#           payments with no clerk keying it, marked cleared and allocated; the
#           provider re-sending the same callback produces ONE payment, not
#           two."*  Table named by `CR-059 §4` as one of its four new tables.
# Story:    US-PAY-001 (the recording path this feeds)   Screens: S33
# Rules:    BR-PAY-003 (inbound payment webhooks dedupe on `webhook_key`
#           UNIQUE) · BR-PAY-028 (idempotency; key mechanics Eng-Lead 🔒) ·
#           CLAUDE.md hard rule 6 (idempotency on inbound payment webhooks) ·
#           hard rule 1 (tenant scoping, RLS FORCE) · hard rule 7 (audit)
# Tests:    06-backend/tests/test_cr060_c21_webhooks.py
# ───────────────────────────────────────────────────────
"""payments 0020 — `payment_webhook_events`, the record of what a gateway said.

HUMAN-OWNED (webhook keys are a CLAUDE.md 🔒 path by name, and this table is
what stands between a provider's retry and a second payment on a customer's
account). HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO ruling of
2026-08-09.

════════════════════════════════════════════════════════════════════════════
WHY A TABLE AT ALL, WHEN `payments.webhook_key` ALREADY DEDUPES
════════════════════════════════════════════════════════════════════════════
`uq_payments_webhook_key` is what makes a redelivered callback write one payment
— that has been true since `payments/0003` and C21 does not change it. **What it
cannot do is answer any question about a callback that produced NO payment**, and
those are the ones that cost a support call:

  * a callback whose **signature did not verify**. It must not create a payment
    and it must not vanish either — a provider misconfiguration and an attack
    look identical in an empty log.
  * a callback for an **account this tenant does not have**, or an amount that
    cannot be parsed. The money is real at the gateway; somebody has to see it.
  * a callback that arrived **before** the account existed and would succeed on a
    retry.

So every delivery is recorded, verified or not, accepted or not — and the
payment it produced, when it produced one. **`payments` records money; this table
records what the provider SAID**, which is a different fact and is the one a
person needs when the two disagree.

════════════════════════════════════════════════════════════════════════════
THE UNIQUE KEY IS `(tenant, provider, event_id)` AND IT IS THE SECOND GUARD
════════════════════════════════════════════════════════════════════════════
A gateway's own event id is the thing it repeats on a retry, and it is unique
per provider rather than globally: two providers may both number an event `1`.
So the constraint is on all three columns and it is **INDEPENDENT of
`payments.webhook_key`** — deliberately, and for `DEF-058`'s reason. Two guards
that catch the same fact on the same code path are one guard, and the day
somebody changes the key scheme is the day the other stops covering it. These
two catch genuinely different things:

    uq_payment_webhook_events_event   this DELIVERY has been seen before
    uq_payments_webhook_key           this PAYMENT has been recorded before

A replay hits the first and never reaches the second. A callback that was seen,
refused for a bad signature, then re-sent with the same id after the secret was
fixed is **still a replay of a delivery** and the row says what happened to it.

════════════════════════════════════════════════════════════════════════════
WHAT IS DELIBERATELY NOT IN THIS TABLE
════════════════════════════════════════════════════════════════════════════
* **No signature and no secret.** The row records whether verification PASSED,
  never the material. A stored signature is a stored credential with extra steps.
* **No card number, no last four, no cardholder name.** C21 is the INBOUND half —
  recording what a gateway says already happened — and none of those facts is
  needed to record a payment. `CR-059` CS-1 (taking money from a card) is v2 and
  out of this release; a column here that only a charging path would fill is a
  column that invites one to be written.
* **The raw body is stored, and it is the one judgement worth stating.** Without
  it a failed delivery cannot be replayed or explained and the support call ends
  in a shrug. It is why the RLS policy on this table matters as much as the one
  on `payments`.
"""

from django.db import migrations, models

import core.dbfields

#: RLS, in the shape `payments/0002` and `payments/0013` already use for this
#: module's tables. FORCE, so the table's own owner is filtered too (CLAUDE.md
#: hard rule 1) — a webhook row carries an account id and a money figure, and a
#: cross-tenant read of it is a cross-tenant read of a customer's payment.
RLS = """
ALTER TABLE payment_webhook_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_webhook_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_payment_webhook_events ON payment_webhook_events;
CREATE POLICY rls_payment_webhook_events ON payment_webhook_events
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""

DROP_RLS = """
DROP POLICY IF EXISTS rls_payment_webhook_events ON payment_webhook_events;
ALTER TABLE payment_webhook_events NO FORCE ROW LEVEL SECURITY;
ALTER TABLE payment_webhook_events DISABLE ROW LEVEL SECURITY;
"""

#: ⚠ **SINGLE `%`, NOT `%%` — AND THE DIFFERENCE IS A MIGRATION THAT WILL NOT
#: APPLY.** Every other trigger in this module is installed through
#: `migrations.RunSQL`, which passes the string to the driver as a QUERY and
#: therefore needs `%` doubled. These are executed through
#: `schema_editor.connection.cursor().execute(sql)` with **no parameters**, so
#: no interpolation happens and `%%` survives into plpgsql — where it reads as
#: an escaped literal `%` rather than a placeholder, leaving the RAISE with
#: three arguments and nowhere to put them:
#:
#:     psycopg.errors.SyntaxError: too many parameters specified for RAISE
#:     CONTEXT: compilation of PL/pgSQL function …
#:
#: **It is invisible on the default suite**, which is CLAUDE.md hard-won law 14
#: exactly: SQLite installs neither of these, so every test passed and the
#: migration failed the first time it met a real PostgreSQL.
#: Append-only. A delivery is a statement about what a provider sent at a moment
#: in time, so amending one would be re-writing history — the same argument
#: `payments/0002` makes for a payment, and the same shape.
#:
#: ⚠ **THE STATUS WALK IS THE ONE THING THAT MOVES**, because a delivery that
#: could not be processed is RETRIED and the outcome of the retry belongs on the
#: row that recorded the attempt. Everything else — the provider, the event id,
#: the body, the received moment — is frozen from the instant the row exists.
FREEZE = """
CREATE OR REPLACE FUNCTION payments_webhook_event_append_only() RETURNS trigger AS $$
DECLARE
  mutable    text[] := ARRAY['status', 'payment_id', 'outcome', 'processed_at', 'updated_at'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-003 / hard rule 4: webhook delivery % cannot be removed. It is the record of what a payment provider told this utility, and it is the only evidence that exists when the gateway and the books disagree.',
      OLD.id::text;
  END IF;
  frozen_old := to_jsonb(OLD) - mutable;
  frozen_new := to_jsonb(NEW) - mutable;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-003 / hard rule 4: webhook delivery % is append-only. Only its processing OUTCOME may move (a refused delivery can be retried); the provider, the event id, the body and the moment it arrived are frozen from the instant the row exists. Changed: %',
      OLD.id::text,
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_payment_webhook_event_append_only ON payment_webhook_events;
CREATE TRIGGER trg_payment_webhook_event_append_only
  BEFORE UPDATE OR DELETE ON payment_webhook_events
  FOR EACH ROW EXECUTE FUNCTION payments_webhook_event_append_only();
"""

DROP_FREEZE = """
DROP TRIGGER IF EXISTS trg_payment_webhook_event_append_only ON payment_webhook_events;
DROP FUNCTION IF EXISTS payments_webhook_event_append_only();
"""


def apply_postgres_guarantees(apps_registry, schema_editor):
    """RLS and the freeze — PostgreSQL only.

    SQLite has neither, which is exactly why `payments/0002`'s own docstring
    says the app-layer tenant filter *"protects the SQLite developer tier, which
    has no policies at all"*. Every read in `webhooks.py` filters on the tenant
    explicitly for that reason, and this is the second, independent guarantee.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(RLS)
        cursor.execute(FREEZE)


def remove_postgres_guarantees(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(DROP_FREEZE)
        cursor.execute(DROP_RLS)


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0019_cr059_cs33_partial_reversal"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentWebhookEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("provider", models.TextField()),
                ("event_id", models.TextField()),
                ("event_type", models.TextField(blank=True, null=True)),
                ("status", models.TextField(default="received")),
                ("signature_verified", models.BooleanField(default=False)),
                ("body", models.JSONField(blank=True, default=dict)),
                ("received_at", models.DateTimeField()),
                ("processed_at", models.DateTimeField(blank=True, null=True)),
                ("payment_id", models.UUIDField(blank=True, null=True)),
                ("outcome", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=models.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "payment_webhook_events"},
        ),
        migrations.AddConstraint(
            model_name="paymentwebhookevent",
            constraint=models.UniqueConstraint(
                fields=["tenant", "provider", "event_id"],
                name="uq_payment_webhook_events_event",
            ),
        ),
        migrations.AddIndex(
            model_name="paymentwebhookevent",
            index=models.Index(
                fields=["tenant", "status", "-received_at"], name="ix_pay_webhook_status"
            ),
        ),
        migrations.RunPython(apply_postgres_guarantees, remove_postgres_guarantees),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 §0d.1 C21 · CR-059 §4 (the four new tables) · BR-PAY-003 ·
#         BR-PAY-028 · apps/payments/idempotency.py (the key scheme this reuses
#         rather than inventing a second one) · apps/payments/migrations/0003
#         (`uq_payments_webhook_key`, the guard this one does NOT replace)
# generated: 2026-09-03 by the CR-059/CR-060 payments cross-account lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — the payments a webhook
#            records appear on the EXISTING S33 list, which is what C21's
#            acceptance line asks for) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 no signature, secret, card number or last four is stored. See the module
#      docstring; a column only a CHARGING path would fill is a column that
#      invites one, and taking money from a card is CS-1, v2, out of scope.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

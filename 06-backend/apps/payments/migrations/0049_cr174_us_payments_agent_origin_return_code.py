# ── Trace ──────────────────────────────────────────────
# Change:   CR-174-BRC10 — US Payments (Prime): the three calls they make to us
# Rules:    CLAUDE.md hard rule 4 (append-only payments; a column written at
#           INSERT and frozen after) · hard rule 2 · B2 §2 · BR-PAY-013
# Tests:    06-backend/tests/test_cr174_us_payments.py
# ───────────────────────────────────────────────────────
"""payments/0049 — a fourth origin, and a home for the bank's return code.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and this adds three
columns and two CHECKs on a hard-rule-4 table).

HUMAN-REVIEW-PENDING — a 🔒 payments migration, AI-authored 2026-10-07 under
the PO ruling of 2026-08-09 (*"AI will do it; we will review it later as
human"*). Row in `12-governance/09-human-review-ledger.md`.

THREE CHANGES, ALL ADDITIVE
--------------------------
1. **`ck_payments_origin` gains `agent`.** PO 2026-10-07 (D3): US Payments
   money must not enter the New World receipts feed, which selects
   `origin = webhook` and is not to be changed. `entry` and `import` would be
   false of it, so it is a fourth word — `models.PAYMENT_ORIGIN_AGENT` says
   what it means. The CHECK is dropped and re-added over four words; no row
   moves, because no row holds `agent` before this migration exists.

2. **`payments.return_code`**, nullable text — the Nacha code a return
   notification carries (`R01`). `REVERSAL_REASONS` is a closed four-word set
   that decides what a bounce does, so the bank's own code is kept BESIDE it,
   never inside it. `ck_payments_return_code_on_reversal` allows a value only
   on a reversing row.

3. **`payments.channel` and `payments.terminal`**, nullable text — where the
   customer stood when an agent took the money (`kiosk`, `csr`, `web`, `ivr`,
   `other`; `ck_payments_agent_channel`) and which machine (`4471`). The
   coordinator's brief: *"Channel and kioskId: shown on the payment's detail
   (wherever source/confirmation shows today); kept in the raw landed
   message."* The raw message keeps them whole; these columns are what the
   payment's page reads without parsing a partner's JSON.

WHY NO TRIGGER CHANGE
---------------------
`trg_payment_immutable` compares `to_jsonb(OLD) - <allow list>` against the
same for NEW, so a new column is frozen by construction from the moment it
exists: it is on neither of `payments/0014`'s lists. An INSERT carries it
freely, which is the only write it ever gets. Adding a nullable column with no
default is a catalogue change on PostgreSQL — no row is rewritten and the
trigger never fires.

ROLLBACK
--------
Reverse drops the three columns and restores the three-word CHECK. ⚠ The reverse
FAILS if any payment already carries `agent` — deliberately: a CHECK that
silently stopped describing the rows under it would be worse than a refused
rollback. Delete nothing; re-apply forward instead.
"""

from django.db import migrations, models

FOUR = ("entry", "webhook", "import", "agent")
CHANNELS = ("kiosk", "csr", "web", "ivr", "other")


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0048_rls_cr171_deposit_releases"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="payment", name="ck_payments_origin"),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=models.Q(origin__in=FOUR) | models.Q(origin__isnull=True),
                name="ck_payments_origin",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="return_code",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=models.Q(return_code__isnull=True)
                | models.Q(reverses_payment__isnull=False),
                name="ck_payments_return_code_on_reversal",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="channel",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="terminal",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=models.Q(channel__isnull=True) | models.Q(channel__in=CHANNELS),
                name="ck_payments_agent_channel",
            ),
        ),
    ]

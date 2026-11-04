# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-027 (EP-INT-07) — "a nightly sweep that warns days ahead
#           with the date in words … once per day, never twice for the same
#           day", CR-069 wave H task H2
# Rules:    BR-INT-042 (P6 — credentials have a lifecycle, not a moment)
# ───────────────────────────────────────────────────────
"""integrations 0006 — the day we last said it. HUMAN-OWNED (migration
ordering is a 🔒 sensitive path, CLAUDE.md).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-06 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); the review-ledger row is
in `12-governance/09-human-review-ledger.md` and states, in plain English with
the figure, exactly what a reviewer is being asked to agree to.

ONE NULLABLE DATE COLUMN, AND THE INTERESTING PART IS WHICH TABLE IT IS ON
--------------------------------------------------------------------------
`BR-INT-042` asks for a warning that arrives once a day and not twice. That
needs a memory of the last day we said it, and the obvious home is the
CONNECTION — one row per connection, one flag.

It is on `integration_credential` instead, and the reason is the other half of
the same rule: *a renewal path that keeps the connection's whole run history*.
Re-authorising writes credential v(n+1) on the same connection row. If the
memory lived on the connection, that write would owe a SECOND write to clear
the flag — and a utility whose lane forgot it would go on being told to
re-authorise a credential it had already replaced, with every test green,
because nothing in the schema would be wrong.

On the credential, v(n+1) arrives with this column NULL by construction and
carries its own later `expires_at`. The warning stops because the row it was
about is no longer the active credential. **There is no reset step to forget.**

⚠ WHY A `date` AND NOT A `timestamp`. The rule is *once per DAY*, and a day is
a fact about the tenant's calendar rather than about UTC. `services.sweep_expiry`
resolves the tenant's own today through `core.tenancy` and compares dates, so a
utility in America/Chicago is warned once on its own Tuesday — not twice
because a UTC boundary fell in the middle of its afternoon.

⚠ THE COLUMN INHERITS `integration_credential`'s RLS. `0002_rls_force` put
`FORCE ROW LEVEL SECURITY` on the table and the policy is over the ROW, not
over a column list, so a column added later is covered the moment it exists.
Nothing here re-states the policy, and a lane checking that should read
`0002_rls_force` rather than expect a clause in this file.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0005_f1_skipped_outcome"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationcredential",
            name="expiry_warned_on",
            field=models.DateField(blank=True, null=True),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-027 (EP-INT-07 — the dated warning) · BR-INT-042
# generated: 2026-09-06 by the CR-069 wave H build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 row in 09-human-review-ledger.md)
# gates: makemigrations --check clean · sqlmigrate prints one ADD COLUMN, nullable, no default and no table rewrite · tests/test_us_int_027_expiry.py (the second sweep on one day writes nothing)
# exceptions: none — one nullable column, no backfill. Every credential already in the table reads NULL, which is exactly right: nothing has been warned about yet
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────

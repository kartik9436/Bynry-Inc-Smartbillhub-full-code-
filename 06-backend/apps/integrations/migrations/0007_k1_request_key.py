# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-035 (EP-INT-09) — "a fetch that changes their world recorded
#           as a write": an idempotency key and a receipt written BEFORE the
#           call, and a retry refused as a duplicate. CR-069 wave K task K1.
# Rules:    BR-INT-050 (no vendor default on a money path; `mutates_partner_state`
#           recorded with key and receipt; retry refused) · BR-INT-020 (the key
#           is generated before the call) · CLAUDE.md hard rule 6 (idempotency
#           by unique key)
# ───────────────────────────────────────────────────────
"""integrations 0007 — the key we mint before the request leaves. HUMAN-OWNED
(migration ordering AND idempotency keys are both 🔒 sensitive paths, CLAUDE.md).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-06 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*); the review-ledger row is
in `12-governance/09-human-review-ledger.md` and states, in plain English with
the figure, exactly what a reviewer is being asked to agree to.

ONE NULLABLE TEXT COLUMN AND ITS INDEX, AND THE INTERESTING PART IS WHY IT IS
NOT `input_hash`
-----------------------------------------------------------------------------
`integration_run` already carries `input_hash` — a hash of a file's BYTES,
computed before anything parses them, which refuses the same bank file arriving
twice (`CR-069` wave I). It is tempting to reuse it: both are idempotency keys,
both live on a run row, both are looked up the same way.

**Two reasons not to, and the first one reaches a clerk.** S142 labels
`input_hash` **Content hash** and shows it on the run detail. An outbound
request key sitting behind that label is a lie a person reads off a screen — a
value that is not a hash, of a file that never existed. The second is that they
are computed at opposite ends of a call and mean opposite things: `input_hash`
is *what we received*, `request_key` is *what we are about to say*. A column
that means both means neither, and the next lane to touch either one would have
to work out which.

⚠ WHY THE KEY IS WRITTEN BEFORE THE CALL AND NOT AFTER IT. Neptune's export can
carry `CloseOnExport`, which **closes billing routes on their side**. A retry
after a timeout must not close them a second time — and a key written when the
call RETURNS does not exist during the window where a retry is most likely,
which is precisely the moment the far end went quiet. So the row is opened with
the key already on it, exactly as `arrivals.record_arrival` opens a row with the
digest already on it, and the ordering is a fact about the row rather than a
claim in a comment (hard-won law 1).

⚠ NULL FOR EVERY EXISTING ROW, AND THAT IS CORRECT RATHER THAN A BACKFILL WE
SKIPPED. No operation shipped before this migration declares
`mutates_partner_state`, so no run in any tenant's history changed a partner's
state. A backfilled value would be a claim about the past that nobody made.

⚠ THE COLUMN INHERITS `integration_run`'s RLS. `0002_rls_force` put `FORCE ROW
LEVEL SECURITY` on the table and the policy is over the ROW, not over a column
list, so a column added later is covered the moment it exists. Nothing here
re-states the policy; a lane checking that should read `0002_rls_force`.

⚠ THE INDEX IS `(tenant_id, request_key)` AND THE DUPLICATE QUERY NARROWS BY
CONNECTION, which is the shape `ix_intg_run_input_hash` already has and is the
same judgment: two connections at one utility may legitimately mint the same
key for the same period against two different partners, and neither should
refuse the other's.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0006_h2_expiry_warned_on"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationrun",
            name="request_key",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddIndex(
            model_name="integrationrun",
            index=models.Index(fields=["tenant", "request_key"], name="ix_intg_run_request_key"),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-INT-035 (EP-INT-09 — safety parameters and a partner-state write) · BR-INT-050 · BR-INT-020
# generated: 2026-09-06 by the CR-069 wave K build lane
# checklist: A✔ B=n/a C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 row in 09-human-review-ledger.md)
# gates: makemigrations --check clean · sqlmigrate prints one ADD COLUMN (nullable, no default, no table rewrite) and one CREATE INDEX · tests/test_us_int_035_safety_parameters.py (the retry of a CloseOnExport period is refused naming the first close by date)
# exceptions: none — one nullable column and one index, no backfill. Every existing run reads NULL, which is exactly right: no operation shipped before this declares mutates_partner_state
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────

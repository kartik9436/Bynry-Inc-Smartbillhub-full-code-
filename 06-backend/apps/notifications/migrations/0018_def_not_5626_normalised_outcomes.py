# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-014 (bounces + returned mail — the queue statuses the
#           bad-address flow feeds on)   Screens: S8 · S30
# Rules:    BR-NOT-005 (statuses queued→sent→delivered/failed/bounced,
#           forward-only; retry ×3 with backoff) · BR-NOT-013 (`delivered` and
#           `bounced` are PROVIDER facts and nothing in this repo writes one —
#           unchanged by this migration, which ships WORDS and no writer) ·
#           BR-PAY-018 (a suppression is what a bad address earns; its paper
#           half already exists and this is the email half's vocabulary) ·
#           CLAUDE.md rule 1 (tenant scoping — the index is per tenant) ·
#           rule 6 (the five-column idempotency key is UNCHANGED)
# Change:   DEF-NOT-5626, 2026-09-17 — the SendGrid/Postmark normalised outcome
#           set needs four values `OutboundMessage.STATUSES` does not have.
# ───────────────────────────────────────────────────────
"""notifications 0018 — the failures index learns the four normalised outcomes.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-09-17 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

WHAT THIS MIGRATION ACTUALLY DOES, AND WHAT IT DELIBERATELY DOES NOT
────────────────────────────────────────────────────────────────────────────
`outbound_messages.status` is a plain `TextField` with **no CHECK constraint and
no enum type** — the vocabulary lives in `models.STATUSES`, in Python. So adding
four lawful values is not a DDL change at all, and this migration would be empty
were it not for ONE object that names the old vocabulary in the DATABASE: the
partial index `ix_outbound_msgs_failed`, whose predicate was
`status IN ('failed','bounced')`.

It becomes `status IN ('failed','bounced','bounced_hard','bounced_soft',
'complained')` — `models.ATTENTION_STATUSES`, the same tuple
`selectors._apply_order` and `delivery_ops.failures` read. A hard bounce that
the one screen built to show a clerk what went wrong could not index would be
hard-won law 7's *reporting zero over a scope it silently excludes*.

`unsubscribed` is deliberately absent from that predicate. It is the one outcome
of the six that is not a failure — a person exercising a choice — and a clerk
looking at a list headed *failures* must not be invited to undo it. It surfaces
on the blocked-addresses screen instead.

NOT ONE ROW IS REWRITTEN, AND THAT IS THE DECISION RATHER THAN THE SHORTCUT
────────────────────────────────────────────────────────────────────────────
There is no data migration here. `bounced` stays a LAWFUL value and every row
carrying one keeps it.

**Why, in the figures:** `BR-NOT-013` (PO ruling 2026-08-15) says *"`delivered`
and `bounced` can never be written by anything in this repo"* — both are
provider facts and no email adapter with a feedback door has ever existed. So
**no code path has ever written a `bounced` row**, and the count measured on the
seeded lane database on 2026-09-17 was **0 rows in `outbound_messages` in any
status at all.**

**And if a deployment somewhere DOES hold one, it still must not be rewritten.**
A row reading `bounced` states *the provider bounced this and we do not know
which kind*. Guessing it into `bounced_hard` would put a live consumer's address
on a do-not-send list on no evidence and move their bills to paper for ever;
guessing it into `bounced_soft` would retry into a dead mailbox for ever. The
honest value for an unclassifiable row is the one it already has, so `bounced`
keeps its place in `STATUSES`, keeps its place on the failures index, keeps its
place in `REQUEUEABLE_STATUSES` (it is the only action available on it), and is
simply never written again.

REVERSIBLE, AND THE REVERSE IS NOT A DATA LOSS
────────────────────────────────────────────────────────────────────────────
`RemoveIndex` + `AddIndex` both ways. Reversing narrows the predicate back to
the two statuses; no row is touched in either direction, because a partial index
decides what is INDEXED and never what is stored.

⚠ **CONCURRENCY, STATED BECAUSE THIS TABLE IS THE BIGGEST ONE A UTILITY HAS.**
Django's `AddIndex` takes an `ACCESS EXCLUSIVE` lock for the build. On a T5
tenant (40,000 accounts — the top of the ICP, per CLAUDE.md) `outbound_messages`
carries of the order of one row per document per channel per month, so this is a
maintenance-window operation and not an online one. It is named here rather than
discovered: there is no `CONCURRENTLY` in this repo's migration vocabulary and
inventing one for this index alone would be a pattern nothing else follows.
"""

from django.db import migrations, models
from django.db.models import Q

#: Repeated as literals rather than imported from `apps.notifications.models`.
#: A migration is a record of what the schema was asked to become ON THIS DATE,
#: and importing a live constant makes the historical record change under a
#: later edit — the same reason every other migration in this module spells its
#: values out.
ATTENTION_STATUSES = (
    "failed",
    "bounced",
    "bounced_hard",
    "bounced_soft",
    "complained",
)


class Migration(migrations.Migration):

    dependencies = [
        ("notifications", "0017_def2496_notification_version_pin_lock"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="outboundmessage",
            name="ix_outbound_msgs_failed",
        ),
        migrations.AddIndex(
            model_name="outboundmessage",
            index=models.Index(
                condition=Q(status__in=ATTENTION_STATUSES),
                fields=["tenant", "-created_at"],
                name="ix_outbound_msgs_failed",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-NOT-5626 (12-governance/10-defect-log.csv) · 04-docs/05-modules/10-notifications/02-business-rules.md BR-NOT-005 + BR-NOT-013 + BR-NOT-1032 · apps/notifications/models.py STATUSES/ATTENTION_STATUSES/PROVIDER_OUTCOME_STATUSES · apps/notifications/dispatcher.py ALLOWED_TRANSITIONS · apps/notifications/delivery_ops.py REQUEUEABLE_STATUSES
# generated: 2026-09-17 by an AI lane (SendGrid/Postmark gap 3 — the normalised outcome vocabulary)
# checklist: A✔ B=deferred(no frontend half — this slice ships a vocabulary; the screen that shows a suppressed address is gap 4) C✔ D=deferred(no API call — a migration) E=deferred(as B) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_us_not_001_outbound_queue.py + tests/test_us_not_002_dispatcher.py + tests/test_us_not_013_015_delivery_ops.py, and tests/test_def_not_5626_normalised_outcomes.py::test_a_soft_bounce_retries_and_a_hard_bounce_is_refused_in_the_same_breath PROVED RED FIRST on real PostgreSQL 16 by putting bounced_hard back on REQUEUEABLE_STATUSES: `1 failed, 5 passed`, `AssertionError … Left contains one more item` — both rows re-queued. The migration itself was applied to a live PostgreSQL 16 and the predicate read back from pg_indexes
# exceptions: (1) NO DATA MIGRATION AND NO ROW REWRITTEN — see the docstring; `bounced` stays lawful because an unclassifiable bounce has no truthful successor. (2) NOTHING WRITES THE FOUR NEW VALUES — BR-NOT-013 still holds and no adapter exists; this ships the words the adapters will need, and `delivery_ops.UNPOPULATED_STATUSES` and `models.PROVIDER_OUTCOME_STATUSES` both say so rather than implying coverage (hard-won law 2: built is not wired, stated out loud). (3) THE INDEX BUILD TAKES AN ACCESS EXCLUSIVE LOCK — named in the docstring, not discovered.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

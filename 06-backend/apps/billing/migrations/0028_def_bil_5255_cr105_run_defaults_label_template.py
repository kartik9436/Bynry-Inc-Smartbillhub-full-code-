# ── Trace ──────────────────────────────────────────────
# Change:   `DEF-BIL-5255` (the run-level DEFAULTS group and the run label) +
#           `CR-105-BRC03` (the bill template is decided at step 1 Scope).
#           ONE migration for both, because both are columns on the same row
#           and a money-path migration is reviewed once.
#           Screens: S31 step 1 — the blueprint's screen 16 `Scope`, p046-p048
# Rules:    BR-BIL-1040 (a run carries its standing answers to the recurring
#           cases, resolved at creation) · BR-BIL-1041 (the run's template is
#           CHOSEN at Scope and its version is still PINNED at issue) ·
#           BR-BIL-015 (a missing read is a per-case staff choice — NOT
#           replaced; see the docstring's supersession note) · BR-BIL-025
#           (template resolves per account: override -> category -> tenant
#           fallback) · BR-BIL-026 (template + version pinned at issue and
#           frozen there) · BR-BIL-005 (a run is idempotent on tenant + cycle +
#           period — none of these three columns joins that key) ·
#           CLAUDE.md rule 4 (nothing already issued moves) · CLAUDE.md 🔒
#           sensitive paths (migration ordering — HUMAN-REVIEW-PENDING)
# ───────────────────────────────────────────────────────
# 🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING (PO 2026-08-09: "AI will do it; we will
# review it later as human") — row in 12-governance/09-human-review-ledger.md,
# dated 2026-09-14, stating in plain English with a figure what was shown.
# ───────────────────────────────────────────────────────
"""billing 0028 — three columns on `bill_runs`: the run's standing answers, its
label, and the template a clerk chose at Scope.

HUMAN-OWNED (migration ordering 🔒). HUMAN-REVIEW-PENDING — AI-authored
2026-09-14 under the PO ruling of 2026-08-09.

WHY ONE MIGRATION AND NOT TWO. `DEF-BIL-5255` and `CR-105-BRC03` are different
kinds of work — a defect against a drawing the PO already signed, and a change
the PO asked for on top of it — but they land on the SAME ROW of the SAME TABLE
and they are reviewed by the same person for the same reason. Two migrations
would be two reviews of one fact.

────────────────────────────────────────────────────────────────────────────
`case_defaults` — BR-BIL-1040, `DEF-BIL-5255`
────────────────────────────────────────────────────────────────────────────
Screen 16's `DEFAULTS` group, which the blueprint calls *"the single biggest
error-reducer in this redraw"*: three recurring decisions a clerk makes ONCE for
the whole run instead of hundreds of times per account — *when there is no
reading* (estimate from history), *when a bill looks unusually large* (hold it
for review), *unusual days* (pro-rate by days).

`jsonb`, keyed by CASE KIND, and deliberately not three typed columns with a
CHECK apiece. The case vocabulary is `apps.billing.decisions.CHOICES_BY_CASE`
and it has grown twice this month (CR-038 W8 added seven cases; `DEF-BIL-5270`
added `billing_continuity` on 2026-09-14). A CHECK constraint spelling the
choices out would be a SECOND copy of that vocabulary — the exact mistake
`apps/tenancy/settings_families.py` records beside `back_bill_cap_months`, where
a duplicated default leaves the tenant's screen and the engine's guard
disagreeing in silence. `runs.resolve_case_defaults` validates both halves of
every pair against the one vocabulary and refuses an unknown by name.

⚠ **IT DOES NOT SUPERSEDE BR-BIL-015, AND THE DISTINCTION IS LOAD-BEARING.**
That rule's no-pre-committed-default clause was reaffirmed by its author on
2026-08-26, verbatim: *"keep the rule — speed comes from the bulk button, not
from decisions nobody made; an auditor asking 'who chose to estimate M-4412?'
gets a name"*. Nothing here writes a `bill_run_decisions` row and the per-account
trail stays append-only. What this column stores is the RUN's standing answer,
and the name the auditor gets is the run's own `run_by` plus the
`bill_run.created` audit row, which now carries the map. The 2026-09-11
run-intent ruling — *"allow him to do all decision before hand"* — is the later
statement and is what the blueprint draws. **The supersession is stated rather
than assumed** (change process §2) and is recorded in the decision log.

────────────────────────────────────────────────────────────────────────────
`label` — `DEF-BIL-5255` ④
────────────────────────────────────────────────────────────────────────────
The clerk's own name for the run, drawn as `September, after the water rate
change` and read back by screen 16's `ALREADY RUN FOR THIS CYCLE` table, whose
`LABEL` column had nothing behind it. It is not `run_no` and not a status:
`run_no` is the series number a customer quotes, and `DEF-171`/`DEF-602` are the
defects where every finished run reads *Draft* for ever and two runs over one
period cannot be told apart by anyone. Free text, never parsed, never printed on
a bill, and NOT unique — two runs may honestly carry the same words.

────────────────────────────────────────────────────────────────────────────
`template_id` — BR-BIL-1041, `CR-105-BRC03`
────────────────────────────────────────────────────────────────────────────
PO ruling 2026-09-14, verbatim: *"in this step 1 scope - you will ahve to also
decide on billing template"*.

⚠ **DECIDING IS NOT STAMPING, AND THE FREEZE DOES NOT MOVE.** The column holds
the TEMPLATE and no version number. `assemble_document` still stamps template AND
version onto each invoice at ISSUE and freezes it there (BR-BIL-026), so a
template edited between Scope and Send cannot silently change a bill a clerk
already approved. A version pinned at Scope would be stale by Send on any tenant
that publishes in between — which is why the column is one FK and not two
columns.

WHAT ACTUALLY MOVES FORWARD IS THE REFUSAL. `issue.IssuedRun.template_problems`
already counts *"distinct reasons a bill could not resolve its own template, with
the number of bills each affected"* — so a bill CAN fail to find one, and today
that is discovered at ISSUE, after Scope, after Check, after the clerk signed
off. `runs.validated_template_pin` checks the two ways it fails — a template that
is not this tenant's, and a template with no PUBLISHED version — at creation.

FK, not a bare uuid, and `PROTECT`: a template a run is pinned to must not be
deletable out from under it, which is the same audit-lock BR-BIL-027 puts on a
version any bill has pinned. **No cross-module edge** — `bill_templates` is
billing's own table (migration 0018).

────────────────────────────────────────────────────────────────────────────
SAFETY
────────────────────────────────────────────────────────────────────────────
ALL THREE ARE NULLABLE WITH NO DEFAULT AND NO BACKFILL. Every run that exists
today gets NULL on all three, NULL means *this run predates the column*, and
nothing reads a NULL as a value: `resolve_case_defaults` is called on the
CREATION path only, `label` renders as blank, and a NULL `template_id` is
BR-BIL-025's per-account chain running exactly as it does today. **No
already-issued bill, due date or template pin can move** (CLAUDE.md rule 4).

NOT IN THE IDEMPOTENCY KEY. BR-BIL-005 keys a run on (tenant, cycle, period);
adding any of these would let one cycle-period be billed twice by changing a
dropdown or retyping a label — the identical reasoning that keeps `bill_date`
and `due_days` out of it.

NO MONEY MOVES. No rate, no amount, no currency and no ❄️ FROZEN B4/B5 figure is
touched, so no finance re-sign is triggered (change process step 2). The two
money-adjacent properties are that a standing answer must be a choice the case
actually offers, and that a pinned template must have a published version; both
are enforced in `runs.py` and both REFUSE rather than substitute.

RLS: NOTHING TO RE-POLICE. `bill_runs` has carried ENABLE + FORCE and the B2 §3
tenant-isolation policy since billing's W3 migration, and that policy is
ROW-scoped — three new columns on an already-policed table are covered the moment
they exist. The FK's target, `bill_templates`, carries its own policy from
migration 0019.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0027_rls_cr051_bill_run_breaks"),
    ]

    operations = [
        migrations.AddField(
            model_name="billrun",
            name="case_defaults",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="billrun",
            name="label",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="billrun",
            name="template",
            field=models.ForeignKey(
                blank=True,
                db_column="template_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pinned_bill_runs",
                to="billing.billtemplate",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: 04-docs/05-modules/07-billing/conformance/CR-105-BRC03-s03-element-inventory.md §5.1 (screen 16, p046-p048) · 12-governance/change-requests/CR-105-BRC03-bill-template-at-scope.md · 12-governance/10-defect-log.csv DEF-BIL-5255
# generated: 2026-09-14 by the billing schema lane (CR-105-BRC03 contracts 3 and 4)
# checklist: A✔ B=deferred(the Scope screen's three controls, the label box and the template chooser are a front-end wave) C✔(tests/test_br_bil_1040_run_case_defaults.py, proved on real PostgreSQL 16) D✔ E=deferred(no-frontend-half) F✔ G✔ H=PENDING(🔒 migration ordering — HUMAN-REVIEW-PENDING, ledger row written 2026-09-14)
# gates: makemigrations --check clean · billing suite green on PostgreSQL
# exceptions: none — three nullable columns, no backfill, no data touched
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

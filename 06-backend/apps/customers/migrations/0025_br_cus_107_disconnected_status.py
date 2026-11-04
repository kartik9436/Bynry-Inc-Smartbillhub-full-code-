# ── Trace ──────────────────────────────────────────────
# Change:   BR-CUS-107 — the sixth account status (PO ruling 2026-08-25,
#           closing DEF-701)
# Rules:    BR-CUS-107 (a cut account is `Disconnected`, class `non_billable`) ·
#           BR-CUS-055 (the seeded status vocabulary this amends) ·
#           BR-CUS-103 (why the class is not `billable_base_only`) ·
#           BR-TEN-012 (per-list idempotent; a tenant-touched row is never
#           overwritten) · BR-TEN-036 (a seeded row is deactivatable, never
#           deletable) · BR-TEN-030 (codes unique per list per tenant, CI) ·
#           CLAUDE.md rule 1 (tenant scoping)
# Impacts:  apps/customers/services.SEED_ACCOUNT_STATUSES (the ratified copy) ·
#           apps/tenancy/fixtures/lookup_defaults.json (V2.48.0.0) ·
#           apps/tenancy/reference_sweep.RATIFIED_FIXTURE_DIGESTS
# ───────────────────────────────────────────────────────
"""Seed BR-CUS-107's `Disconnected` status into every tenant that already exists.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — CLAUDE.md files *migration ordering* as a
🔒 sensitive path. AI-authored under the PO ruling of 2026-08-09 (*"AI will do
it; we will review it later as human"*); a row in
`12-governance/09-human-review-ledger.md` is OWED and this lane does not own
that file, so it is REPORTED rather than written.

════════════════════════════════════════════════════════════════════════════
WHAT THE PO RULED, AND WHY THE OTHER THREE CLASSES ARE CLOSED
════════════════════════════════════════════════════════════════════════════
BR-CUS-107, 2026-08-25, closing DEF-701: **a cut account gets a sixth status,
`Disconnected`, in behaviour class `non_billable`.** BR-CUS-055 seeded five —
Pending activation · Active · Marked disconnect · Vacation hold/Suspended ·
Closed — and none of them means *"the service is off"*. A cut account read
`Marked disconnect / billable`, which is the rung BEFORE the cut and whose own
seed comment says *"consuming until cut"* about a customer who has stopped
consuming (DEF-701, measured on `A-11340`).

The other three classes were each ruled out with a stated reason, so they are
not a later lane's to revisit: `billable` bills a service that no longer runs;
`billable_base_only` was eliminated by the PO's OWN answer the same day
(BR-CUS-103 — base stops at the cut, so there is no base to bill); `terminal`
is what `Closed` means, and a cut account is not closed — it holds a debt, it
can pay, and it comes back.

**Worked, on a real seeded account:** `A-11488`, cut **2026-08-18** owing
**$612.75**, reads `Disconnected / non-billable`; nothing accrues (BR-CUS-103),
the $612.75 stays owed, and `mark_reconnecting` can still take it back.

════════════════════════════════════════════════════════════════════════════
WHY A MIGRATION AND NOT ONLY THE FIXTURE BUMP
════════════════════════════════════════════════════════════════════════════
The row is in `lookup_defaults.json` at V2.48.0.0 and the sweep will deliver it
to every tenant behind that version. But the sweep is a JOB somebody runs, and
`_seed_reference_data` skips a list whose seed-run row already sits at the
current version — so on a deployment where nobody runs it, the sixth status
would exist for NEW tenants and for nobody else. That is 2026.08.2's
undelivered fix in a different list (DEF-213's entry in
`reference_sweep.RATIFIED_FIXTURE_DIGESTS` records what it cost).

So this migration inserts the row directly, per tenant, insert-missing. Running
it and then running the sweep is harmless: both are `get_or_create` on
(tenant, code), and BR-TEN-012 says an existing row is never overwritten — a
tenant that has already renamed it keeps its own label.

════════════════════════════════════════════════════════════════════════════
WHY IT MATCHES ON `code` CASE-INSENSITIVELY
════════════════════════════════════════════════════════════════════════════
BR-TEN-030 makes codes unique per list per tenant CASE-INSENSITIVELY, so a
tenant that already added its own `Disconnected` row through the S8 card must
not be handed a second one that the unique index would then refuse. The
`iexact` probe is the same one `services._seed_reference_data` uses.

════════════════════════════════════════════════════════════════════════════
⛔ THIS MIGRATION SEEDS A STATUS. IT ASSIGNS IT TO NO ACCOUNT.
════════════════════════════════════════════════════════════════════════════
No `accounts` row is read or written here, and `disconnects.commit_cut` still
writes none either — `DSC-02.4`'s prohibitions stand untouched. Two measured
consequences of the CLASS have to be closed before anything moves an account
onto this row, and both are reported rather than decided:

  1. **OCCUPANCY.** `services.OCCUPYING_BEHAVIOR_CLASSES` is
     (billable, billable_base_only), so an account on this row stops occupying
     its unit — the unit reads vacant and pickable for another move-in, and
     `move_out`, transfer, change-plan and payment-plan all refuse the cut
     customer with `not_an_occupant`. `DSC-02.4` cuts *"leaving the account
     open"* and BR-MET-036 flips a unit to Vacant when the account is CLOSED,
     which a cut account is not.
  2. **BILLING DROPS THE WHOLE ACCOUNT.**
     `billing.stages.resolve_subscription.CLASSES_THAT_BILL` bills neither
     `non_billable` nor `terminal`, so a cut account becomes a NON-RETRYABLE
     break on every run's phase-3 exception list and the usage it consumed
     BEFORE the cut is never billed. BR-CUS-103 does not need this row to stop
     base — it stops it by subtracting the dark days from `service_days`, which
     only runs on an account billing has not dropped.

════════════════════════════════════════════════════════════════════════════
REVERSIBILITY
════════════════════════════════════════════════════════════════════════════
Reverse deletes only rows that are still EXACTLY as seeded — `is_system`, the
ratified name, the ratified class, and no account pointing at them. A row a
tenant has renamed, re-classed or used is left alone: BR-TEN-036 makes a seeded
row deactivatable and never deletable, and a reverse that deleted a status an
account references would take the account's status with it.
"""

from django.db import migrations

#: BR-CUS-107, verbatim. A COPY, deliberately: a migration must survive a later
#: edit to `services.SEED_ACCOUNT_STATUSES`, and the two are pinned equal by
#: `tests/test_br_cus_107_disconnected_status.py`.
STATUS_CODE = "disconnected"
STATUS_NAME = "Disconnected"
STATUS_BEHAVIOR_CLASS = "non_billable"


def forwards(apps, schema_editor):
    AccountStatus = apps.get_model("customers", "AccountStatus")

    tenant_ids = list(
        AccountStatus.objects.order_by("tenant_id").values_list("tenant_id", flat=True).distinct()
    )
    for tenant_id in tenant_ids:
        if AccountStatus.objects.filter(tenant_id=tenant_id, code__iexact=STATUS_CODE).exists():
            # BR-TEN-012 — an existing row is never overwritten, including one
            # a tenant added itself before this landed.
            continue
        AccountStatus.objects.create(
            tenant_id=tenant_id,
            code=STATUS_CODE,
            name=STATUS_NAME,
            behavior_class=STATUS_BEHAVIOR_CLASS,
            is_system=True,
            active=True,
        )


def backwards(apps, schema_editor):
    AccountStatus = apps.get_model("customers", "AccountStatus")
    Account = apps.get_model("customers", "Account")

    rows = AccountStatus.objects.filter(
        code__iexact=STATUS_CODE,
        name=STATUS_NAME,
        behavior_class=STATUS_BEHAVIOR_CLASS,
        is_system=True,
    )
    used = set(
        Account.objects.filter(status_id__in=rows.values_list("id", flat=True))
        .values_list("status_id", flat=True)
        .distinct()
    )
    rows.exclude(id__in=used).delete()


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("customers", "0024_cr030_w7_cut_reconnect"),
    ]

    operations = [migrations.RunPython(forwards, backwards)]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-020@2bd3053d (EP-CUS-07 account onboarding + reference data, at
#         the sha it was read at — `git log -1 --format=%h -- 04-docs/05-modules/
#         03-customers/06-epics/EP-CUS-07-account-onboarding.md`) · BR-CUS-107
#         (PO ruling 2026-08-25 closing DEF-701: a cut account gets a sixth
#         status, `Disconnected`, in behaviour class `non_billable`) · BR-CUS-055
#         (the five it amends) · BR-CUS-103 (why not `billable_base_only`) ·
#         BR-TEN-012 · BR-TEN-030 · BR-TEN-036 · BR-TEN-077 (the fixture bump
#         this migration backstops)
# generated: 2026-08-25 by lane DISCSTATUS (BR-CUS-107 / DEF-701)
# checklist: A✔ B✔ C✔(tests/test_br_cus_107_disconnected_status.py — 9 cases, five guards proved RED first in a scratchpad copy) D=deferred(no-API-half — a reference row has no endpoint of its own; the S8 lookup CRUD already serves the list) E=deferred(no-frontend-half — the pill renders the tenant's own status_name; the one frontend change this ruling forced is customersShared.isDraftAccount) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — measured, not claimed. G7 gains exactly one
#         problem from this file ("no row in the human-review ledger", 31 → 32)
#         and it closes when the OWED ledger row lands; this lane does not edit
#         12-governance and REPORTS the row instead.
# exceptions: (1) THE ROW IS SEEDED AND ASSIGNED TO NO ACCOUNT. `commit_cut`
#         still writes no `accounts` column, so DEF-701's symptom — a cut account
#         reading `Marked disconnect / billable` on S17/S21 — is NOT yet fixed.
#         Two consequences of the `non_billable` CLASS are measured and must
#         close first, and neither is a reason to pick a different class
#         (BR-CUS-107 ruled the other three out): an account on this row stops
#         OCCUPYING its unit, and billing DROPS it from the run entirely rather
#         than merely stopping its base. Both are asserted in the test file and
#         named in `disconnects.DISCONNECTED_STATUS_NOT_ASSIGNED`.
#         (2) The occupancy boundary is derived from the CLASS
#         (`services.OCCUPYING_BEHAVIOR_CLASSES`), and BR-MET-036 + `DSC-02.4`
#         together say a cut account still holds its premises. Reconciling those
#         is a ruling plus a decision-log row, not a side effect of seeding a
#         status — REPORTED, and a new open question is OWED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Change:   CR-067 task A1 — the diagnostic record: table + migration, its own
#           retention, NO FK into `audit_log` (12-governance/11-change-requests.md)
# Rules:    CLAUDE.md hard rule 1 (tenant scoping, RLS FORCE — the policy lands
#           in the SAME migration as the table) · BR-AUD-002 (the audit log has
#           no write verbs — which is WHY this table exists beside it rather
#           than inside it) · BR-AUD-006 (PII masked only) · BR-AUD-015 (the
#           precedent for a bare `tenant_id` in this module)
# Tests:    06-backend/tests/test_cr067_diagnostics.py
# ───────────────────────────────────────────────────────
"""`error_diagnostics` — the technical half of one failure, and it EXPIRES.

WHY IT IS A SEPARATE TABLE AND NOT COLUMNS ON `audit_log`
----------------------------------------------------------
CR-067 §3, as approved:

| | the audit row | the diagnostic record |
|---|---|---|
| Lifetime | permanent — never edited, never deleted | expires on its own schedule |
| Holds | what was attempted · who · when · a stable code · **the reference** | the error and where in the code · the request's field NAMES · tenant · release · the settings in force · the job |
| Never holds | anything private, because it cannot be removed | a field VALUE, an account number, a balance, a reading, a credential |

Two lifetimes cannot live in one row. `audit_log` is append-only by trigger and
by rule (BR-AUD-002) — there is no path that deletes from it, deliberately — so
anything written there is written for the retention life of the trail. This
table is pruned on a schedule, which is only possible because it is not that
table.

WHY THERE IS NO FOREIGN KEY, IN EITHER DIRECTION
-------------------------------------------------
CR-067 §3 / task A1 is explicit, and the reason is the lifetimes again: a
foreign key would make one record hostage to the other's retention. An FK from
here into `audit_log` would refuse the prune (or cascade into a permanent row,
which is worse); an FK the other way would refuse to write a trail row when a
diagnostic was refused or expired.

**They join on `reference`, which is a VALUE and not a constraint.** The audit
row's payload carries `reference: "5F2B-9C1D"`; this table carries the same
string. A drawer that finds no diagnostic for a reference is a NORMAL state —
the record expired — and the permanent row still reads correctly on its own.

`tenant_id` IS A BARE UUID, LIKE `audit_log`'s
-----------------------------------------------
Same module, same reason as BR-AUD-015: no cross-module foreign key is added
from `apps.audit` into `tenancy.tenants`, so removing a tenant never cascades
or blocks here. What removes a tenant's diagnostics is the retention sweep and
the day-91 offboarding purge, both of which delete rows explicitly — a
lifetime enforced by a job that can be read, not by a constraint that fires
invisibly.

RLS is what scopes it: `error_diagnostics_tenant_isolation`, the signed B2 §3
template, applied in the same migration that creates the table (CLAUDE.md rule
1 — a table that exists for even one migration without its policy is a table
any tenant can read). Another tenant's diagnostic is **absent** under this
tenant's scope, not forbidden.

WHAT THE COLUMNS MAY HOLD — THE ONE RULE THIS TABLE LIVES UNDER
----------------------------------------------------------------
Every text column here is filled by `core.diagnostics`, whose signature accepts
**names and never values**. `request_fields` is a list of field NAMES;
`settings_in_force` is read from `django.conf.settings` by the writer itself
through a secret filter; `exception_type` is a class name; `frames` are file,
function and line. **`str(exc)` is never stored.** The guarantee is the
writer's signature, not this docstring — see `core/diagnostics.py`.
"""

from django.db import models

from core.dbfields import uuid7_pk


class ErrorDiagnostic(models.Model):
    """One reproducible account of one failure, joined to its audit row by value."""

    id = uuid7_pk()
    #: BR-AUD-015's shape — a bare uuid, not an FK. See the module docstring.
    tenant_id = models.UUIDField()
    #: `5F2B-9C1D` — the first eight hex of `trace_id`, uppercased and grouped.
    #: The same string the audit row's payload carries and the same one
    #: `supportRef()` forms in `07-frontend/src/api/client.ts`.
    reference = models.TextField()
    #: The full 32-hex trace id, so a server log line can still be found by
    #: `grep` for the whole of it rather than only its first eight characters.
    trace_id = models.TextField()
    #: The stable code the audit row also carries — one vocabulary, not two.
    error_code = models.TextField()
    #: WHERE in the product, as a name: `tenancy:sample_data`.
    component = models.TextField()
    exception_type = models.TextField()
    exception_module = models.TextField()
    #: `__cause__` / `__context__` as TYPES, innermost last — hard-won law 14's
    #: "the driver's exception is two or three hops down".
    exception_chain = models.JSONField(default=list, blank=True)
    #: `[{file, function, line}]`, outermost first. No source text, no message.
    frames = models.JSONField(default=list, blank=True)
    #: `{SETTING_NAME: value}` — read by the writer, never passed to it.
    settings_in_force = models.JSONField(default=dict, blank=True)
    #: Field NAMES only. A value here is a bug in the caller and is refused.
    request_fields = models.JSONField(default=list, blank=True)
    job_kind = models.TextField(null=True, blank=True)
    job_id = models.TextField(null=True, blank=True)
    #: Which step of the job, and of how many — "step 8 of 17".
    step = models.IntegerField(null=True, blank=True)
    step_total = models.IntegerField(null=True, blank=True)
    #: The `audit_log.action` of the permanent row this pairs with. A NAME, so
    #: the drawer can confirm the pairing without a foreign key.
    audit_action = models.TextField(null=True, blank=True)
    release = models.TextField()
    created_at = models.DateTimeField()
    #: Stamped at WRITE time from `DIAGNOSTIC_RETENTION_DAYS`, never computed at
    #: read time. Shortening the setting must not retroactively expire records
    #: somebody is already looking at, and lengthening it must not resurrect
    #: ones a person was told were gone.
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "error_diagnostics"
        indexes = [
            # The join: "show me the detail for 5F2B-9C1D", inside one tenant.
            models.Index(fields=["tenant_id", "reference"], name="ix_err_diag_reference"),
            # The list read: newest first, inside one tenant.
            models.Index(fields=["tenant_id", "created_at"], name="ix_err_diag_recent"),
            # The sweep: everything past its date. Tenant-first because the
            # sweep runs INSIDE a tenant's context (RLS FORCE), one at a time.
            models.Index(fields=["tenant_id", "expires_at"], name="ix_err_diag_expiry"),
        ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-067 task A1 (12-governance/11-change-requests.md §3 the approved shape, §6 the task table) + B2 §3 (the signed RLS template) + BR-AUD-002/BR-AUD-015
# generated: 2026-09-02 by the CR-067 backend lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09) — ⚠ AMENDED 2026-09-02 by the CR-067 B2/B3 lane: B, D and E read `deferred(no endpoint of its own)` and that is what DEF-3321 quoted as its evidence. `GET /audit-log/{id}/diagnostic` serves this table now, behind `SystemAdminOnly`, and the S61 drawer draws it (hard-won law 1 — a trailer that outlives its fact is read as current).
# gates: see the lane report
# exceptions: (1) NO FK to `audit_log` in either direction and NO FK to `tenancy.tenants` — both stated in the docstring with their reasons (different lifetimes; BR-AUD-015's no-cascade posture). (2) `expires_at` is STAMPED, not derived at read time, so changing the retention setting cannot retroactively expire or resurrect a record.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

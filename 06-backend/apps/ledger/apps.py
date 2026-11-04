# ── Trace ──────────────────────────────────────────────
# Change:   P4.1 + P4.10 (Finance blueprint p017) — the seven Finance reports
#           become export resources on the ONE kernel tenancy hosts.
# Rules:    BR-TEN-031 (the OWNING module registers its own exportable lists) ·
#           BR-REP-018 (IS-11 downloads) · BR-SHL-016 (server-side, streamed,
#           capped, audited)
# Tests:    06-backend/tests/test_p4_1_finance_exports.py
# Impacts:  apps/ledger/finance_exports.py (registered here) ·
#           config/settings/base.py INSTALLED_APPS ("apps.ledger")
# ───────────────────────────────────────────────────────
"""ledger AppConfig — registration only, no logic.

The ledger module ran for six weeks with no AppConfig at all, which was correct
while it registered nothing: Django imports `apps.ledger.models` by default and
that was the whole of what the app registry needed.

`P4.1` changes that. Finance now declares seven downloads — the trial balance,
remittance by authority, the account ledger, by premises, the customer
statement, the export preview and revenue by service — and an export resource
exists only if the module that OWNS the list registers it at startup, which is
`BR-TEN-031` and is the same posture `apps/reports/apps.py` takes for the four
report viewers and `apps/metering`, `apps/assets` and `apps/rating` take for the
nine lists. **Registration is the only thing that happens here**, and the
alternative — importing `finance_exports` from some module that happens to load
— is how a deployment ends up with a resource that exists on one process and
404s on another.

⚠ **`default_auto_field` IS DECLARED AND IT CHANGES NOTHING.** Every ledger
model names its own primary key explicitly, so no field is auto-created from
this setting; it is here because an AppConfig without it makes Django emit a
`models.W042` warning per model, and a new warning in a clean run is noise that
trains people to stop reading warnings.
"""

from django.apps import AppConfig


class LedgerConfig(AppConfig):
    name = "apps.ledger"
    label = "ledger"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.ledger import finance_exports

        finance_exports.register()


# ── Lifecycle ─────────────────────────────────────────────
# packet: P4.1 + P4.10 (05-prototype/07 Finance Blueprint.pdf p017 · apps/reports/apps.py, the precedent this copies verbatim)
# screens: 6·2 Export · 4·1 By authority · S38 · S59 · S60
# generated: 2026-09-24 by lane FIN-P4
# checklist: A✔ B✔ C=deferred(registration only) D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

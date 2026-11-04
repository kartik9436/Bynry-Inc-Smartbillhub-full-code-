# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-009 (the S8 card grid the handlers make live) · US-CUS-001
#           (the S17 status vocabulary) · US-CUS-003 (the S18 customer-type
#           select)   Screens: S8 · S17 · S18
# Rules:    BR-TEN-031 (the OWNING module registers the handler for its
#           reference lists; tenancy renders and routes) · BR-CUS-055 (account
#           statuses are Reference data) · BR-TEN-036 (seeded +
#           tenant-extensible)
# Tests:    06-backend/tests/test_us_cus_schema_and_seed.py
# Impacts:  apps.tenancy LOOKUP_LISTS (`account_statuses`, `account_types`) ·
#           /lookups/{list} endpoints · reference_data_report() counts
# ───────────────────────────────────────────────────────
"""customers AppConfig — registration only, no logic.

The app had no AppConfig at all before this slice, so Django used the default
one and nothing in this module ever ran at startup. That is precisely why
tenancy's registry carried two `handler=None` entries: the code to register
them had nowhere to be called from.

Registration is defensive: a tenancy registry that does not know a list code
must not break app startup for a deployment that has not landed that lane.
"""

from django.apps import AppConfig


class CustomersConfig(AppConfig):
    name = "apps.customers"
    label = "customers"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.customers import lookups, search_sources

        lookups.register()
        # US-SHL-003 — FOUR of universal search's nine groups (accounts, master
        # accounts, customers, service requests). Registered HERE because the
        # module that owns the table owns its query (core/search.py's BE-08
        # contract: "core owns NO queries"). ⚠ A group whose source is never
        # registered does not error — it simply never appears in the popover,
        # which is hard-won law 2 wearing a search box, so these three lines sit
        # beside the file they register rather than anywhere a lane can forget.
        search_sources.register()
        # PO 2026-10-17 (`DEF-CUS-10180`) — the Accounts list's download, with
        # Opened, Account age and Aging in it. A resource never registered is a
        # Download button the screen cannot render (BR-SHL-010), so it sits here.
        from apps.customers import exports as customer_exports

        customer_exports.register()
        # PO 2026-09-20 — *"Something has to read cut dates daily and surface
        # what's due"*. ⚠ THIS LINE IS THE ONLY THING THAT MAKES THE WATCH REAL:
        # `beat_schedule()` being CORRECT and the entry being INSTALLED are two
        # different claims, and hard-won law 2 is about exactly that gap. It is
        # the same path `notifications`, `payments` and `work` install their
        # entries from. `install()` never raises: a deployment without celery
        # logs `installed: False` and the application starts.
        from apps.customers import disconnect_schedule

        disconnect_schedule.install()
        # CR-183-BRC10 T4 — a temporary stop starts on its stop date and ends on
        # its restart date by itself. Installed here for the same reason as the
        # line above (G132 reads this call in the syntax tree).
        from apps.customers import temporary_stop_schedule

        temporary_stop_schedule.install()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-001@a2e1d59 (story+rules snapshot — EP-CUS-01 lead story; co-packets EP-CUS-02@bbed56d · customers 02-business-rules@f125a9c)
# generated: 2026-08-10 by story-coder (W2 customers SCHEMA + SEAM slice)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — registration only) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — ruff✔ black✔ · pytest tests -m "not golden and not isolation"✔ · run_gates 14-PASS/0-FAIL/1-SKIP✔
# exceptions: none — registration only. No exporter is registered (US-SHL-008's account list export belongs to the accounts-list slice, which owns the columns it would export)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

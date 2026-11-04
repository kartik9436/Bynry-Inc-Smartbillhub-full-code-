# ── Trace ──────────────────────────────────────────────
# Story:    US-AST-001 (BR-AST-031 lifecycle stages + BR-AST-004 types are
#           Reference data — the lists the S49 registry keys off) ·
#           US-AST-002 (creation cannot happen without a seeded stage) ·
#           US-TEN-009 (the S8 card grid the handlers make live)
#           Screens: S49, S8 (Settings → Reference data)
# Rules:    BR-AST-031 (stages seeded + tenant-extensible, behavior classes) ·
#           BR-AST-004/009/042 (type set) · BR-AST-043 (meter_types +
#           read_methods) · BR-TEN-031 (owning module supplies the /lookups
#           handler) · BR-TEN-036 (seeded + tenant-extensible)
# Tests:    06-backend/tests/test_us_ast_001_003_registry.py
# Impacts:  apps.tenancy LOOKUP_LISTS (all four: `asset_types`,
#           `asset_statuses`, `meter_types`, `read_methods` — verified
#           declared, CR-028 debt sweep D7 2026-08-22) ·
#           /lookups/{list} endpoints · every asset write path
# ───────────────────────────────────────────────────────
"""assets AppConfig — registration only, no logic.

BR-TEN-031: the OWNING module registers the handler for its reference lists;
tenancy renders and routes. `asset_types`, `asset_statuses` and `meter_types`
are declared in tenancy's LOOKUP_LISTS with owner "metering" (the tables are
metering-owned, hosted in this app — see models.py), so the handlers are
registered from here. `read_methods` (BR-AST-043) IS declared in
LOOKUP_LISTS too — the gap this paragraph used to report was closed by the
tenancy-side lanes and re-verified by the CR-028 debt sweep (D7,
2026-08-22): all four handlers register without a skip and the S8 cards
render.

Registration is defensive: a tenancy registry that does not know a list code
must not break app startup for a deployment that has not landed that lane.
"""

import logging

from django.apps import AppConfig

logger = logging.getLogger("smartbillhub.assets")


class AssetsConfig(AppConfig):
    name = "apps.assets"
    label = "assets"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.assets import exports, lookups, search_sources

        lookups.register()
        # US-SHL-008: S49's registry export — this module owns the list, so it
        # owns the exporter (same posture as the lookup handlers above).
        exports.register()
        # US-SHL-003 — the `assets` group of universal search, NEW by PO ruling
        # 2026-09-03. Same posture again: the module that owns the table owns
        # its query. ⚠ An unregistered group does not error, it is simply ABSENT
        # from the popover — hard-won law 2 wearing a search box — so this line
        # lives beside the file it registers.
        search_sources.register()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AST-001@9d8d058 (story+rules snapshot hash — EP-AST-01 registry story)
# generated: 2026-08-09 by story-coder v1 (W1 metering + assets feature lane) · AMENDED 2026-08-09 by story-coder (BR-AST-043 reference-data gap lane — meter_types + read_methods)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — registration only) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: [list-export lane 2026-08-10] ruff✔ black✔ py_compile✔ · pytest tests/test_be_list_export.py 49 passed✔ · suite `pytest tests -m "not golden and not isolation"` 762 passed / 7 skipped / 47 deselected (713 was the baseline when this lane started; the 49 new TCs are this lane's) · `-m isolation` 14 passed / 22 postgres-only skipped · migrate from empty✔ makemigrations --check --dry-run clean✔ (no migration in this lane) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · frontend tsc✔ eslint✔ vitest 501 passed / 132 todo across 43 files✔ (487+130 baseline) · ruff✔(E4/E7/E9/F select — the bar the baseline passes) black✔ migrate-from-empty✔ makemigrations --check✔ · suite `pytest tests -m "not golden and not isolation"` 587 passed / 8 skipped (580 baseline green + the 7 new BR-AST-043 TCs) · `-m isolation` 14 passed / 20 postgres-only skipped (13 baseline + 1 new) · run_gates 11-PASS/0-FAIL/1-SKIP✔ · trace_lint✔ · migration 0003 data path exercised on a scratch file-backed sqlite DB seeded at 0002 (ami→AMI, 'AMR'→amr case-insensitively, 'na'→NULL+logged, NULL→NULL; reverse restores the codes and drops both tables) · mypy NOT INSTALLED in this environment (B8 strict scope noted — recorded, not skipped silently)
# exceptions: none — registration only · BR-AST-043 gap lane 2026-08-09: two more handlers registered from ready(); `read_methods` has no tenancy LOOKUP_LISTS entry yet, so it takes the defensive skip-until-wired path — REPORTED · CR-028 debt-sweep lane 2026-08-22 (D7): the entry EXISTS in tenancy's LOOKUP_LISTS now — verified, stale claims here and in lookups.py corrected; the defensive path stays as the law for future lists
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

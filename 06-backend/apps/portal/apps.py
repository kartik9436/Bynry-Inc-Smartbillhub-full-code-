# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-069 (EP-CWP-12) — the portal module exists and a System
#           Admin can switch it on. Screens: CWP-069 · CWP-070 · CWP-001
# Rules:    BR-CWP-011 (the guest edge and the portal edge are separate
#           files and separate middleware) · BR-CWP-012 (no second copy of any
#           owning module's data) · CR-068 §11b (a tenth code module, not a
#           widening of an existing one)
# Tests:    06-backend/tests/test_us_cwp_069_settings.py
# Impacts:  config/settings/base.py INSTALLED_APPS ("apps.portal") ·
#           config/urls.py (two includes: guest, back office — the portal edge
#           arrives with its first route, wave E)
# ───────────────────────────────────────────────────────
"""portal AppConfig — the customer web portal's own module (`CR-068`).

The portal owns FIVE tables (`03-field-map.md` §1) and reads everything else
through seams (`apps/portal/seams/`). Wave A creates the first of the five,
`portal_settings`; the other four arrive with the waves whose stories fill
them, and nothing here pre-declares them (a table nobody reads is what G74
exists to catch).

Nothing registered at `ready()` in wave A. ⚠ **FROM 2026-10-02 ONE THING
DOES: the nightly clean-up of unsent applications** (`draft_cleanup.py`, PO
ruling 2026-10-02 — an unsent application and its files are deleted 30 days
after the applicant's last visit). `ready()` is the one hook that runs in every
process that could be celery beat, and `G132` fails the build when a module
declares a `BEAT_ENTRY` its own `ready()` does not install.
"""

from django.apps import AppConfig


class PortalConfig(AppConfig):
    name = "apps.portal"
    label = "portal"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # ⚠ THIS CALL IS WHAT MAKES THE NIGHTLY CLEAN-UP REAL (hard-won law 2):
        # `draft_cleanup.beat_schedule()` being correct and the entry being
        # INSTALLED are two claims. `install()` registers only — it starts
        # nothing, reads no clock, touches no table, and never raises.
        from apps.portal import draft_cleanup

        draft_cleanup.install()

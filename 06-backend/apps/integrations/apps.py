# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-013 (EP-INT-05) — the manifest registry is filled at
#           `AppConfig.ready()`, and a bad manifest refuses to start the process.
# Rules:    BR-INT-037 (configuration is data, not code) · BR-INT-028 (a
#           provider is a set of operations) · CR-069 §13 gate 3 (idempotency
#           mode and completion mode are refused at registration, never at run
#           time) · CLAUDE.md hard-won law 3 (defaults fail closed — a manifest
#           that cannot be trusted stops the process rather than the first batch)
# Tests:    06-backend/tests/test_us_int_013_registry.py (TC-2: the refusal
#           names the provider and the operation; TC-6: a coming-soon card has
#           no adapter and nothing raises)
# Impacts:  config/settings/base.py INSTALLED_APPS already names
#           "apps.integrations" (line ~99) with no config class — Django picks
#           this one up as the module's only AppConfig subclass.
# ───────────────────────────────────────────────────────
"""integrations AppConfig — registers the seventeen manifests, and nothing else.

`ready()` runs once per process, before any request and before any job body.
It calls `manifests.register_all()`, and the registry refuses the first bad
manifest BY NAME — `manifest refused — payments_kiosk · payments: no completion
mode declared` — so `manage.py check`, `runserver`, `migrate` and the test
session all stop on the developer's machine, which is where a configuration
error is cheap (US-INT-013 TC-2). Refusing at run time instead would fail the
first real batch at 06:02 on the first of the month.

Wave B (US-INT-015 · 016) adds two more registrations, in this order and
after the manifests, because both read the registry:

  * `adapters.register_all()` — binds each REAL adapter class to its LIVE
    manifest; the registry refuses a binding to a coming-soon provider by
    name (BR-INT-001). The list is EMPTY until wave E's first adapter.
  * `jobs.register()` — the five `integration.*` job kinds on the
    `integrations` queue (`core.jobs.set_job_queue`, read by
    `config/celery_routes.py`) and the two bodies that exist. The CONSUMER
    half is `docker-compose.yml`'s `celery-integrations` (`-Q integrations`)
    — BR-INT-041, both halves in one commit, `G80` refuses either alone.

No export resource and no signal.

⚠ **ONE MORE THING `ready()` CAN DO, AND IT IS FENCED THREE WAYS (wave K).**
`NEPTUNE_RECORDED=1` binds the RECORDED water-meter head-end
(`neptune_fixtures.RecordedHeadEnd`) into the server process, so the wave-K
walkthrough can drive a real screen over a real runner without dialling a real
vendor. It is refused unless **`DEBUG` is on**, so a production process cannot
be talked into answering from a fixture by an environment variable; it logs a
line saying it happened, because a silent fake provider is the worst possible
version of this; and the variable has to be typed, which is hard-won law 3 —
the unsafe option is the one you type.
"""

import logging
import os

from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class IntegrationsConfig(AppConfig):
    name = "apps.integrations"
    label = "integrations"  # unchanged from Django's default, so no migration moves
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        # Refuses at LOAD: a manifest missing a declared value stops the process
        # here, naming the provider and the operation (registry.ManifestError).
        from apps.integrations import adapters, jobs, manifests

        manifests.register_all()
        adapters.register_all()
        jobs.register()
        self._bind_recorded_head_end()

    @staticmethod
    def _bind_recorded_head_end() -> None:
        """Wave K's walkthrough seam. Refused unless DEBUG; announced when taken.

        ⚠ **THE `DEBUG` GUARD IS THE WHOLE SAFETY OF THIS**, and it is checked
        HERE rather than trusted to deployment: an environment variable is a
        thing an operator can set by accident, and a production process
        answering meter readings from a fixture would be indistinguishable from
        a working one until somebody reconciled a bill.
        """
        if os.environ.get("NEPTUNE_RECORDED") != "1":
            return
        if not getattr(settings, "DEBUG", False):
            logger.warning(
                "NEPTUNE_RECORDED is set and DEBUG is off — the recorded head-end "
                "is NOT bound; this process talks to the real provider or to nothing"
            )
            return
        from apps.integrations import neptune_fixtures
        from apps.integrations.adapters import meters_neptune360

        meters_neptune360.HEAD_END_CLIENT = neptune_fixtures.RecordedHeadEnd()
        logger.warning(
            "NEPTUNE_RECORDED=1 — the water meter cloud is answering from a RECORDED "
            "fixture in this process. Nothing here reaches a real head-end."
        )

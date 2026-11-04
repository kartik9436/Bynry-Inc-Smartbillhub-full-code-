"""App config — registers the audit store as the kernel's sink at startup (US-AUD-001).

CR-067 added a SECOND sink from the same place and for the same reason: the
diagnostic record lives in this module's table, and `core.diagnostics` must not
import an app model. See `apps/audit/diagnostics.py`.
"""

from django.apps import AppConfig


class AuditConfig(AppConfig):
    name = "apps.audit"
    label = "audit"

    def ready(self) -> None:
        # Import here: models are only loadable once the app registry is populated.
        from . import services

        services.register()
        # CR-067 task A1 — `error_diagnostics` lives in its own module for the
        # reason `apps/tenancy/document_models.py` does: a table with its own
        # argument about lifetime and redaction belongs beside that argument.
        # Imported HERE because Django registers a model when the module
        # defining it is imported during app loading, and nothing else imports
        # this one.
        from . import diagnostic_models  # noqa: F401
        from . import diagnostics

        diagnostics.register()

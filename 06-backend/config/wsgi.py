"""WSGI entry point — what gunicorn imports in production.

    gunicorn config.wsgi:application

Deployment blocker closed 2026-08-10: the AWS runbook (09-infra/02) found the
project had no wsgi/asgi module at all, so no production server could start it.
Local dev uses `manage.py runserver`, which never needs this file — which is
exactly why its absence stayed invisible until the first real deploy was planned.

Settings default to production here, not local: a container that somehow starts
without DJANGO_SETTINGS_MODULE must fail closed (DEBUG off, secrets required),
never boot into dev settings on a public port.

⚠ DEF-2717 — this module also asks whether the connection gunicorn is about to
serve on actually OBEYS row-level security, and refuses to produce an
`application` when it does not. PostgreSQL exempts superusers and BYPASSRLS
roles from RLS unconditionally, FORCE included, and nothing observable says so —
so a process serving on such a connection answers every request with tenant
isolation switched off and no error anywhere. The check lives here, and not only
in `docker-entrypoint.sh`, because this is the one module gunicorn imports
however it was started; an entrypoint can be bypassed by a `command:` override,
a one-off task or a `docker run`. `core/rls_guard.py` argues the whole posture.
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_wsgi_application()

# AFTER get_wsgi_application(), which is what runs django.setup() — the settings
# and the connection do not exist before it. Raises ImproperlyConfigured when the
# role bypasses RLS and nobody typed the escape hatch (hard-won law 3); prints one
# line and continues in every other case, INCLUDING when the database is
# unreachable — turning a transient outage into a refusal to boot would be a
# self-inflicted incident, and a guard that fails on the wrong condition is the
# guard the next lane disables.
from core import rls_guard  # noqa: E402  (must follow django.setup())

rls_guard.enforce_at_startup()

# DEF-TEN-9190 — the web process hands out every export's signed link, so it
# says where exports live and refuses to serve when they live nowhere (outside
# DEBUG). NO network probe here, deliberately: each gunicorn worker imports this
# module, and a slow bucket must not hold a worker's boot inside gunicorn's own
# timeout. The celery worker, which uploads, is the one that probes.
from core import storage_guard  # noqa: E402

storage_guard.enforce_export_storage_at_startup(process="web", probe_network=False)

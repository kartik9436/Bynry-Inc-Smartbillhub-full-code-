"""ASGI entry point — for an async server (uvicorn) if the deployment chooses one.

    uvicorn config.asgi:application

Same fail-closed settings default as wsgi.py: a container starting without
DJANGO_SETTINGS_MODULE lands on production settings, never on dev.
The app is synchronous today (TD-19 DRF); this exists so the choice of server
is the DevOps engineer's, not a code change.
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

application = get_asgi_application()

"""Celery app for async jobs: bill runs, read imports, reconcile, sends.
Every job that touches tenant tables MUST set app.tenant_id first (B3)."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
app = Celery("smartbillhub")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# DEF-TEN-9190 — a worker says where it will store export files, and refuses to
# start when it has nowhere (`core/storage_guard.enforce_export_storage_at_startup`).
# `worker_init` fires once, in the worker's main process, before any task is
# taken — so a misconfigured worker never accepts an export it cannot store.
# celery-beat sends no `worker_init` and is untouched. SystemExit is not an
# Exception, so celery's signal dispatcher does not swallow it.
from celery.signals import worker_init  # noqa: E402


@worker_init.connect
def _export_storage_at_start(**_kwargs: object) -> None:
    from core import storage_guard

    storage_guard.enforce_export_storage_at_startup(process="celery worker")

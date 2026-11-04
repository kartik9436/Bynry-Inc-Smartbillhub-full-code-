# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-1080 — the PO hit HTTP 500 on the asset import and no one could
#           say why, because the traceback was never written anywhere at all.
# Rules:    hard-won law 1 (a comment claiming a guarantee is not the guarantee)
#           · hard-won law 3 (defaults fail closed) · hard-won law 7 (prove a
#           guard RED before trusting it green)
# Impacts:  06-backend/config/settings/base.py (the LOGGING dict this pins)
# ───────────────────────────────────────────────────────
"""An unhandled 500 MUST leave a traceback in the container log.

WHY THIS TEST EXISTS AND WHAT IT WOULD HAVE CAUGHT
--------------------------------------------------
Before 2026-08-27 this project defined no ``LOGGING`` at all, so Django's
``DEFAULT_LOGGING`` applied — and under ``DEBUG=False`` it discards every
unhandled exception by three mechanisms at once:

  1. its ``console`` handler is filtered by ``require_debug_true``, so it is
     declined in exactly the environment where it matters;
  2. its ``mail_admins`` handler passes that filter but mails ``ADMINS``, which
     this project never sets — so it mails nobody;
  3. ``logging.lastResort`` never fires, because it applies only when a record
     finds NO handler; here one was found and then declined, which counts.

``test_django_default_would_have_swallowed_it`` below is the RED half, kept
permanently rather than deleted after the fix: it asserts the defaulted
behaviour really does drop the record, so the reason this file exists cannot be
forgotten or argued away later.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.utils.log import DEFAULT_LOGGING


def _handler_filters(handler_conf: dict) -> list:
    return list(handler_conf.get("filters") or [])


def test_django_default_would_have_swallowed_it() -> None:
    """RED half — the behaviour we replaced, pinned so it stays legible.

    If a future Django release stops filtering its console handler, this fails
    and the LOGGING dict can be reconsidered. That is the honest trigger for
    revisiting it — not somebody's memory.
    """
    console = DEFAULT_LOGGING["handlers"]["console"]
    assert "require_debug_true" in _handler_filters(console), (
        "Django's DEFAULT_LOGGING console handler is no longer debug-filtered. "
        "DEF-1080's root cause has changed; re-derive the LOGGING dict."
    )
    assert DEFAULT_LOGGING["handlers"]["mail_admins"]["class"].endswith("AdminEmailHandler")
    # ...and nothing in this project sets ADMINS, which is the second mechanism.
    assert not getattr(settings, "ADMINS", []), (
        "ADMINS is now set. The mail_admins path may deliver, which changes "
        "DEF-1080's analysis — but does not remove the need for a log line."
    )


def test_request_errors_reach_a_handler_with_no_debug_filter() -> None:
    """GREEN half — `django.request` is wired to an unfiltered stream handler."""
    conf = settings.LOGGING
    assert conf["disable_existing_loggers"] is False

    request_logger = conf["loggers"]["django.request"]
    assert request_logger["level"] == "ERROR"
    assert request_logger["propagate"] is False
    assert request_logger["handlers"], "django.request has no handler — DEF-1080 again"

    for name in request_logger["handlers"]:
        handler = conf["handlers"][name]
        assert handler["class"] == "logging.StreamHandler", (
            f"handler {name!r} is not a stream handler; stderr IS the container "
            "log because docker-entrypoint.sh runs gunicorn with --error-logfile -"
        )
        assert not _handler_filters(handler), (
            f"handler {name!r} carries filters {_handler_filters(handler)!r}. "
            "A filtered handler is precisely the DEF-1080 bug — the default one "
            "was declined by require_debug_true and nothing was ever printed."
        )


def test_a_traceback_actually_comes_out(caplog) -> None:
    """The functional half: an exc_info record on `django.request` is emitted.

    Asserting the dict is not the same as asserting behaviour — hard-won law 1.
    """
    logger = logging.getLogger("django.request")
    with caplog.at_level(logging.ERROR, logger="django.request"):
        try:
            raise RuntimeError("DEF-1080 probe")
        except RuntimeError:
            logger.error("Internal Server Error: /probe", exc_info=True)

    assert caplog.records, "no record captured — django.request is muted"
    record = caplog.records[-1]
    assert record.exc_info is not None, "the record carries no traceback"
    assert "DEF-1080 probe" in logging.Formatter().format(record)

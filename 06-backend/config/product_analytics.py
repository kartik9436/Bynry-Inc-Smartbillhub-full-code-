"""Server-side product analytics — PostHog, after commit, never in a money path.

Change:  CR-169-BRC10 §2 row 9 (PO 2026-10-04, decision log *"POSTHOG
         USER-ACTIVITY TRACKING"*). Business events are sent from the SERVER,
         after the transaction that made them true has committed.

WHY HERE AND NOT IN A MODULE. It writes nothing to the database and owns no
table, so it is infrastructure like `config.celery`, not a business module —
and billing, payments and work all call it, which a module-to-module import
would forbid.

THE FOUR RULES IT KEEPS, EACH OF THEM A TEST
(`06-backend/tests/test_cr169_product_analytics.py`):

1. **Off unless configured, never a fallback (hard-won law 3).** No
   `POSTHOG_KEY` → nothing is sent and no client is built. A key with no
   `POSTHOG_ENVIRONMENT` is also OFF: an event with no environment cannot be
   told apart in the Production chart that must stay at 0 (CR §2 row 10).
2. **One environment's data never reaches another's project (CR §0 item 1).**
   A non-production server whose key's fingerprint equals
   `POSTHOG_PROD_KEY_FINGERPRINT` refuses to send, and logs why, once; a
   production server whose key does NOT match it refuses too; and a key with no
   fingerprint at all is OFF, the same as the web build (`DEF-TEN-9651` — this
   failed open until 2.509.4).
3. **After commit, never inside it.** `capture_after_commit` registers a
   `transaction.on_commit` callback: a rolled-back payment sends nothing, and
   the network call is never made while a money transaction holds its locks.
   The client itself queues and sends on its own thread (`sync_mode=False`).
4. **An allow-list per event, no PII.** `EVENTS` names every key an event may
   carry; anything else is DROPPED and logged, never sent. No amounts, names,
   account numbers or free text — counts, codes and yes/no only.

A failure anywhere in here is swallowed: analytics must never fail the
request that produced the event (CR §4).
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Callable, Mapping
from typing import Any

from django.conf import settings
from django.db import transaction

# `smartbillhub.*` and not `__name__`: the web process has a handler only for
# the named loggers (`base.py` LOGGING, `DEF-TEN-9190`), so `config.*` would log
# into nothing.
logger = logging.getLogger("smartbillhub.analytics")

#: The three deployed environments, by the same words the front end uses
#: (`VITE_APP_ENV`). Anything else counts as "not production" for rule 2.
PRODUCTION = "production"

#: PostHog's US cloud — the PO's answer 2 (*"(a) PostHog US cloud."*).
DEFAULT_HOST = "https://us.i.posthog.com"

#: event name -> the ONLY property keys it may carry (rule 4). `tenant`,
#: `environment`, `app` and `app_version` are added by this module itself.
EVENTS: Mapping[str, frozenset[str]] = {
    "bill_run_finalised": frozenset({"queue_rows_resolved"}),
    "payment_recorded": frozenset({"method", "purpose", "payment_type", "cleared"}),
    "work_order_completed": frozenset({"source"}),
}

#: Properties this module adds to every event.
COMMON = frozenset({"tenant", "environment", "app", "app_version"})

_client: Any = None
_client_built = False


def fingerprint(key: str) -> str:
    """First 16 hex characters of SHA-256 — the same spelling the front-end
    build uses (`scripts/deployConfig.mjs`'s `keyFingerprint`)."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _config() -> tuple[str, str, str] | None:
    """(key, host, environment), or None when analytics is OFF (rules 1, 2)."""
    key = (getattr(settings, "POSTHOG_KEY", "") or "").strip()
    environment = (getattr(settings, "POSTHOG_ENVIRONMENT", "") or "").strip()
    host = (getattr(settings, "POSTHOG_HOST", "") or "").strip() or DEFAULT_HOST
    if not key:
        return None
    if not environment:
        logger.error("POSTHOG_KEY is set but POSTHOG_ENVIRONMENT is not; analytics is OFF")
        return None
    prod_fp = (getattr(settings, "POSTHOG_PROD_KEY_FINGERPRINT", "") or "").strip()
    # DEF-TEN-9651: fail CLOSED, as the web build does. Without the fingerprint
    # nothing can tell a production key from another, so nothing is sent.
    if not prod_fp:
        logger.error("POSTHOG_KEY is set but POSTHOG_PROD_KEY_FINGERPRINT is not; analytics is OFF")
        return None
    is_prod_key = fingerprint(key) == prod_fp
    if environment != PRODUCTION and is_prod_key:
        logger.error(
            "POSTHOG_KEY on a %s server is the PRODUCTION key; analytics is OFF", environment
        )
        return None
    if environment == PRODUCTION and not is_prod_key:
        logger.error("POSTHOG_KEY on the production server is not the PRODUCTION key; analytics is OFF")
        return None
    return key, host, environment


def _default_factory(key: str, host: str) -> Any:
    from posthog import Posthog

    return Posthog(key, host=host, sync_mode=False, disable_geoip=True)


#: Replaced by tests; never by production code.
client_factory: Callable[[str, str], Any] = _default_factory


def _get_client() -> Any:
    global _client, _client_built
    if not _client_built:
        _client_built = True
        config = _config()
        if config is not None:
            try:
                _client = client_factory(config[0], config[1])
            except Exception:  # noqa: BLE001 — analytics never breaks a request
                logger.exception("PostHog client could not be built; analytics is OFF")
                _client = None
    return _client


def reset_for_tests() -> None:
    """Forget the built client so a test's settings are read again."""
    global _client, _client_built
    _client = None
    _client_built = False


def clean_properties(event: str, properties: Mapping[str, Any]) -> dict[str, Any]:
    """Rule 4: keep only the allow-listed keys, and only plain scalar values."""
    allowed = EVENTS.get(event)
    if allowed is None:
        raise ValueError(f"unknown analytics event {event!r} — add it to EVENTS")
    kept: dict[str, Any] = {}
    for name, value in properties.items():
        if name not in allowed:
            logger.warning("analytics: dropped property %r on %s (not allow-listed)", name, event)
            continue
        if value is None or isinstance(value, (bool, int, str)):
            kept[name] = value
        else:
            logger.warning("analytics: dropped property %r on %s (not a scalar)", name, event)
    return kept


def _tenant_slug(tenant_id: Any) -> str | None:
    from apps.tenancy import models as tenancy_models

    return (
        tenancy_models.Tenant.objects.filter(pk=tenant_id)
        .values_list("subdomain", flat=True)
        .first()
    )


def _version() -> str:
    """`pyproject.toml`'s version — the backend's copy of the one release
    number (CR-004 §7). Read, never restated here."""
    try:
        import tomllib

        with open(settings.BASE_DIR / "pyproject.toml", "rb") as handle:
            return str(tomllib.load(handle)["project"]["version"])
    except Exception:  # noqa: BLE001
        return ""


def send_now(
    event: str,
    *,
    tenant_id: Any,
    actor_id: Any = None,
    properties: Mapping[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> bool:
    """Send one event now. Returns whether it was handed to the client."""
    try:
        cleaned = clean_properties(event, properties or {})
        client = _get_client()
        if client is None:
            return False
        config = _config()
        if config is None:
            return False
        slug = _tenant_slug(tenant_id) if tenant_id is not None else None
        props: dict[str, Any] = {
            **cleaned,
            "tenant": slug,
            "environment": config[2],
            "app": "server",
            "app_version": _version(),
        }
        kwargs: dict[str, Any] = {
            # The STAFF user's internal id — the same `distinct_id` the browser
            # identifies with (`/me`'s `id`), so a server event lands on the
            # person who caused it. A system job has no person: `server`.
            "distinct_id": str(actor_id) if actor_id is not None else "server",
            "properties": props,
        }
        if slug:
            kwargs["groups"] = {"tenant": slug}
        if dedupe_key:
            # A resumed bill run calls its close twice; one uuid per fact
            # lets PostHog keep one event.
            kwargs["uuid"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"sbh:{event}:{dedupe_key}"))
        client.capture(event, **kwargs)
        return True
    except Exception:  # noqa: BLE001 — analytics never breaks a request (CR §4)
        logger.exception("analytics: %s was not sent", event)
        return False


def capture_after_commit(
    event: str,
    *,
    tenant_id: Any,
    actor_id: Any = None,
    properties: Mapping[str, Any] | None = None,
    dedupe_key: str | None = None,
) -> None:
    """Rule 3 — register the send to run after the surrounding transaction
    commits. Outside any transaction Django runs it immediately, which is
    after the autocommit already happened. The allow-list is checked NOW, so a
    bad call fails in the test that makes it rather than silently later."""
    clean_properties(event, properties or {})
    frozen = dict(properties or {})
    transaction.on_commit(
        lambda: send_now(
            event,
            tenant_id=tenant_id,
            actor_id=actor_id,
            properties=frozen,
            dedupe_key=dedupe_key,
        )
    )


def actor_id_of(actor: Any) -> Any:
    """A staff actor's user id, or None for a system actor."""
    return getattr(actor, "pk", None) if actor is not None else None

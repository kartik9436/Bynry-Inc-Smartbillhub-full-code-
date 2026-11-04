# ── Trace ──────────────────────────────────────────────
# Story:    CR-187-BRC10 (the native field app) · closes the build of OQ-FLD-12797
#           Screens: S8 (Settings → Security, "Field app certificates" card)
# Rules:    OQ-FLD-12797 CLOSED 2026-10-24 (decision log "FOUR PO ANSWERS ON THE
#           FIELD APP'S OPEN QUESTIONS" item 3) · 18-field-app/12-security.md §4
#           (Transport: two pins and a documented rotation) and §7.2 ·
#           CLAUDE.md hard rules 1 (tenant scoping — the row is RLS FORCE'd) and
#           7 (every change audited before/after)
# Tests:    06-backend/tests/test_oq_fld_12797_field_app_pins.py
# Impacts:  apps/identity/api.py (GET/PUT settings/security-policy/field-app-pins)
#           · apps/work/seams/identity_seam.py → GET work/mobile/settings (the phone)
# ───────────────────────────────────────────────────────
"""The field app's certificate pins — held in Settings › Security, not in code.

PO, 2026-10-24, verbatim: *"Trust the certificate issuer's key plus one backup
issuer, replaced through an app update at least 60 days before either expires.
plese dont hardcode it use settings - security values set in staff portal"*.

A PIN is the base64 SHA-256 of a certificate authority's SubjectPublicKeyInfo,
with a label a person can read (*ISRG Root X1*), the date that authority's
certificate stops being valid, and whether it is active.

⚠ **PER UTILITY, WITH A PLATFORM DEFAULT UNDERNEATH — AND WHY (the lane's
judgment, recorded here because it is the reason this file is shaped as it is).**
Every utility is reached through ONE server certificate, so the physically true
fact is platform-wide. But the PO put the list on the STAFF PORTAL's Settings ›
Security, and that tab is one utility's: its admin is one utility's admin. A
platform-wide list edited from it would let any utility's admin re-pin every
other utility's phones — a typo at one utility would strand the whole fleet of
forty. So:

  * **Each utility owns its own list** (`security_policies.field_app_pins`,
    RLS FORCE since `identity/0004`). A list is served only to that utility's
    phones, through a tenant-scoped read, so one utility cannot break another's
    phones by construction.
  * **A utility that has never edited it is served the PLATFORM DEFAULT**
    (`settings.FIELD_APP_DEFAULT_PINS`, from the environment) — the same pair
    the build carries. NULL in the column means exactly that, so the operator
    can rotate the default for every utility that has not taken the list over,
    and a utility that never opens the card behaves as its build does.
  * **A utility cannot strand its OWN phones either**, which is the rule below
    the two the brief named: a save must keep at least one key that is
    CURRENTLY active and unexpired. A phone only accepts a new list over a
    connection pinned by its old one; a list sharing no key with the old one is
    a list the fleet can never fetch the correction for. Rotation is therefore
    always *add the new key, let phones sync, then deactivate the old one* —
    which is exactly the worked example in the ruling.

Validation, all of it here and nowhere else:
  * the hash is base64 of exactly 32 bytes;
  * a label is given; `not_after` is a real date; no key is listed twice;
  * at least `MIN_VALID_PINS` (2) are active with a date not yet passed;
  * the continuity rule above.

`PIN_WARNING_DAYS` (60) is the ruling's own figure — *"at least 60 days before
either expires"* — and is SERVED to the card rather than typed into it.

HUMAN-REVIEW-PENDING — 🔒 transport security, AI-authored 2026-10-24 under the
PO ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*).
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from apps.identity.models import SecurityPolicy
from core import audit as core_audit
from core import errors
from core.permissions import SYSTEM_ADMIN, require_role

#: The ruling's figure: the office replaces a key at least 60 days before it expires.
PIN_WARNING_DAYS = 60
#: The design's *"two pins"* (12-security.md §4) and the ruling's *"issuer plus one backup"*.
MIN_VALID_PINS = 2
#: A label is a name a clerk reads, not a document.
LABEL_MAX = 80

AUDIT_ACTION = "settings.field_app_pins_updated"


def today_utc() -> dt.date:
    """A certificate's `notAfter` is a UTC instant, so its date is read in UTC."""
    return timezone.now().astimezone(dt.timezone.utc).date()


def _hash_ok(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 44:
        return False
    try:
        return len(base64.b64decode(value, validate=True)) == 32
    except (binascii.Error, ValueError):
        return False


def _date(value: Any) -> dt.date | None:
    if isinstance(value, dt.date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def _usable(pins: list[dict[str, Any]], today: dt.date) -> set[str]:
    """The hashes that are active and whose date has not passed."""
    return {
        p["spki_sha256"]
        for p in pins
        if p.get("active") and (_date(p.get("not_after")) or dt.date.min) >= today
    }


def default_pins() -> list[dict[str, Any]]:
    """The platform's default set, active. A malformed default is a deploy
    fault and refuses loudly (hard-won law 3) rather than serving a phone a
    pin that can never match."""
    out = []
    for raw in getattr(settings, "FIELD_APP_DEFAULT_PINS", None) or []:
        if not _hash_ok(raw.get("spki_sha256")) or _date(raw.get("not_after")) is None:
            raise ImproperlyConfigured("SBH_FIELD_APP_DEFAULT_PINS holds an invalid pin")
        out.append(
            {
                "spki_sha256": raw["spki_sha256"],
                "label": str(raw.get("label") or "").strip(),
                "not_after": _date(raw["not_after"]).isoformat(),
                "active": True,
            }
        )
    return out


def current_pins(tenant_id: Any) -> tuple[list[dict[str, Any]], str]:
    """`(pins, source)` — the utility's own list, or the platform default."""
    policy = SecurityPolicy.objects.filter(tenant_id=tenant_id).first()
    if policy is None or policy.field_app_pins is None:
        return default_pins(), "default"
    return [dict(p) for p in policy.field_app_pins], "utility"


def status_of(pin: dict[str, Any], today: dt.date) -> tuple[str, int]:
    """`(status, days_left)` — `inactive`, `expired`, `expiring` (≤60 days) or `valid`."""
    days_left = ((_date(pin.get("not_after")) or today) - today).days
    if not pin.get("active"):
        return "inactive", days_left
    if days_left < 0:
        return "expired", days_left
    if days_left <= PIN_WARNING_DAYS:
        return "expiring", days_left
    return "valid", days_left


def pins_payload(tenant_id: Any, today: dt.date | None = None) -> dict[str, Any]:
    """The Security tab card's read: every pin with its derived status."""
    today = today or today_utc()
    pins, source = current_pins(tenant_id)
    rows = []
    for pin in pins:
        status, days_left = status_of(pin, today)
        rows.append({**pin, "status": status, "days_left": days_left})
    return {
        "pins": rows,
        "source": source,
        "warning_days": PIN_WARNING_DAYS,
        "min_valid": MIN_VALID_PINS,
    }


def phone_pins(tenant_id: Any, today: dt.date | None = None) -> list[dict[str, Any]]:
    """What a phone is given: the ACTIVE, UNEXPIRED pins only, no status words.
    The phone re-checks the dates itself (its clock moves after this answer)."""
    today = today or today_utc()
    pins, _source = current_pins(tenant_id)
    usable = _usable(pins, today)
    return [
        {"spki_sha256": p["spki_sha256"], "label": p["label"], "not_after": p["not_after"]}
        for p in pins
        if p["spki_sha256"] in usable
    ]


def _refuse(field_errors: list[dict[str, Any]]) -> None:
    raise errors.ValidationError(
        field_errors[0]["code"],
        message_key="errors.identity.pins_invalid",
        br_ref="OQ-FLD-12797",
        field_errors=field_errors,
    )


def validate_pins(
    incoming: Any, current: list[dict[str, Any]], today: dt.date
) -> list[dict[str, Any]]:
    """The whole list as it should be stored, or a refusal naming each fault."""
    if not isinstance(incoming, list):
        _refuse(
            [
                {
                    "field": "pins",
                    "code": errors.VAL_FORMAT,
                    "message_key": "errors.identity.pins_too_few",
                    "params": {"min": MIN_VALID_PINS},
                }
            ]
        )
    field_errors: list[dict[str, Any]] = []
    clean: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, raw in enumerate(incoming):
        raw = raw if isinstance(raw, dict) else {}
        spki = raw.get("spki_sha256")
        spki = spki.strip() if isinstance(spki, str) else spki
        label = raw.get("label")
        label = label.strip() if isinstance(label, str) else ""
        not_after = _date(raw.get("not_after"))
        active = raw.get("active", True)
        if not _hash_ok(spki):
            field_errors.append(
                {
                    "field": f"pins[{i}].spki_sha256",
                    "code": errors.VAL_FORMAT,
                    "message_key": "errors.identity.pin_hash_invalid",
                }
            )
        elif spki in seen:
            field_errors.append(
                {
                    "field": f"pins[{i}].spki_sha256",
                    "code": errors.VAL_FORMAT,
                    "message_key": "errors.identity.pin_duplicate",
                }
            )
        if not label or len(label) > LABEL_MAX:
            field_errors.append(
                {
                    "field": f"pins[{i}].label",
                    "code": errors.VAL_REQUIRED,
                    "message_key": "errors.identity.pin_label_required",
                    "params": {"max": LABEL_MAX},
                }
            )
        if not_after is None:
            field_errors.append(
                {
                    "field": f"pins[{i}].not_after",
                    "code": errors.VAL_FORMAT,
                    "message_key": "errors.identity.pin_date_invalid",
                }
            )
        if not isinstance(active, bool):
            field_errors.append(
                {
                    "field": f"pins[{i}].active",
                    "code": errors.VAL_FORMAT,
                    "message_key": "errors.identity.option_not_allowed",
                    "params": {"allowed": [True, False]},
                }
            )
        if isinstance(spki, str):
            seen.add(spki)
        clean.append(
            {
                "spki_sha256": spki,
                "label": label,
                "not_after": not_after.isoformat() if not_after else None,
                "active": active,
            }
        )
    if field_errors:
        _refuse(field_errors)
    usable = _usable(clean, today)
    if len(usable) < MIN_VALID_PINS:
        _refuse(
            [
                {
                    "field": "pins",
                    "code": errors.VAL_RANGE,
                    "message_key": "errors.identity.pins_too_few",
                    "params": {"min": MIN_VALID_PINS},
                }
            ]
        )
    # Continuity: a fleet pinned on today's keys must still reach the server.
    # Exempt only when nothing is usable today — such a fleet is already
    # stranded and a fresh list is the only way out for a new build.
    usable_now = _usable(current, today)
    if usable_now and not (usable_now & usable):
        _refuse(
            [
                {
                    "field": "pins",
                    "code": errors.VAL_RANGE,
                    "message_key": "errors.identity.pins_keep_one_current",
                }
            ]
        )
    return clean


@require_role(SYSTEM_ADMIN)
@transaction.atomic
def save_pins(
    *, actor: Any, tenant_id: Any, pins: Any, today: dt.date | None = None
) -> dict[str, Any]:
    """Replace this utility's pin list. Validated in full, audited before/after
    (hard rule 7). A refused save writes nothing — not even the policy row."""
    today = today or today_utc()
    policy = SecurityPolicy.objects.select_for_update().filter(tenant_id=tenant_id).first()
    stored = policy.field_app_pins if policy is not None else None
    current = [dict(p) for p in stored] if stored is not None else default_pins()
    clean = validate_pins(pins, current, today)
    if policy is None:
        policy, _created = SecurityPolicy.objects.get_or_create(tenant_id=tenant_id)
    policy.field_app_pins = clean
    policy.save(update_fields=["field_app_pins", "updated_at"])
    core_audit.money_action(
        actor,
        AUDIT_ACTION,
        "security_policy",
        policy.id,
        # `None` before = the platform default was in force, said as such.
        before={"field_app_pins": stored},
        after={"field_app_pins": clean},
    )
    return pins_payload(tenant_id, today)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-187-BRC10 · OQ-FLD-12797 (decision log 2026-10-24 item 3)
# generated: 2026-10-24 by lane PINS
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions: HUMAN-REVIEW-PENDING (🔒 transport security) — ledger row needed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

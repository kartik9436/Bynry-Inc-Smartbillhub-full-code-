# ── Trace ──────────────────────────────────────────────
# Change:   DEF-WRK-10352 (CR-187-BRC10) — a native sign-out releases the
#           handset's push token
# Rules:    BR-WRK-002 (a module acts on another through that module's own
#           service, never its tables) · BR-WRK-059/060 · CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_def_wrk_10352_sign_out_push.py ·
#           06-backend/tests/test_def_wrk_10352_sign_out_push_pg.py
# Impacts:  apps/identity/native.py (`sign_out_native`, the only caller)
# ───────────────────────────────────────────────────────
"""identity → work: ONE service call, made when a technician signs out.

`apps.work.mobile.release_push_on_sign_out` clears the push token on this
login's registration of this handset, in this utility. It is WORK's write of
WORK's table (`technician_devices`); identity only asks for it. This is the
mirror of `apps/work/seams/identity_seam.revoke_device_tokens`, by which work
asks identity to revoke a handset's tokens on the office's remote sign-out.

⚠ **NO `apps.work.models` IMPORT HERE OR ANYWHERE IN IDENTITY.**
"""

from __future__ import annotations

from typing import Any


def release_push_on_sign_out(*, tenant_id: Any, user_id: Any, device_uid: str) -> int:
    """Work's `mobile.release_push_on_sign_out` — rows cleared (0 when none)."""
    from apps.work import mobile

    return mobile.release_push_on_sign_out(
        tenant_id=tenant_id, user_id=user_id, device_uid=device_uid
    )


__all__ = ["release_push_on_sign_out"]

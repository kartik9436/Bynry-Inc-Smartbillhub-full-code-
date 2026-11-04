# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 TC-6 (fix a blocked account inline, it is re-checked and
#           moves to Ready) · changes row 36 / 46 (*"a blocking tag with a fact
#           the clerk can supply here … is fixed INLINE on the row and
#           re-checked"*)
# Defect:   DEF-BIL-8218 — the Fix column could only open the owning screen
# Plan:     15-bulk-bill-run-build-plan.md B14 · F10
# Rules:    B1 / CLAUDE.md module map — billing writes no other module's tables;
#           every fact is WRITTEN BY ITS OWNING MODULE'S SERVICE · rule 7
#           (the owning service audits its write; this file audits the Check
#           act that asked for it)
# Tests:    06-backend/tests/test_bbr_inline_fixes.py
# ───────────────────────────────────────────────────────
"""The Check's INLINE FIXES: a fact the clerk supplies on the row, written by
the module that owns it, then that one account re-checked.

WHAT IS FIXED HERE, AND BY WHOM — the table IS the design:

  ===========================  =====================  ============================  =========
  tag (finding code)           the fact               written by                    re-check
  ===========================  =====================  ============================  =========
  unit_has_no_plan             the unit's plan        metering.services             services
                                                      .assign_unit_plan
  connection_size_unresolved…  the connection size    assets.services.update_asset  services
                                                      (`size_class`, every meter
                                                      now on that connection)
  premises_jurisdiction_…      inside / outside the   metering.services             services
                               city limits            .update_premises
  ===========================  =====================  ============================  =========

The size row also answers `ruled_path_refused` when its params say the missing
fact is the connection size — with R3 switched on that is how a missing size
actually arrives (`fix_for`).

Billing IMPORTS NONE OF THOSE MODULES: each service is resolved BY NAME
(`gather._resolve`, the seam pattern every billing read uses and
`metering_seam.record_billed_estimates` uses for a write), is called with the
clerk as its actor — so the owning module's own role check, validation,
plan-lock (BR-MET-007) and audit row all apply exactly as on its own screen —
and billing writes no row of theirs. A refusal from the owner reaches the clerk
as the owner's own message.

WHAT IS NOT FIXED HERE, deliberately: a reading (Meter Reads corrects a
committed read through its correction flow, BR-MET-053 — a one-field edit on a
Check row is not that flow), a count of unmetered assets (no single field
holds it), and a unit for an account (a move-in, not a field). Those rows keep
the *Open <screen> ↗* link and **Re-check** — changes row 36's *"anything else
links to its screen"*.

EVERY FIX IS FOLLOWED BY A RE-CHECK OF THAT ACCOUNT ONLY, of the category the
fact feeds and what is downstream of it (`check_engine.downstream`,
DEF-BIL-8286) — the answer the clerk sees is the saved result after the fix,
never an optimistic *fixed*.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.billing import check_engine, check_models, check_store, gather
from apps.billing.exceptions import BillingRuleError
from core import audit
from core import tenancy as core_tenancy

FIX_SET_PLAN = "set_plan"
FIX_SET_SIZE = "set_size"
FIX_SET_CITY_LIMITS = "set_city_limits"


@dataclass(frozen=True)
class InlineFix:
    """One fix the Check can make on a row."""

    name: str
    #: The finding code(s) this fix answers — refused for any other row.
    codes: tuple[str, ...]
    #: `(module, kind, function)` — the OWNING module's write, resolved by name.
    owner: tuple[str, str, str]
    #: The Check categories the fact feeds (their downstream re-runs too).
    recheck: tuple[str, ...]
    #: The payload keys the clerk must supply.
    needs: tuple[str, ...]


FIXES: dict[str, InlineFix] = {
    FIX_SET_PLAN: InlineFix(
        FIX_SET_PLAN,
        codes=("unit_has_no_plan",),
        owner=("metering", "services", "assign_unit_plan"),
        recheck=(check_engine.CATEGORY_SERVICES,),
        needs=("plan_id",),
    ),
    FIX_SET_SIZE: InlineFix(
        FIX_SET_SIZE,
        codes=("connection_size_unresolved_for_sized_schedule",),
        owner=("assets", "services", "update_asset"),
        recheck=(check_engine.CATEGORY_SERVICES,),
        needs=("service_code", "size_class"),
    ),
    FIX_SET_CITY_LIMITS: InlineFix(
        FIX_SET_CITY_LIMITS,
        codes=("premises_jurisdiction_unstated",),
        owner=("metering", "services", "update_premises"),
        recheck=(check_engine.CATEGORY_SERVICES,),
        needs=("inside_city_limits",),
    ),
}

#: finding code → the fix that answers it, published on the findings read so
#: the screen offers the fix control only where one exists.
FIX_BY_CODE: dict[str, str] = {code: fix.name for fix in FIXES.values() for code in fix.codes}

#: The ruled pricing path (R3 switched on) refuses a missing connection size
#: under its GENERIC code, `ruled_path_refused`, naming the missing fact in
#: stable params (`resolution_switch.apply` → `{"blocked":
#: "connection_size_unresolved", "service_code": …}`). Only THAT cause is the
#: size fix; every other ruled-path refusal keeps its link.
RULED_PATH_REFUSED = "ruled_path_refused"
RULED_SIZE_MISSING = "connection_size_unresolved"


def fix_for(code: str, params: dict[str, Any] | None = None) -> str | None:
    """The inline fix for ONE finding (its code and, where the code is
    generic, its params), or None."""
    if code in FIX_BY_CODE:
        return FIX_BY_CODE[code]
    if code == RULED_PATH_REFUSED and (params or {}).get("blocked") == RULED_SIZE_MISSING:
        return FIX_SET_SIZE
    return None


class FixRefused(BillingRuleError):
    """The fix cannot be made from this row (named, with a catalogue key)."""


def _owner(fix: InlineFix) -> Any:
    module, kind, function = fix.owner
    write = gather._resolve(module, function, kind)
    if write is None:
        raise FixRefused(
            f"{module} has not published {function}, so this fix cannot be written "
            "from the Check. Open the owning screen instead.",
            message_key="billing.check.fix.ownerUnavailable",
        )
    return write


def _saved(run: Any, account_id: str) -> Any:
    row = check_models.BillRunAccountCheck.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(), bill_run=run, account_id=account_id
    ).first()
    if row is None:
        raise FixRefused(
            f"account {account_id} has not been checked on this run.",
            message_key="billing.check.fix.notChecked",
        )
    return row


def _unit_of(row: Any) -> str:
    unit_id = row.unit_id or ((row.covered_unit_ids or [None])[0])
    if not unit_id:
        raise FixRefused(
            f"account {row.account_no} names no unit, so there is nothing to fix on it here.",
            message_key="billing.check.fix.noUnit",
        )
    return str(unit_id)


def _write(fix: InlineFix, actor: Any, row: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Hand the fact to its owner. Answers what was written, for the audit."""
    write = _owner(fix)
    unit_id = _unit_of(row)
    if fix.name == FIX_SET_PLAN:
        write(
            actor,
            unit_id,
            {
                "plan_id": str(payload["plan_id"]),
                "source": "bill_run_check",
                "reason": payload.get("reason") or "Set on a bill run's Check",
            },
        )
        return {"unit_id": unit_id, "plan_id": str(payload["plan_id"])}
    if fix.name == FIX_SET_SIZE:
        assets_of = gather._resolve("metering", "connection_asset_ids_for")
        asset_ids = assets_of(unit_id, str(payload["service_code"])) if assets_of else []
        if not asset_ids:
            raise FixRefused(
                f"account {row.account_no} has no {payload['service_code']} connection on "
                "its unit, so there is no meter to record a size on.",
                message_key="billing.check.fix.noConnection",
                br_ref="BR-AST-500",
            )
        for asset_id in asset_ids:
            write(actor, asset_id, {"size_class": str(payload["size_class"])})
        return {
            "unit_id": unit_id,
            "service_code": str(payload["service_code"]),
            "size_class": str(payload["size_class"]),
            "asset_ids": asset_ids,
        }
    # FIX_SET_CITY_LIMITS
    unit_row = gather._resolve("metering", "unit_row")
    premises_id = getattr(unit_row(unit_id), "premises_id", None) if unit_row else None
    if not premises_id:
        raise FixRefused(
            f"account {row.account_no}'s unit names no premises.",
            message_key="billing.check.fix.noPremises",
        )
    inside = payload["inside_city_limits"]
    write(actor, premises_id, {"inside_city_limits": inside})
    return {"premises_id": str(premises_id), "inside_city_limits": inside}


def apply_fix(
    run: Any,
    *,
    account_id: str,
    fix: str,
    payload: dict[str, Any],
    actor: Any,
) -> dict[str, Any]:
    """Write one fact through its owning module, audit the Check's act, and
    re-check that account. Answers the account's saved findings after it."""
    check_store.refuse_if_sent(run)
    chosen = FIXES.get(fix)
    if chosen is None:
        raise FixRefused(f"no inline fix named {fix!r}.", message_key="billing.check.fix.unknown")
    row = _saved(run, str(account_id))
    matching = [
        f for f in row.findings.order_by("id") if fix_for(f.code, dict(f.params or {})) == fix
    ]
    if not matching:
        raise FixRefused(
            f"account {row.account_no} has no problem on this run that the {fix} fix answers.",
            message_key="billing.check.fix.notOnThisAccount",
        )
    payload = dict(payload)
    if fix == FIX_SET_SIZE and not payload.get("service_code"):
        # The row names its service; the clerk typed only the size.
        found = matching[0]
        payload["service_code"] = found.service_code or (found.params or {}).get("service_code")
    missing = [key for key in chosen.needs if payload.get(key) in (None, "")]
    if missing:
        raise FixRefused(
            f"the {fix} fix needs {', '.join(missing)}.",
            message_key="billing.check.fix.valueRequired",
        )
    written = _write(chosen, actor, row, payload)
    audit.money_action(
        actor,
        "bill_run.check_fix_applied",
        "bill_run",
        str(run.pk),
        before={"account_id": str(account_id), "codes": sorted({f.code for f in matching})},
        after={"account_id": str(account_id), "fix": fix, **written},
    )
    check_store.check_run(run, only_accounts=[str(account_id)], categories=list(chosen.recheck))
    found = check_store.account_findings(run, str(account_id)) or {}
    return {"fix": fix, "written": written, "account": found}


__all__ = ["FIXES", "FIX_BY_CODE", "FixRefused", "InlineFix", "apply_fix", "fix_for"]

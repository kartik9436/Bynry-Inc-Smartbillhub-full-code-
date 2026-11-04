# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-037 (EP-WRK-07) — rules that raise work orders on their own.
#           Screens: Work-026 (the rule list). Fixture: 10-execution-plan.md
#           wave M task M5 — *"the drawing's seven rules, six On"*.
# Rules:    BR-WRK-033 (a rule raises orders without a person; a rule that is
#           OFF raises nothing) · BR-WRK-002 (Work writes no other module's
#           tables) · BR-TEN-056/057 (the sample set, and the tag on the owning
#           row) · BR-TEN-060 (an unwired or impossible block is a NAMED line,
#           never a silent skip) · BR-TEN-063 (atomic per module, idempotent,
#           audited) · CLAUDE.md hard rule 1 (tenant scoping)
# Tests:    06-backend/tests/test_cr070_m_sample_data.py
# Impacts:  apps/tenancy/sample_data.py (the SAMPLE_MODULES row) ·
#           apps/work/services.py (the seam) ·
#           10-scripts/render-checks/cr070-m-rules-and-doors.mjs (M7)
# ───────────────────────────────────────────────────────
"""`work`'s block of the sample set — the seven rules on `Work-026`.

WHY THIS FILE EXISTS AT ALL (`DEF-WRK-4085`)
────────────────────────────────────────────────────────────────────────────
Wave M shipped the rules engine, proved it on 18 SQLite cases and 7 on real
PostgreSQL, and then could not run its own demo script: `work` was not a
sample-data module, so a freshly seeded tenant held **zero rules** and
`cr070-m-rules-and-doors.mjs` would have failed at step 1 on an empty table.
The engine was proved; the SCREEN was not, and nothing in this repository reads
rendered output (hard-won law 6).

⚠ **THIS RUNS FOR EVERY TENANT, ON EVERY SAMPLE-DATA LOAD.** Three properties
follow from that and each is load-bearing rather than good practice:

  * **Tenant-scoped.** Every write here goes through `rules.create_rule`, which
    stamps `core_tenancy.current_tenant_id()`, under RLS `FORCE`. Nothing in
    this file names a tenant.
  * **Idempotent** (`BR-TEN-063`). The identity is the rule's NAME, which is
    also the database's own `uq_work_order_rules_tenant_name` — the check here
    is the fast path and that constraint is the guarantee, the same pairing
    `rules_models.py` documents for the sweep. A replay writes nothing, and
    **a tenant that switched a seeded rule OFF, re-pointed it or re-prioritised
    it keeps its answer**: a replay that re-created a rule the utility had
    silenced would start it raising work again with nobody having asked.
    ⚠ **RENAMING IS THE ONE EDIT A REPLAY DOES NOT RESPECT, AND IT IS SAID HERE
    RATHER THAN IMPLIED.** The name IS the identity, so a utility that renames
    *Leak investigation* to *Leaks* has, as far as this block can tell, no such
    rule — and the next sample-data load seeds a second one under the original
    name. Keying on anything else would need a seed key on the row, which
    `work_order_rules` does not have and which is not worth a migration for a
    fixture; keying on *"this tenant has any sample rule"* would leave a tenant
    that seeded 4 of 7 (because it uses none of the asset types the other three
    name) stuck at four for ever. `test_cr070_m_sample_data.py` asserts this
    behaviour so the next lane meets it as a fact rather than a surprise.
  * **It fails soft and BY NAME** (`BR-TEN-060`). Every rule needs a published
    template, and a tenant selling a service whose templates were never
    published has none. That is reported as a log line naming the rule, not as
    an exception that takes the other six down with it.

⚠ **SIX OF THE SEVEN ARE ENABLED, WHICH MEANS THE NIGHTLY SWEEP REALLY WILL
RAISE JOBS ON A TRIAL TENANT.** That is the drawing's shape (`WS-26`: *7 rules
· 6 on*) and `EP-WRK-01`'s demo-fixture story asks for it in those words, and
it is the feature demonstrating itself — a new operator opens Work the next
morning and finds the jobs a rule made. It is stated here because it is the one
consequence of this file that a reader would otherwise meet in production.

── THE DRAWING ASKS FOR SEVEN RULES AND THE ENGINE HAS FIVE TRIGGERS ────────
`EP-WRK-07` §4 lists the seven rules of `WS-26` with their triggers. **Two of
them name a trigger this product has no reader for**, and that is a real gap
rather than an oversight in this file:

    | the drawing's rule      | the drawing's trigger                  |
    |-------------------------|----------------------------------------|
    | Reconnect after payment | *Payment clears on a disconnected acct*|
    | Backflow test due       | *Certification due within 30 days*     |

`rules.TRIGGER_READERS` holds exactly five — one per source module — and
`_clean_rule` **refuses an unknown trigger at save time**, deliberately: *"a
rule whose trigger_kind has no reader saves happily, sits on Work-026 looking
exactly like a working rule, shows THIS MONTH 0 for ever, and gives nobody a
reason."* So neither of those two rules can be seeded as drawn, and seeding
them on a trigger that DOES exist would put a sentence on a customer's screen
that is not true of the row beneath it.

**What this file does instead, and why each choice is the honest one:**

  * **`Reconnect after payment` is NOT SEEDED.** There is one payments reader
    (*a final notice expired unpaid*) and pointing a rule called *Reconnect
    after payment* at it would raise reconnection visits for people who are
    about to be disconnected — the exact inversion, ENABLED, on every trial
    tenant. It is left out by name and filed (`OQ-WRK-1726`,
    `DEF-WRK-4096`), which is `BR-TEN-060`'s posture applied to a fixture: a
    named absence beats a plausible lie.
  * **`Backflow test due` IS seeded, on `asset_past_certification_life`
    restricted to backflow preventers, and it is the one that is OFF** — as
    drawn. The divergence is the LEAD TIME (the drawing wants *30 days before*;
    the engine answers *already past*), and it costs nothing here because a
    rule that is off raises nothing at all (`BR-WRK-033`).
  * **The drawing's `Meter exchange programme` and the plan's `Asset age rule`
    are BOTH seeded**, because the repository names the asset-age rule twice
    and differently: `EP-WRK-07` §4 draws it as *Meter exchange programme*,
    while `rules.py`'s own module docstring, the execution plan's `M7` line and
    `cr070-m-rules-and-doors.mjs` all say the raised orders read **Raised by:
    Asset age rule**. Rather than pick one and contradict the other, they are
    two rules with **disjoint subjects** — `Asset age rule` takes meters and
    `Meter exchange programme` takes sub-meters — so no meter is ever raised
    twice and both names are on the screen a person is shown. `OQ-WRK-1725`
    asks the PO which name survives.

── WHY THE SUBJECTS ARE NOT IN THIS FILE ───────────────────────────────────
The three meters past their certification life are seeded by
`apps/assets/sample_data.seed_sample_aged_meters`, because **Work may not write
`assets`** (`BR-WRK-002`; `G78` fails a foreign write from Work's first
commit). Work reads them through `seams/assets_seam.assets_past_certification`
and through nothing else.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from apps.work import rules
from apps.work.rules_models import WorkOrderRule
from apps.work.seams import assets_seam, metering_seam
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.work")

#: The template every seeded rule raises. Metering seeds and owns the row
#: (`apps/metering/sample_data.EXCHANGE_TEMPLATE_NAME`); this is a READ of it.
#: Spelled with an em dash, once, because two spellings of an em-dashed name is
#: a bug nobody sees until a demo.
EXCHANGE_TEMPLATE_NAME = "Meter exchange — residential"

#: The seven rows of `Work-026`, in the drawing's order.
#:
#: `asset_type_names` is resolved to ids at seed time through the assets seam —
#: a supervisor picks *Backflow preventer* on the builder and the rule stores
#: the id, so the fixture is written the way a person writes it and translated
#: once, here.
#:
#: ⚠ **`enabled` IS DATA AND NOT A DEFAULT.** `WorkOrderRule.enabled` defaults
#: to True (the builder's last step is *Review & activate*), so the one rule
#: that must ship OFF says so explicitly and a test asserts the count.
SEEDED_RULES: tuple[dict[str, Any], ...] = (
    # ⚠ **ROUND 5 (`CR-168-BRC10` lane SRV-4): EACH RULE NAMES ITS PROCESS, and
    # the process key IS the label its jobs read (`DEF-WRK-4096`).** Wave M
    # wrote a module + trigger name here and four of the five could never
    # raise. `trigger_kind`/`source_module` are no longer written by this file.
    {
        "name": "Disconnect for non-pay",
        "process": "dunning_auto",
        "params": {"grace_days": 2},
        "priority": "HIGH",
        "enabled": True,
    },
    {
        "name": "Read verification",
        "process": "billing_exception",
        "params": {"retryable": False},
        "priority": "NORMAL",
        "enabled": True,
    },
    {
        # The drawing's name for the asset-age rule (`EP-WRK-07` §4).
        # Sub-meters only — see the module docstring on the two names.
        "name": "Meter exchange programme",
        "process": "asset_age_rule",
        "asset_type_names": ["Sub-meter"],
        "priority": "NORMAL",
        "enabled": True,
    },
    {
        # THE ONE THE DEMO DRIVES. `M7` step 2: three orders on `Work-007`
        # read *Raised by: Asset age rule*, and `_raise_one` prints
        # `rule.name` there. Meters only.
        "name": "Asset age rule",
        "process": "asset_age_rule",
        "asset_type_names": ["Meter"],
        "priority": "NORMAL",
        "enabled": True,
    },
    {
        # ⚠ **WATER, IN kgal, AND SHIPPED OFF (`DEF-WRK-4097`; decision log
        # *"CR-168 ROUND 5 · SRV-4"*).** Wave M seeded this with no service and
        # a bare floor of 0, which matched 98 of the demo's 128 meters — 51 of
        # them electric. A service and a unit (hard rule 3) take it to 47 water
        # meters, and 47 of 49 is still *every meter that is used*: the only
        # floor this product holds is the reader's own 0, and choosing another
        # would be a lane inventing a leak threshold. So it ships OFF, and the
        # rule's own page says *Tonight it would raise 47 jobs* before a
        # supervisor switches it on with a floor of their choosing.
        "name": "Leak investigation",
        "process": "high_usage_alert",
        "params": {"service": "water", "unit": "kgal", "consecutive_reads": 3,
                   "minimum_consumption": "0"},
        "priority": "HIGH",
        "enabled": False,
    },
    {
        # A SCREEN moment since round 5 (ruling 10): the move-in screen offers
        # this rule's job ticked, and the overnight sweep never reads it. The
        # NAME is kept because it is the seed's identity (`BR-TEN-063`).
        "name": "Move-in / move-out",
        "process": "move_in",
        "priority": "NORMAL",
        "enabled": True,
    },
    {
        # ⚠ THE ONE THAT IS OFF, as drawn — and since round 5 it is the drawing's
        # own trigger: *certification due soon* (`compliance_calendar`, P3.32).
        # The 30 days are DEMO DATA on a sample row, as drawn (WS-26); the
        # process itself has no default lead time and refuses a rule without one.
        "name": "Backflow test due",
        "process": "compliance_calendar",
        "params": {"days_ahead": 30},
        "asset_type_names": ["Backflow preventer"],
        # `DEF-WRK-9687` — a backflow test, done TO a backflow preventer. It
        # raised the meter-exchange template, which names meters only, so every
        # preventer it found was refused (`asset_type_not_on_template`).
        "template": "backflow",
        "priority": "LOW",
        "enabled": False,
    },
)


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _exchange_template_id() -> str | None:
    """The published `Meter exchange — residential` template, or None.

    A READ through Work's own metering seam — `work_order_templates` is
    metering's table (`03-field-map.md` §4) and metering's seeder is what
    publishes and tags this row.

    ⚠ **PUBLISHED, NOT MERELY PRESENT.** `rules._raise_one` refuses to raise
    from a draft or a deactivated template and logs instead, so a rule pointed
    at an unpublished one is a rule that shows *This month 0* for ever. The
    same two conditions `BR-WRK-012`/`BR-WRK-016` state everywhere else.

    ⚠ **A TEMPLATE NAME IS NOT UNIQUE, AND THIS IS THE ONLY PLACE LEFT THAT
    LOOKS ONE UP BY NAME ALONE (2026-09-07).** `work_order_templates` is unique
    on **(tenant, service, name, version)** — four columns, ruled as a judgment
    on 2026-09-05 so that *"a utility holds New connection and Leak
    investigation for Water at once"*. The seeded set already contains the
    proof: **two templates are both called *Meter set***, one electric
    (`ST-0002`) and one water (`ST-0005`). *Meter exchange — residential*
    happens to be unique today, so taking the first match has always returned
    the right row — **by luck, not by construction.** The day a utility adds a
    gas one, this would bind seven nightly rules to whichever row the queryset
    happened to order first, and every one of them would raise the wrong
    checklist onto a real job with nothing anywhere going red.

    So an AMBIGUOUS name is now refused BY NAME rather than resolved by
    position (`BR-TEN-060`: a named not-loaded line, never a silent wrong
    answer). Renaming the two *Meter set* rows was considered and rejected — the
    Templates screen carries a Service column and a *Filter by service* control,
    `BR-WRK-010` explicitly allows more than one template per service, and a
    utility genuinely calls both of them that. **The duplicate is lawful; the
    by-name lookup was the bug.**
    """
    matches = [
        template
        for template in metering_seam.templates_queryset()
        if getattr(template, "name", None) == EXCHANGE_TEMPLATE_NAME
        and getattr(template, "active", False)
        and int(getattr(template, "version", 0) or 0) >= 1
    ]
    if not matches:
        return None
    if len(matches) > 1:
        logger.info(
            "sample data (CR-070 wave M): no work-order rules were seeded — this tenant has "
            "%d published %r templates, on services %s, and a rule must name ONE. A template "
            "name is unique per SERVICE and not per tenant, so this cannot be resolved by "
            "picking the first. Point the rules at a template by id, or give these rows "
            "distinguishable names on Work > Templates",
            len(matches),
            EXCHANGE_TEMPLATE_NAME,
            ", ".join(sorted(str(getattr(m, "service_id", "?")) for m in matches)),
        )
        return None
    return str(matches[0].id)


#: `DEF-WRK-9687` — the template the backflow rule raises. Seeded here because
#: no seeded template is done TO a backflow preventer, and the rule exists only
#: to raise one; the six `sample_field_work` fills are untouched.
BACKFLOW_TEMPLATE_NAME = "Backflow test"


def _backflow_template_id(actor: Any) -> str | None:
    """The published *Backflow test* template, created on first need, or None.

    ⚠ **DONE TO A BACKFLOW PREVENTER AND NOTHING ELSE.** Its one asset type is
    *Backflow preventer*, so `create_work_order`'s asset-type check passes on
    exactly the subjects the rule sweeps. A tenant with no such asset type gets
    None — the rule is then skipped by name below, as it always was.

    ⚠ **A SAVEPOINT AROUND THE WRITE (law 14)**: this runs inside tenancy's
    per-module transaction, and a refused insert on PostgreSQL would poison it.
    """
    from apps.work import templates_svc

    for template in metering_seam.templates_queryset():
        if (
            getattr(template, "name", None) == BACKFLOW_TEMPLATE_NAME
            and getattr(template, "active", False)
            and int(getattr(template, "version", 0) or 0) >= 1
        ):
            return str(template.id)
    type_ids = assets_seam.asset_type_ids_of_names(["Backflow preventer"])
    if not type_ids:
        return None
    try:
        with transaction.atomic():
            header = templates_svc.create_draft(
                actor,
                {"name": BACKFLOW_TEMPLATE_NAME, "service": "water", "scope": "per_asset",
                 "sequence": 0},
            )
            tid = header["id"]
            templates_svc.replace_collection(
                actor,
                tid,
                "tasks",
                [
                    {"title": "Test the assembly and note each check valve", "est_minutes": 20},
                    {"title": "Seal and tag the assembly with today's date", "est_minutes": 5},
                ],
            )
            templates_svc.replace_collection(
                actor,
                tid,
                "readings",
                [{"prompt": "Differential pressure", "unit_of_measure": "psid", "min": "0",
                  "max": "20", "required": True, "posts_as_meter_read": False}],
            )
            templates_svc.replace_collection(
                actor, tid, "asset-types", [{"asset_type_id": str(type_ids[0])}]
            )
            templates_svc.publish(actor, tid)
    except Exception as exc:  # noqa: BLE001 — named, never swallowed
        logger.info(
            "sample data (CR-168 FIX-8A): the %r template was not seeded — %s: %s. The "
            "Backflow test due rule is skipped rather than pointed at a meter template",
            BACKFLOW_TEMPLATE_NAME, type(exc).__name__, exc,
        )
        return None
    return str(tid)


def _priority_id(code: str) -> Any:
    """One of the four seeded `work_priorities`, by code, or None.

    None is lawful and is not a fallback to *Normal*: `work_order_rules.
    priority` is nullable precisely so that a rule naming no priority lets the
    TEMPLATE's own default stand, and inventing one here would silently
    override a template whose author chose Urgent.
    """
    from apps.work import models as work_models

    return (
        work_models.WorkPriority.objects.filter(tenant_id=_tenant_id(), code=code)
        .values_list("id", flat=True)
        .first()
    )


def seed_sample_records(actor: Any) -> int:
    """`BR-TEN-056/057` — this module's block: the seven rules of `Work-026`.

    Returns the number of rules it CREATED, which is 0 on a replay and 0 again
    on a tenant that already has them — both of which are success, not a skip.
    """
    template_id = _exchange_template_id()
    if template_id is None:
        # BR-TEN-060 — a NAMED not-loaded line and not a silent zero. This is
        # the one precondition this block cannot supply for itself: the
        # template is metering's row, published by metering's own block.
        logger.info(
            "sample data (CR-070 wave M): no work-order rules were seeded — this tenant has "
            "no PUBLISHED %r template for them to raise, so every rule would show 'This "
            "month 0' for ever (BR-WRK-016). Check the Premises, units & service points "
            "block above, which is what publishes it",
            EXCHANGE_TEMPLATE_NAME,
        )
        return 0

    existing = set(
        WorkOrderRule.objects.filter(tenant_id=_tenant_id()).values_list("name", flat=True)
    )
    written = 0
    for spec in SEEDED_RULES:
        # BR-TEN-063 — the identity is the NAME, which is also the database's
        # own unique key. A tenant that renamed or switched a seeded rule off
        # keeps its answer; a replay writes nothing.
        if spec["name"] in existing:
            continue
        params = dict(spec.get("params") or {})
        names = spec.get("asset_type_names")
        if names:
            type_ids = assets_seam.asset_type_ids_of_names(list(names))
            if not type_ids:
                # The tenant does not use this kind of asset. Seeding the rule
                # UNRESTRICTED would silently widen it to every asset the
                # utility owns — a *Backflow test due* rule that raises on
                # meters. Named, skipped, and the other six still land.
                logger.info(
                    "sample data (CR-070 wave M): rule %r was not seeded — this tenant has "
                    "no %s asset type, and seeding it unrestricted would point it at every "
                    "asset instead of none",
                    spec["name"],
                    " / ".join(names),
                )
                continue
            params["asset_type_ids"] = type_ids
        rule_template_id = template_id
        if spec.get("template") == "backflow":
            rule_template_id = _backflow_template_id(actor)
            if rule_template_id is None:
                logger.info(
                    "sample data (CR-168 FIX-8A): rule %r was not seeded — there is no %r "
                    "template for it to raise, and the meter-exchange template would be "
                    "refused on every backflow preventer it found (DEF-WRK-9687)",
                    spec["name"], BACKFLOW_TEMPLATE_NAME,
                )
                continue
        payload = {
            "name": spec["name"],
            "triggers": [{"kind": spec["process"], "params": params}],
            "template_id": rule_template_id,
            "enabled": bool(spec.get("enabled", True)),
        }
        priority_id = _priority_id(spec["priority"]) if spec.get("priority") else None
        if priority_id:
            payload["priority_id"] = priority_id
        try:
            # ⚠ **THE SAVEPOINT IS THE POINT OF THIS BLOCK** (CLAUDE.md hard-won
            # law 14, and `G66` fails the merge without it). This loop runs
            # inside tenancy's per-module `atomic`, and on PostgreSQL ONE
            # refused INSERT aborts the WHOLE transaction — so the `except`
            # below would "continue" into `InFailedSqlTransaction` on every
            # later statement and lose the rules already written, at COMMIT,
            # while passing the entire SQLite suite green (`config/settings/
            # test.py` hardcodes in-memory SQLite, which has no aborted-
            # transaction state). `create_rule` opens one of its own, and that
            # is exactly why this is here anyway: relying on a callee's
            # internal savepoint makes this function's correctness depend on a
            # detail of another function that no test of THIS one would notice
            # changing. NOT tidiness — do not remove.
            with transaction.atomic():
                created = rules.create_rule(actor, payload)
        except Exception as exc:  # noqa: BLE001 — named, never swallowed
            logger.info(
                "sample data (CR-070 wave M): rule %r was not seeded — %s: %s. Work > Rules "
                "will list one row fewer than the drawing",
                spec["name"],
                type(exc).__name__,
                exc,
            )
            continue
        written += 1
        # BR-TEN-057 — the tag on the owning row, written by this module on its
        # OWN table. `create_rule` does not accept it and must not: a utility
        # authoring a rule must never be able to mark it as sample data, or
        # `--remove` would take work it wrote itself.
        WorkOrderRule.objects.filter(tenant_id=_tenant_id(), pk=created["id"]).update(
            is_sample=True
        )
    return written


def remove_sample_records() -> dict[str, Any]:
    """`BR-TEN-061/066` — delete this module's `is_sample` rules, name the rest.

    ⚠ **A RULE THAT HAS ALREADY RAISED IS RETAINED, BY NAME.**
    `work_order_rule_raises.rule` is `ON DELETE CASCADE`, so deleting the rule
    would delete THE SWEEP'S MEMORY — and the memory is what stops the same
    meter being raised again (`rules_models.py`'s module docstring says so at
    length). Removing sample data must not make tonight's sweep re-raise a job
    a crew already did. So a rule with raises is switched **off** and reported
    as retained, which is `BR-TEN-066`'s partial-and-named answer.
    """
    tenant_id = _tenant_id()
    from apps.work.rules_models import WorkOrderRuleRaise

    removed = 0
    retained: list[dict[str, Any]] = []
    for row in WorkOrderRule.objects.filter(tenant_id=tenant_id, is_sample=True):
        if WorkOrderRuleRaise.objects.filter(tenant_id=tenant_id, rule_id=row.id).exists():
            if row.enabled:
                row.enabled = False
                row.save(update_fields=["enabled", "updated_at"])
            retained.append(
                {
                    "label": f"rule {row.name}",
                    "reason": (
                        "it has already raised work orders; deleting it would delete the "
                        "record of what it raised and tonight's sweep would raise them "
                        "again. It is switched off instead"
                    ),
                }
            )
            continue
        row.delete()
        removed += 1
    return {"removed": removed, "retained": retained}


def sample_record_count() -> int:
    """How many sample rules this module holds right now, read live."""
    return int(WorkOrderRule.objects.filter(tenant_id=_tenant_id(), is_sample=True).count())


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-037@d1b76486 (EP-WRK-07) · 10-execution-plan.md wave M task M5
# generated: 2026-09-05 by the CR-070 wave M fixture lane (DEF-WRK-4085)
# checklist: A✔ B✔ C✔ D=n/a(no endpoint) E=n/a(no screen of its own — S62 renders the block) F✔ G✔ H=n/a
# gates: pytest tests/test_cr070_m_sample_data.py · G78 · run_gates
# exceptions: `Reconnect after payment` is NOT seeded — the engine has no reader for its trigger (OQ-WRK-1726 / DEF-WRK-4096); `Backflow test due` carries the past-due reader rather than the drawing's 30-day lead time, and is OFF
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

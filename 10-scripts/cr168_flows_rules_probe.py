"""CR-168-BRC10 lane FLOW-MEASURE — does a RULE-raised job get past the source check?

`apps/work/rules.py::_raise_one` stamps ``source = rule.source_module``, and a
rule's source module is one of FIVE words (``WorkOrderRule.SOURCE_MODULES``:
payments · billing · assets · reads · accounts). ``create_work_order`` refuses
any ``source`` outside ``WORK_ORDER_SOURCES`` (sixteen tokens) with
``work.order.source_unknown``. Only ``assets`` is in both lists.

This probe asks the question the way the nightly sweep does, on PostgreSQL:

  1. For each of the five source modules, raise ONE job through the same seam
     the sweep uses (``metering_seam.raise_work_order``), inside a SAVEPOINT that
     is always rolled back, and print accepted / refused with the message key.
  2. Count every work order in the demo tenant by ``source`` and print it.
  3. Count the job types (``work_order_types``: types and sub-types) and the
     templates, and which ``source`` each template's raised orders carry.

Writes NOTHING that survives: step 1 is rolled back, steps 2-3 only read.

    cd 06-backend && DATABASE_URL=postgres://postgres@127.0.0.1:55433/sbh_wflows \\
      DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      /tmp/venv_a5c/bin/python manage.py shell < ../10-scripts/cr168_flows_rules_probe.py
"""
from collections import Counter

from django.db import transaction

from apps.identity import models as identity_models
from apps.work import connection_models as work_tables
from apps.tenancy.models import Tenant
from apps.work import models as work_models
from apps.work import rules_models
from apps.work.seams import metering_seam
from core import tenancy as core_tenancy


class _Rollback(Exception):
    pass


tenant = Tenant.objects.get(subdomain="brazosbend")
with core_tenancy.tenant_context(tenant.id):
    dana = identity_models.User.objects.filter(tenant_id=tenant.id, email__startswith="dana").first()
    anchor = work_tables.WorkOrder.objects.filter(premises_id__isnull=False).values("premises_id").first()
    print("== 1 · a rule-raised job, per source module (rolled back) ==")
    for module in rules_models.WorkOrderRule.SOURCE_MODULES:
        verdict = None
        try:
            with transaction.atomic():
                metering_seam.raise_work_order(
                    dana,
                    {
                        "premises_id": str(anchor["premises_id"]),
                        "type": "Probe",
                        "source": module,
                        "source_ref": f"probe rule ({module})",
                    },
                )
                verdict = "ACCEPTED"
                raise _Rollback
        except _Rollback:
            pass
        except Exception as exc:  # noqa: BLE001 - the refusal IS the measurement
            verdict = f"REFUSED {type(exc).__name__} {getattr(exc, 'message_key', '')}"
        print(f"  rule source_module={module!r:12} in WORK_ORDER_SOURCES={module in work_tables.WORK_ORDER_SOURCES!s:5} -> {verdict}")

    print("\n== 2 · work orders in the demo tenant, by source ==")
    counts = Counter(work_tables.WorkOrder.objects.values_list("source", flat=True))
    for token in (*work_tables.WORK_ORDER_SOURCES, None):
        print(f"  {token!s:22} {counts.get(token, 0)}")
    print(f"  TOTAL                  {sum(counts.values())}")

    print("\n== 3 · job types and templates ==")
    types = work_models.WorkOrderType.objects.all()
    parents = [t for t in types if t.parent_id is None]
    children = [t for t in types if t.parent_id is not None]
    print(f"  work_order_types: {len(parents)} types, {len(children)} sub-types ({types.count()} rows)")
    templates = work_tables.WorkOrderTemplate.objects.all().order_by("name")
    print(f"  work_order_templates: {templates.count()} rows, published (version>=1, active): "
          f"{templates.filter(active=True, version__gte=1).count()}")
    for tpl in templates:
        used = Counter(work_tables.WorkOrder.objects.filter(template_id=tpl.id).values_list("source", flat=True))
        svc = tpl.service.code if tpl.service_id else "-"
        jt = tpl.type.name if tpl.type_id else "-"
        print(f"   - {tpl.name!s:40} job_type={jt!s:22} service={svc:10} scope={tpl.scope!s:9} gate={tpl.is_gate!s:5} "
              f"active={tpl.active!s:5} v{tpl.version}  orders by source: {dict(used) or '{}'}")
    untyped = Counter(work_tables.WorkOrder.objects.filter(template_id__isnull=True).values_list("type", flat=True))
    print(f"  orders with NO template, by free-text type: {dict(untyped)}")
    rules = rules_models.WorkOrderRule.objects.all()
    print(f"\n  work_order_rules: {rules.count()} -> " + ", ".join(
        f"{r.name} ({r.source_module}/{r.trigger_kind}, enabled={r.enabled})" for r in rules))

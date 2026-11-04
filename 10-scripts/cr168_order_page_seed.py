"""CR-168-BRC10 round 2, lane ORDER-PAGE — two jobs in the shapes images 03-11 draw.

Run inside `manage.py shell` against a SCRATCH database seeded with
`seed_demo` + `load_sample_data --tenant brazosbend` (never a real tenant):

    DATABASE_URL=... DJANGO_SETTINGS_MODULE=config.settings.local \
      python manage.py shell < 10-scripts/cr168_order_page_seed.py

It raises two orders from *Meter exchange — residential* on meter W-5000 (Unit 1,
101 Silver Creek Rd, AC-2026-00001) — the job the drawing was captured on:

  * OPEN — assigned to D. Ortiz for tomorrow 09:00-12:00 (images 03, 05, 07, 08,
    10, 11);
  * COMPLETED — the same, then worked AS D. ORTIZ: every safety line and task
    ticked, readings taken, two task photographs and one reading photograph, the
    customer's signature, and the field result sent (images 04, 06, 09).

The completion is made by the technician's own user, never the office's, because
ruling 18 says only the field completes a job. Prints the two order numbers.
"""
import io
import struct
import zlib
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.identity.models import User
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import checklist, evidence
from apps.work import dispatch
from apps.work import models as wm
from core import tenancy as ct


def png(width, height, painter):
    rows = b""
    for y in range(height):
        rows += b"\x00" + b"".join(bytes(painter(x, y)) for x in range(width))
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def dial(bg):
    def paint(x, y):
        dx, dy = x - 160, y - 120
        r2 = dx * dx + dy * dy
        if r2 < 80 * 80 and 95 < y < 125 and 110 < x < 210:
            return (25, 25, 30)          # the register window
        if r2 < 90 * 90:
            return (232, 230, 222)       # the face
        if r2 < 100 * 100:
            return (40, 42, 48)          # the bezel
        return bg
    return png(320, 240, paint)


def signature_mark():
    import math
    def paint(x, y):
        wave = 50 + int(28 * math.sin(x / 14.0) * (1 if x < 280 else 0))
        return (20, 20, 20) if abs(y - wave) < 2 and 20 < x < 300 else (255, 255, 255)
    return png(320, 100, paint)


tid = ct.tenant_id_for_slug("brazosbend")
with ct.tenant_context(tid):
    dana = User.objects.get(email="dana@brazosbendutilities.com")
    ortiz_tech = wm.Technician.objects.select_related("user").get(tenant_id=tid, user__full_name="D. Ortiz")
    ortiz = ortiz_tech.user
    template = work_tables.WorkOrderTemplate.objects.filter(tenant_id=tid, name="Meter exchange — residential").order_by("-version").first()
    # Looked up by the numbers a person reads, never by uuid: a uuid is minted
    # when the demo is built, so a literal one only exists in the database it
    # was copied from (round 3, lane MAP2 — the literals here refused on a
    # fresh build with `deny_as_not_found("BR-TEN-003")`).
    from django.apps import apps as django_apps
    asset_id = str(django_apps.get_model("assets", "Asset").objects.get(tenant_id=tid, asset_no="W-5000").id)
    unit_id = str(django_apps.get_model("metering", "Unit").objects.filter(
        tenant_id=tid, premises__address_line="101 Silver Creek Rd").order_by("unit_no").first().id)
    account_id = str(django_apps.get_model("customers", "Account").objects.get(tenant_id=tid, account_no="AC-2026-00001").id)
    tomorrow = (timezone.localtime() + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)

    made = {}
    for label in ("open", "completed"):
        order = w6.create_work_order(dana, None, {
            "asset_id": asset_id, "unit_id": unit_id, "account_id": account_id,
            "template_id": str(template.id), "type": "Meter exchange — residential", "source": "dispatcher",
        })
        oid = order["id"]
        dispatch.record_act(dana, oid, {
            "act": "assign", "technician_id": str(ortiz_tech.id),
            "window_start": tomorrow.isoformat(), "window_end": (tomorrow + timedelta(hours=3)).isoformat(),
        })
        made[label] = (oid, order.get("order_no"))

    oid = made["completed"][0]
    for row in wm.WorkOrderSafety.objects.filter(work_order_id=oid).order_by("seq"):
        checklist.tick_safety(ortiz, oid, row.id)
    tasks = list(wm.WorkOrderTask.objects.filter(work_order_id=oid).order_by("seq"))
    for task in tasks:
        if task.photo_required:
            evidence.record_attachment(ortiz, oid, {
                "idempotency_key": f"cr168-task-{task.seq}-{oid}", "task_id": str(task.id),
                "content_type": "image/png", "display_name": f"task-{task.seq}.png",
            }, SimpleUploadedFile(f"task-{task.seq}.png", dial((134, 122, 104) if task.seq == 1 else (96, 110, 128)), content_type="image/png"))
        checklist.tick_task(ortiz, oid, task.id)
    for reading in wm.WorkOrderReading.objects.filter(work_order_id=oid).order_by("seq"):
        if reading.unit_of_measure in ("gal", "kgal", "ft3", "kWh", "m3"):
            evidence.set_reading(ortiz, oid, reading.id, {"value": "4821" if reading.seq == 1 else "0", "unit": reading.unit_of_measure})
            if reading.seq == 1:
                evidence.record_attachment(ortiz, oid, {
                    "idempotency_key": f"cr168-reading-1-{oid}", "reading_id": str(reading.id),
                    "content_type": "image/png", "display_name": "reading-1.png",
                }, SimpleUploadedFile("reading-1.png", dial((134, 122, 104)), content_type="image/png"))
    evidence.capture_signature(ortiz, oid, {"printed_name": "Ana Alvarez"},
                               SimpleUploadedFile("signature.png", signature_mark(), content_type="image/png"))
    try:
        w6.submit_field_result(ortiz, oid, field_data={}, outcome="passed")
    except Exception as exc:  # report, do not hide — a refusal here is a finding
        print("FIELD RESULT REFUSED:", type(exc).__name__, getattr(exc, "message_key", exc))
    print("OPEN", made["open"][1], made["open"][0])
    print("COMPLETED", made["completed"][1], made["completed"][0])

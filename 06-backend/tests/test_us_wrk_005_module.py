# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-005 (EP-WRK-01) — `apps/work/`: the eleventh module, its
#           read-only seams, the migrated-list entry, and the gate that proves
#           it writes nothing of anyone else's.
# Rules:    BR-WRK-001 (Work is its own module) · BR-WRK-002 (one read-only
#           seam per module; a gate) · B14 rule 21 + the per-file clause
#           (`route-b-migrated.txt`, DEF-974) · CR-070 §2(a) (the module map
#           moves in the commit that carries the first migration) · CLAUDE.md
#           hard rule 1 (a seam read with no tenant context answers nothing)
# Tests:    this file — TC-1 · TC-2 · TC-3 · TC-4 · TC-5 · TC-6 · TC-7
# ───────────────────────────────────────────────────────
"""US-WRK-005 — the module exists, inside a wall.

TC-3 and TC-4 are the gate's own red-proofs, applied to a COPY of the real
`apps/work` in a temp directory: one line is added, the gate must name the
file, the line and the model, and the repo is never touched (G53's self-test
records why a proof that sabotages real repo content is worthless the day
that content is already broken).
"""

from __future__ import annotations

import importlib.util
import inspect
import shutil
import tempfile
from pathlib import Path

import pytest
from django.conf import settings

from core import tenancy as core_tenancy

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_premises, tenant_ctx

REPO = Path(__file__).resolve().parents[2]
WORK_APP = REPO / "06-backend" / "apps" / "work"
GATE = REPO / "10-scripts" / "gates" / "g78_work_writes_nothing_foreign.py"
MIGRATED = REPO / "07-frontend" / "src" / "styles" / "route-b-migrated.txt"
FORBIDDEN_PREFIXES = ("create_", "set_", "update_", "delete_", "post_")


def _gate():
    """The gate module, loaded by path — `10-scripts/gates` is not a package."""
    import sys

    gates_dir = str(GATE.parent)
    if gates_dir not in sys.path:
        sys.path.insert(0, gates_dir)
    spec = importlib.util.spec_from_file_location("g78_work_writes_nothing_foreign", GATE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _copy_of_work_app() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="g78-"))
    target = tmp / "work"
    shutil.copytree(WORK_APP, target, ignore=shutil.ignore_patterns("__pycache__"))
    return target


# ── TC-1 · the app exists and the map names it ──────────────────────────────
def test_us_wrk_005_tc1_the_app_is_installed_and_the_module_map_names_it():
    assert "apps.work" in settings.INSTALLED_APPS
    from django.apps import apps

    assert apps.get_app_config("work").name == "apps.work"
    claude_md = (REPO / "CLAUDE.md").read_text(encoding="utf-8")
    module_map = claude_md.split("## Module map", 1)[1].split("\n## ", 1)[0]
    assert "work" in module_map, "CLAUDE.md's module map does not name `work` (CR-070 §2(a))"


# ── TC-2 · the gate over the real tree is clean ─────────────────────────────
def test_us_wrk_005_tc2_the_boundary_gate_passes_with_zero_findings():
    gate = _gate()
    assert gate.selftest(), "G78's own self-test does not hold"
    assert gate.scan(WORK_APP) == []
    status, detail = gate.run()
    assert status == "PASS", detail


# ── TC-3 · a foreign write in services.py is named ──────────────────────────
def test_us_wrk_005_tc3_one_foreign_update_in_services_fails_the_gate_naming_the_line():
    gate = _gate()
    copy = _copy_of_work_app()
    services = copy / "services.py"
    source = services.read_text(encoding="utf-8")
    sabotaged = source.replace(
        "from apps.work.seams import metering_seam\n",
        "from apps.assets.models import Asset\n"
        "from apps.work.seams import metering_seam\n\n\n"
        "def retire(order_id):\n"
        '    Asset.objects.filter(pk=order_id).update(status="retired")\n',
        1,
    )
    assert sabotaged != source
    services.write_text(sabotaged, encoding="utf-8")
    findings = gate.scan(copy)
    assert any("services.py" in f and "Asset.objects.update" in f for f in findings), findings
    assert any("imports apps.assets.models outside seams/" in f for f in findings), findings
    # the line is named, as a number
    assert all(":" in f and f.split(":")[1].split(" ")[0].isdigit() for f in findings), findings


# ── TC-4 · a foreign models import outside seams/ is named, even for a read ──
def test_us_wrk_005_tc4_a_foreign_models_import_outside_seams_fails_the_gate():
    gate = _gate()
    copy = _copy_of_work_app()
    (copy / "dispatch.py").write_text(
        "from apps.assets.models import Asset\n\n\ndef plan(asset_id):\n"
        "    return Asset.objects.filter(pk=asset_id).first()\n",
        encoding="utf-8",
    )
    findings = gate.scan(copy)
    assert findings == [
        f"{copy.relative_to(copy)}dispatch.py:1 imports apps.assets.models outside seams/ (BR-WRK-002)"
    ] or (
        len(findings) == 1
        and "dispatch.py:1 imports apps.assets.models outside seams/" in findings[0]
    ), findings
    # …and the SAME import inside seams/ is lawful: a seam is where models are read.
    (copy / "dispatch.py").unlink()
    (copy / "seams" / "assets_read.py").write_text(
        "from apps.assets.models import Asset\n\n\ndef asset(asset_id):\n"
        "    return Asset.objects.filter(pk=asset_id).first()\n",
        encoding="utf-8",
    )
    assert gate.scan(copy) == []


# ── TC-5 · every new Work screen file is on the migrated list ───────────────
def test_us_wrk_005_tc5_every_features_work_screen_is_on_route_b_migrated():
    """B14 rule 21's per-file clause (DEF-974): a Tailwind utility is emitted
    ONLY for a file on this list. The test asserts the LIST ENTRY, never that a
    class is in the DOM — a class is in the DOM either way, which is the trap."""
    listed = {line.strip() for line in MIGRATED.read_text(encoding="utf-8").splitlines()}
    work_dir = REPO / "07-frontend" / "src" / "features" / "work"
    screens = sorted(
        p.relative_to(REPO / "07-frontend" / "src").as_posix()
        for p in work_dir.glob("*.tsx")
        if not p.name.endswith(".test.tsx")
    )
    assert screens, "no Work screens under features/work"
    missing = [s for s in screens if s not in listed]
    assert (
        missing == []
    ), f"not on route-b-migrated.txt — their utilities render as NOTHING: {missing}"


# ── TC-6 · each seam exposes reads only ─────────────────────────────────────
#: `DEF-WRK-4035` / `DEF-WRK-9604` — the SANCTIONED exceptions, each with why.
#:
#: These are not table writes by Work: each delegates, BY NAME, to the owning
#: module's own service function, which is the one shape `BR-WRK-002` and
#: `CR-168-BRC10` §7.3 (*"Seams crossing modules (all READ, except metering's
#: own services called by name)"*) allow — `G78` still fails any ORM write to a
#: foreign table. The work-order templates live in `apps/metering/connections.py`
#: until `16-work/03-field-map.md` §4 moves them, so the template builder's four
#: writes reach metering's own `*_work_order_template` services through here,
#: and `post_set_reads` is `BR-WRK-003`'s one door into metering's
#: `commit_event_reads`. The case went red from wave D (2026-09-05) to
#: 2026-10-05 because the list was never written down; it is written down now,
#: and a NEW write-verb name still fails until somebody adds it here with its
#: citation — which is the point of keeping the case.
SANCTIONED_SERVICE_DOORS: dict[str, dict[str, str]] = {
    "metering_seam": {
        "create_template": "metering.create_work_order_template — the template builder (wave D)",
        "update_template": "metering.update_work_order_template — the template builder (wave D)",
        "set_template_active": "metering.set_work_order_template_active — the template builder (wave D)",
        "delete_template": "metering.delete_work_order_template — the template builder (wave D)",
        "post_set_reads": "metering.services.commit_event_reads — BR-WRK-003, US-WRK-046",
    },
}


@pytest.mark.parametrize(
    "seam_name", ["metering_seam", "customers_seam", "assets_seam", "tenancy_seam", "identity_seam"]
)
def test_us_wrk_005_tc6_a_seam_exposes_no_write_verb(seam_name):
    module = importlib.import_module(f"apps.work.seams.{seam_name}")
    public = [
        name
        for name, obj in inspect.getmembers(module, inspect.isfunction)
        if not name.startswith("_") and obj.__module__ == module.__name__
    ]
    assert public, f"{seam_name} publishes nothing"
    sanctioned = SANCTIONED_SERVICE_DOORS.get(seam_name, {})
    offenders = [
        name for name in public if name.startswith(FORBIDDEN_PREFIXES) and name not in sanctioned
    ]
    assert offenders == [], f"{seam_name} publishes a write verb: {offenders}"
    # A sanctioned name that no longer exists is a stale exception — remove it.
    stale = sorted(set(sanctioned) - set(public))
    assert stale == [], f"{seam_name}: sanctioned doors that are gone: {stale}"


# ── TC-7 · a seam read with no tenant context answers nothing ───────────────
@pytest.mark.django_db
def test_us_wrk_005_tc7_every_seam_read_answers_nothing_without_a_tenant(dana, brazos):
    from apps.work.seams import (
        assets_seam,
        customers_seam,
        identity_seam,
        metering_seam,
        tenancy_seam,
    )

    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="77 Cedar Ct")
        assert metering_seam.premises(premises["id"]) is not None
        assert tenancy_seam.enabled_service_codes()  # Brazos Bend sells something
        user_id = dana.id

    core_tenancy.clear_current_tenant()
    assert core_tenancy.current_tenant_id() is None
    assert metering_seam.premises(premises["id"]) is None
    assert metering_seam.connection(premises["id"]) is None
    assert list(metering_seam.open_work_orders_queryset()) == []
    assert customers_seam.account(premises["id"]) is None
    assert assets_seam.asset(premises["id"]) is None
    assert identity_seam.user(user_id) is None
    assert tenancy_seam.enabled_service_codes() == set()
    assert tenancy_seam.areas() == []
    assert tenancy_seam.certification_types() == []
    assert tenancy_seam.number_series_row("work_order") is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-005@87b94265 (EP-WRK-01 §3 TC-1..TC-7) · BR-WRK-001 · BR-WRK-002 · G78
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B=n/a(no screen by design — the story says so) C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: G78 shown RED on the real services.py before it was trusted (quoted in the gate's docstring) · this file's TC-3/TC-4 repeat the proof on a copy every run
# exceptions: TC-1's "eleventh" is read as the module map naming `work`, not as a count of INSTALLED_APPS — that list holds hosting apps (assets, audit, reports) the map does not number
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

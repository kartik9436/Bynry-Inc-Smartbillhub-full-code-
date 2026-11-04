# ── Trace ──────────────────────────────────────────────
# Story:    US-TEN-020 (EP-TEN-03 — keeping existing tenants current as seed
#           data evolves: `manage.py sweep_reference_data`)
# Rules:    BR-TEN-070 (the ledger IS the mechanism) · BR-TEN-071 (insert-if-
#           absent; never UPDATE/DELETE) · BR-TEN-072 (renames forbidden) ·
#           BR-TEN-073 (three categories) · BR-TEN-074 (per-tenant context and
#           transaction, failures isolated) · BR-TEN-075 (audited) · BR-TEN-076
#           (the dry-run writes nothing) · BR-TEN-077 (version-bump policy +
#           content guard) · BR-TEN-078 (no bill-run interlock) · BR-TEN-079
#           (the "behind" read) · BR-TEN-067 (structural catalogues)
# Note:     THE STORY'S TC-6 AND TC-13 ARE AMENDED, NOT IGNORED. Both were
#           written on 2026-08-10 asking for `NotImplementedError("OQ-086")` /
#           `("OQ-088")` stubs; both questions CLOSED the same day, and G8 fails
#           a stub citing a closed OQ. Each test below implements the RULING and
#           says which one in its own docstring.
#           The vendor guard is asserted for real in TC-10; every other command
#           TC patches the command module's `connection` so the body is
#           reachable on the sqlite tier (live-Postgres behaviour = TC-8/G5).
# ───────────────────────────────────────────────────────
"""US-TEN-020 — the reference-data sweep: plan, dry-run, walk, report, guards."""

import json
from types import SimpleNamespace

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

import apps.audit.services as audit_services
import apps.metering.services as metering_services
from apps.audit.models import AuditLog
from apps.metering.models import PremisesType
from apps.tenancy import models, reference_sweep, services

#: ⚠ DERIVED, NEVER TYPED (DEF-213). Every one of these assertions used to carry
#: the literal `"2026.08"`. The fixture has been bumped TWICE since — to
#: `2026.08.1` for CR-004's six lists and DEF-185's corrected vocabulary, then to
#: `2026.08.2` when DEF-187's fix corrected three meter-size names whose phase
#: symbol was double-escaped — and this suite moved with NEITHER. Thirteen cases
#: went red and stayed red.
#:
#: The version-KEY arithmetic below is deliberately left as literals: those
#: assertions are about the ORDERING function, not about what the product ships,
#: and deriving them would make them tautologies.
SHIPPED = reference_sweep.fixture_version()
#: The staged "next" version, DERIVED from SHIPPED by bumping the build digit —
#: the same DEF-213 lesson one line up, learned a second time on 2026-08-17:
#: these cases staged the literal "V1.0.0.1" as the future version, the real
#: fixture then bumped TO V1.0.0.1 (CR-010 A-section), and eight cases went red
#: with `'current' == 'seed'` because the "future" had become the present.
NEXT = "V" + ".".join(
    SHIPPED[1:].split(".")[:3] + [str(int(SHIPPED[1:].split(".")[3]) + 1)]
)
from apps.tenancy.management.commands import sweep_reference_data as sweep_cmd

from tests.isolation_helpers import (  # noqa: F401 — fixtures used by name
    assert_denied_without_context,
    assert_rls_scoped,
    live_tenant_context,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    audit_actions,
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

STRUCTURAL = sorted(services.STRUCTURAL_REFERENCE_LISTS)
#: Tenant-owned reference data (BR-TEN-073 category 2). `account_types` is
#: excluded because B2 r5 #12 [D5] makes it a PLATFORM table — see
#: reference_sweep.PLATFORM_REFERENCE_LISTS.
DISCRETIONARY = sorted(
    {code for code, _ in services.SEED_LIST_OWNERS}
    - services.STRUCTURAL_REFERENCE_LISTS
    - reference_sweep.PLATFORM_REFERENCE_LISTS
)


def forget_list(tenant, list_code, *, rows_model=None):
    """Model a tenant that never received a list: drop its ledger row AND its
    rows, so the sweep genuinely re-delivers instead of writing a zero count.

    Worth saying why it matters: a re-seed that creates 0 rows records
    `seeded_count = 0`, and `reference_data_report()` then reads a handler-less
    list as UNEXPLAINED rather than `uncounted` — a real (pre-existing) sharp
    edge in that report, and not the thing these TCs are about.
    """
    models.ReferenceSeedRun.objects.filter(tenant=tenant, list_code=list_code).delete()
    if rows_model is not None:
        rows_model.objects.filter(tenant=tenant).delete()


# ── plumbing ────────────────────────────────────────────────────────────────
@pytest.fixture()
def pg_vendor(monkeypatch):
    """Make the command's vendor guard pass on the sqlite tier.

    The guard itself is asserted in TC-10 against the REAL `connection`, so
    patching it here removes a precondition from the other TCs without removing
    it from the suite.
    """
    monkeypatch.setattr(sweep_cmd, "connection", SimpleNamespace(vendor="postgresql"))


@pytest.fixture()
def staged_fixture(monkeypatch):
    """Stage a fixture edit the way a real lane would: content + version + the
    BR-TEN-077 digest pin, all three together.

    Returns a callable `stage(mutate=None, version=None, pin=True)`. `pin=False`
    stages the DEFECT BR-TEN-077 exists to catch — content moved, version did not.
    """
    original = services._load_seed_fixture()

    def stage(mutate=None, version=None, pin=True):
        payload = json.loads(json.dumps(original))
        if mutate is not None:
            mutate(payload)
        if version is not None:
            payload["version"] = version
        monkeypatch.setattr(services, "_load_seed_fixture", lambda: payload)
        if pin:
            digest = reference_sweep.fixture_content_digest()
            monkeypatch.setitem(
                reference_sweep.RATIFIED_FIXTURE_DIGESTS, payload["version"], digest
            )
        return payload

    return stage


def sweep(**options):
    """Run the command, returning nothing; CommandError carries the exit code."""
    call_command("sweep_reference_data", **options)


def seed_run_versions(tenant, list_code):
    return sorted(
        models.ReferenceSeedRun.objects.filter(tenant=tenant, list_code=list_code).values_list(
            "fixture_version", flat=True
        )
    )


# ── TC-1 · the dry-run writes NOTHING (BR-TEN-076) ──────────────────────────
def test_us_ten_020_tc1__dry_run_writes_nothing(
    growth_plan, identity_seam, audit_rows, pg_vendor, staged_fixture, capsys
):
    """US-TEN-020 TC-1 — plan printed, zero rows written.

    The counts compared are the three the sweep could possibly move: the seed-run
    ledger, the audit trail and a real reference table. Comparing only the ledger
    would let a dry-run that seeded rows without recording them pass.
    """
    tenant, _ = provisioned_tenant()
    staged_fixture(version=NEXT)
    before = (
        models.ReferenceSeedRun.objects.count(),
        len(audit_rows),
        models.Uom.objects.count(),
    )

    sweep(dry_run=True)

    after = (
        models.ReferenceSeedRun.objects.count(),
        len(audit_rows),
        models.Uom.objects.count(),
    )
    assert after == before, "a dry-run wrote something (BR-TEN-076)"
    out = capsys.readouterr().out
    assert tenant.subdomain in out
    assert f"{SHIPPED} → {NEXT}" in out  # DEF-213: derived, not typed
    assert "NOTHING was written" in out


# ── TC-2 · a wholly NEW list is delivered without a bump (BR-TEN-077) ───────
def test_us_ten_020_tc2__new_list_needs_no_bump(growth_plan, identity_seam, audit_rows, pg_vendor):
    """US-TEN-020 TC-2 — eligibility is keyed (list, version).

    A list with no seed-run row at ANY version is delivered by the next sweep at
    the CURRENT version. Modelled the way it actually happens — a list that was
    in no registry when this tenant signed up, so it carries no row — by removing
    `premises_types`' row, which is DEF-017's own seventh list and the worked
    case BR-TEN-077 cites.
    """
    tenant, _ = provisioned_tenant()
    forget_list(tenant, "premises_types", rows_model=PremisesType)
    assert seed_run_versions(tenant, "premises_types") == []
    assert PremisesType.objects.filter(tenant=tenant).count() == 0

    sweep()

    assert seed_run_versions(tenant, "premises_types") == [SHIPPED]
    # BR-MET-034's six (5 + government_building, CR-010 item 4), re-delivered
    # from metering's own ratified source.
    assert PremisesType.objects.filter(tenant=tenant).count() == 6
    # …and no other list gained a second row: they were all already current.
    for list_code in STRUCTURAL:
        assert len(seed_run_versions(tenant, list_code)) == 1


# ── TC-3 · an existing list, WITH a bump (BR-TEN-070/071) ───────────────────
def test_us_ten_020_tc3__bump_delivers_only_the_new_rows(
    growth_plan, identity_seam, audit_rows, pg_vendor, staged_fixture
):
    """US-TEN-020 TC-3 — 12 asset types in the fixture − 10 held = 2 inserted.

    The story's worked case (BR-AST-042's Container/Cart + Modem/CPE) run in
    reverse, because the fixture already carries 12: two are REMOVED from the
    tenant's holding, then the bump re-delivers exactly those two and touches
    nothing else. The arithmetic is the story's: 12 − 10 = 2.

    NARROWED BY OQ-088 (CLOSED, PO 2026-08-10): the story says "a V1.0.0.1 row is
    written for EVERY list, including the unchanged ones". Discretionary lists
    now get no row at all, because they are not delivered at all — see TC-13.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        handler = services.LOOKUP_LISTS["asset_types"].handler
        assert handler is not None, "assets registers this handler at AppConfig.ready"
        held_before = handler.count()
        assert held_before == 12
        for row in list(handler.search(None))[:2]:
            row.delete()
        assert handler.count() == 10

    staged_fixture(version=NEXT)
    sweep()

    with tenant_ctx(tenant):
        assert services.LOOKUP_LISTS["asset_types"].handler.count() == 12  # 10 + 2
    assert seed_run_versions(tenant, "asset_types") == [SHIPPED, NEXT]
    for list_code in DISCRETIONARY:
        assert NEXT not in seed_run_versions(tenant, list_code), (
            f"{list_code} is discretionary and must not be delivered by a bump — "
            "OQ-088 (PO 2026-08-10)"
        )


# ── TC-4 · replay (BR-TEN-010 posture) ──────────────────────────────────────
def test_us_ten_020_tc4__replay_creates_nothing(
    growth_plan, identity_seam, audit_rows, pg_vendor, staged_fixture
):
    """US-TEN-020 TC-4 — sweep twice, the second run writes nothing."""
    tenant, _ = provisioned_tenant()
    staged_fixture(version=NEXT)
    sweep()
    ledger_after_first = models.ReferenceSeedRun.objects.count()
    audit_after_first = len(audit_rows)

    sweep()

    assert models.ReferenceSeedRun.objects.count() == ledger_after_first
    assert len(audit_rows) == audit_after_first, "a replay wrote an audit row"


# ── TC-5 (neg) · the tenant's own edits survive (BR-TEN-071/072) ────────────
def test_us_ten_020_tc5__renamed_and_deactivated_rows_are_untouched(
    growth_plan, identity_seam, audit_rows, pg_vendor, staged_fixture
):
    """US-TEN-020 TC-5 — no UPDATE and no DELETE reaches a swept table.

    The tenant renames seeded meter type `ami` to "AMI (Itron 100G)" and
    deactivates `walk_by`. After a bumped sweep both are exactly as they left
    them and no duplicate `ami` exists — insert-if-absent means the natural key
    matched, so nothing was created and nothing was overwritten.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        handler = services.LOOKUP_LISTS["meter_types"].handler
        rows = {r.code: r for r in handler.search(None)}
        renamed, deactivated = rows["ami"], rows["walk_by"]
        renamed.name = "AMI (Itron 100G)"
        renamed.save(update_fields=["name"])
        deactivated.active = False
        deactivated.save(update_fields=["active"])
        count_before = handler.count()

    staged_fixture(version=NEXT)
    sweep()

    with tenant_ctx(tenant):
        handler = services.LOOKUP_LISTS["meter_types"].handler
        rows = list(handler.search(None))
        assert handler.count() == count_before, "the sweep created a duplicate"
        assert [r for r in rows if r.code == "ami"][0].name == "AMI (Itron 100G)"
        assert [r for r in rows if r.code == "walk_by"][0].active is False


# ── TC-6 (neg) · a CORRECTED value is NAMED, never applied (OQ-086) ─────────
def test_us_ten_020_tc6__correction_is_reported_and_not_applied(
    growth_plan, identity_seam, audit_rows, pg_vendor, staged_fixture, capsys
):
    """US-TEN-020 TC-6 — AMENDED: OQ-086 CLOSED 2026-08-10, so there is no stub.

    The story asks for `NotImplementedError("OQ-086")`; the PO closed OQ-086 the
    same day with option (b) — *an audited, opt-in "apply correction" that NAMES
    each affected row* — and G8 fails a stub citing a closed question. So the
    ruled behaviour is asserted instead: the held row is NOT changed
    (BR-TEN-071) and the run NAMES the divergence rather than silently doing
    nothing (the DEF-016 posture).

    The story's own worked case is a corrected tax RATE, which no registered
    lookup handler exposes — so this asserts BOTH halves: a corrected NAME is
    named, and every list whose money fields are invisible is reported as
    unverifiable rather than as clean.
    """
    tenant, _ = provisioned_tenant()

    def correct_a_name(payload):
        for entry in payload["meter_types"]:
            if entry["code"] == "ami":
                entry["name"] = "AMI (corrected)"

    staged_fixture(mutate=correct_a_name, version=NEXT)
    sweep()

    with tenant_ctx(tenant):
        held = {r.code: r.name for r in services.LOOKUP_LISTS["meter_types"].handler.search(None)}
    assert held["ami"] == "AMI", "BR-TEN-071: a sweep must never UPDATE a held row"
    out = capsys.readouterr().out
    assert "corrections NOT applied (OQ-086)" in out
    assert "meter_types/ami.name" in out
    assert "'AMI (corrected)'" in out and "'AMI'" in out
    # The invisible half, stated on every run rather than left to be assumed.
    assert "not checkable at all" in out
    assert "tax_jurisdictions" in out


# ── TC-7 (neg) · one tenant fails, the others keep their writes (BR-TEN-074) ─
def test_us_ten_020_tc7__failure_is_isolated_recorded_and_exits_2(
    growth_plan, identity_seam, audit_rows, pg_vendor, staged_fixture, monkeypatch
):
    """US-TEN-020 TC-7 — tenant 2 of 2 explodes: rolled back whole, named, exit 2.

    The failing tenant gets NO seed-run row for the bumped version and ONE
    `reference.sweep_failed` audit row carrying the exception CLASS and no PII;
    the healthy tenant keeps its writes; the command exits 2 (not 1 — a run that
    happened is not a run that was refused).
    """
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    staged_fixture(version=NEXT)

    real_seed = metering_services.seed_reference_list

    def explode_for_lonestar(list_code, entries, fixture_version):
        from core import tenancy as core_tenancy

        if core_tenancy.current_tenant_id() == lonestar.id:
            raise RuntimeError("metering seam crashed mid-sweep")
        return real_seed(list_code, entries, fixture_version)

    monkeypatch.setattr(metering_services, "seed_reference_list", explode_for_lonestar)

    with pytest.raises(CommandError) as caught:
        sweep()

    assert caught.value.returncode == 2
    assert "lonestarridge" in str(caught.value)
    assert seed_run_versions(brazos, "asset_types") == [SHIPPED, NEXT]
    assert seed_run_versions(lonestar, "asset_types") == [SHIPPED], "rollback was not whole"
    failures = [row for row in audit_rows if row["action"] == "reference.sweep_failed"]
    assert len(failures) == 1
    assert failures[0]["after"] == {
        "subdomain": "lonestarridge",
        "error": "RuntimeError",
    }, "BR-TEN-075: tenant + exception class only, no PII, no fixture payload"


# ── TC-8 (isolation) · every read and write under ONE tenant (BR-TEN-074) ───
@pytest.mark.isolation
@requires_postgres
def test_us_ten_020_tc8__sweep_is_per_tenant_and_rls_scoped(
    growth_plan, identity_seam, audit_rows, pg_vendor, rls
):
    """US-TEN-020 TC-8 — the ledger the sweep reads is RLS FORCE.

    Three proofs, because the app filter alone would be vacuous (the app's DB
    role is a superuser and bypasses RLS — see isolation_helpers):
      1. under Lone Star's `app.tenant_id`, the probe role sees ZERO of Brazos
         Bend's `reference_seed_runs` rows;
      2. with NO tenant context the table is denied outright (deny-by-default),
         which is what makes the per-tenant loop mandatory rather than tidy;
      3. sweeping Brazos Bend leaves Lone Star's ledger unchanged to the row.
    """
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    # Both reads take their own tenant's context. Contextless, every count here
    # is 0 (deny-by-default), so `lonestar_before` would be 0, the after-count
    # would be 0, and proof 3 — *"sweeping Brazos leaves Lone Star's ledger
    # unchanged"* — would hold over two empty numbers.
    with live_tenant_context(lonestar.id):
        lonestar_before = models.ReferenceSeedRun.objects.filter(tenant=lonestar).count()
    assert lonestar_before > 0, (
        "Lone Star has no seed-run ledger to leave unchanged — the comparison "
        "below would prove nothing"
    )

    with live_tenant_context(brazos.id):
        assert models.ReferenceSeedRun.objects.filter(tenant=brazos).exists()
    assert_rls_scoped(rls, "reference_seed_runs", owner=brazos, intruder=lonestar)
    assert_denied_without_context(rls, "reference_seed_runs")

    call_command("sweep_reference_data", tenant=["brazosbend"])

    with live_tenant_context(lonestar.id):
        assert models.ReferenceSeedRun.objects.filter(tenant=lonestar).count() == lonestar_before
    with live_tenant_context(lonestar.id):
        report = reference_sweep.behind_report_for_tenant(lonestar)
    assert report["subdomain"] == "lonestarridge"


# ── TC-9 (neg) · no audit sink ⇒ refused up front (CLAUDE.md rule 7) ────────
def test_us_ten_020_tc9__no_audit_sink_refuses_before_touching_a_tenant(
    growth_plan, identity_seam, audit_rows, pg_vendor, monkeypatch
):
    """US-TEN-020 TC-9 — a config write that cannot be audited must not happen."""
    tenant, _ = provisioned_tenant()
    ledger_before = models.ReferenceSeedRun.objects.count()
    from core import audit as core_audit

    monkeypatch.setattr(core_audit, "_sink", None)

    with pytest.raises(CommandError) as caught:
        sweep()

    assert caught.value.returncode == 1
    assert "audit sink" in str(caught.value)
    assert models.ReferenceSeedRun.objects.count() == ledger_before


# ── TC-10 (neg) · a non-Postgres vendor is refused up front ─────────────────
def test_us_ten_020_tc10__a_non_postgres_vendor_is_refused_naming_the_reason(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """US-TEN-020 TC-10 — refused up front, exit 1, naming the reason.

    The vendor is stubbed rather than inherited from the test tier so this TC
    asserts the same thing on BOTH tiers — on sqlite it would otherwise pass for
    free and on live Postgres it would fail for being right. The second assertion
    is what makes the stub honest: the name the guard reads is the REAL
    `django.db.connection`, so patching it here cannot make the guard read
    something the deployed command does not.
    """
    import django.db

    assert sweep_cmd.connection is django.db.connection
    provisioned_tenant()
    ledger_before = models.ReferenceSeedRun.objects.count()
    monkeypatch.setattr(sweep_cmd, "connection", SimpleNamespace(vendor="sqlite"))

    with pytest.raises(CommandError) as caught:
        sweep()

    assert caught.value.returncode == 1
    message = str(caught.value)
    assert "sqlite" in message and "Postgres GUC" in message
    assert models.ReferenceSeedRun.objects.count() == ledger_before


# ── TC-11 · "which tenants are behind" (BR-TEN-079) ─────────────────────────
def test_us_ten_020_tc11__report_distinguishes_behind_from_never_seeded(
    growth_plan, identity_seam, audit_rows, pg_vendor, staged_fixture, capsys
):
    """US-TEN-020 TC-11 — read-only, exit 0, three distinct states.

    `brazosbend` holds every list at 2026.08 and the fixture moves to V1.0.0.1, so
    it is BEHIND; its `charge_codes` row is removed to make one list NEVER
    SEEDED. The two must not render the same — that ambiguity is the whole
    reason BR-TEN-079 names three states rather than a boolean.
    """
    tenant, _ = provisioned_tenant()
    models.ReferenceSeedRun.objects.filter(tenant=tenant, list_code="charge_codes").delete()
    staged_fixture(version=NEXT)
    ledger_before = models.ReferenceSeedRun.objects.count()

    sweep(report=True)

    out = capsys.readouterr().out
    assert "NOT current" in out
    assert f"asset_types: behind ({SHIPPED} < {NEXT})" in out  # DEF-213
    assert "charge_codes: never seeded" in out
    assert models.ReferenceSeedRun.objects.count() == ledger_before, "--report wrote something"


# ── TC-12 (neg) · an UNEXPLAINED empty list exits 3 (DEF-016) ───────────────
def test_us_ten_020_tc12__unexplained_empty_list_exits_3_unless_named(
    growth_plan, identity_seam, audit_rows, pg_vendor, monkeypatch, capsys
):
    """US-TEN-020 TC-12 — exit 3, and the escape hatch is the one you type."""
    provisioned_tenant()
    # A registered handler that answers ZERO, with no row in the register: the
    # list is then empty-and-unexplained, which is exactly DEF-016's shape
    # (`charge_codes` was this for the whole of W0/W1). Asserted through a stub
    # rather than by deleting rows, because `uoms` is protected by FKs from
    # `tenant_services` — deleting them would test Django, not this rule.
    definition = services.LOOKUP_LISTS["uoms"]
    monkeypatch.setattr(
        definition, "handler", SimpleNamespace(count=lambda: 0, search=lambda q: [])
    )
    monkeypatch.setattr(services, "UNSEEDABLE_REFERENCE_LISTS", {})

    with pytest.raises(CommandError) as caught:
        sweep()
    assert caught.value.returncode == 3
    assert "brazosbend/uoms" in str(caught.value)

    sweep(allow_empty_reference_lists=True)  # named on the command line ⇒ exit 0
    assert "tolerated because --allow-empty-reference-lists" in capsys.readouterr().out


# ── TC-13 (neg) · discretionary lists are DEFERRED by name (OQ-088) ─────────
def test_us_ten_020_tc13__discretionary_lists_are_deferred_and_named(
    growth_plan, identity_seam, audit_rows, pg_vendor, staged_fixture, capsys
):
    """US-TEN-020 TC-13 — AMENDED: OQ-088 CLOSED 2026-08-10, so there is no stub.

    Ruling verbatim: *"persist the toggle first, then honour it… Until that
    column exists the sweep delivers STRUCTURAL lists only (BR-TEN-067), never
    discretionary ones — a tenant that asked for no charge codes must not receive
    them because a bump happened."* `tenants.reference_defaults_opted_in` does
    not exist, so every discretionary list is deferred and NAMED with OQ-216,
    the residue that ruling left (what value backfills the column for tenants
    provisioned before it exists).
    """
    tenant, _ = provisioned_tenant()
    # Wipe the discretionary ledger rows so "not delivered" cannot be confused
    # with "already current" — the sweep must decline them on the RULE, not
    # because they happen to be up to date.
    models.ReferenceSeedRun.objects.filter(tenant=tenant, list_code__in=DISCRETIONARY).delete()
    with tenant_ctx(tenant):
        uom_codes_before = sorted(
            models.Uom.objects.filter(tenant=tenant).values_list("code", flat=True)
        )
    staged_fixture(version=NEXT)

    sweep(allow_empty_reference_lists=True)

    for list_code in DISCRETIONARY:
        assert seed_run_versions(tenant, list_code) == [], (
            f"{list_code} was delivered to a tenant whose S111 answer is unknown — "
            "OQ-088 (PO 2026-08-10)"
        )
    with tenant_ctx(tenant):
        assert (
            sorted(models.Uom.objects.filter(tenant=tenant).values_list("code", flat=True))
            == uom_codes_before
        )
    out = capsys.readouterr().out
    assert "DEFERRED" in out
    assert "charge_codes" in out and "tax_jurisdictions" in out
    # The structural six still arrive, toggle or no toggle (BR-TEN-067).
    for list_code in STRUCTURAL:
        assert NEXT in seed_run_versions(tenant, list_code)


# ── TC-14 · no bill-run interlock (BR-TEN-078) ──────────────────────────────
def test_us_ten_020_tc14__sweep_cannot_change_an_in_flight_total(
    growth_plan, identity_seam, audit_rows, pg_vendor, staged_fixture
):
    """US-TEN-020 TC-14 — asserted mechanically rather than by running a bill.

    BR-TEN-078's argument has two legs and both are checkable here without
    billing: (1) the sweep issues no UPDATE, so no priced object changes under a
    run in flight — the swept lists' contents are byte-identical before and
    after; (2) under OQ-088 the sweep does not touch charge codes or tax
    jurisdictions AT ALL today, so the only money-bearing lists are not even
    candidates. A run in flight therefore cannot see a different total, and this
    stays true when the discretionary half is unblocked, because leg 1 does not
    depend on leg 2.
    """

    def money_list_codes():
        """The two money-bearing lists' contents, or None where no handler is
        registered. NOT a convenience: `tests/test_us_ten_009_011_lookups.py`
        legitimately unregisters `charge_codes`' handler and does not put it
        back, so a full-suite run reaches this TC with it absent. Leg 1 of the
        assertion then cannot be made, and saying so is better than the TC
        passing because it silently compared None to None."""
        out = {}
        for list_code in ("charge_codes", "tax_jurisdictions"):
            handler = services.LOOKUP_LISTS[list_code].handler
            out[list_code] = (
                None
                if handler is None
                else sorted(handler.serialize(r)["code"] for r in handler.search(None))
            )
        return out

    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        before = money_list_codes()
    staged_fixture(version=NEXT)

    sweep()

    with tenant_ctx(tenant):
        after = money_list_codes()
    # Leg 1 — nothing the sweep did changed a money-bearing list's contents.
    assert after == before
    # Leg 2 — and today those lists are not even candidates (OQ-088). This leg
    # needs no handler, so it holds on every ordering of the suite.
    assert NEXT not in seed_run_versions(tenant, "charge_codes")
    assert NEXT not in seed_run_versions(tenant, "tax_jurisdictions")


# ── TC-15 (neg) · production: the sweep RUNS, seed_demo refuses (BR-TEN-064) ─
def test_us_ten_020_tc15__runs_under_production_settings_where_seed_demo_refuses(
    growth_plan, identity_seam, audit_rows, pg_vendor, settings
):
    """US-TEN-020 TC-15 — two code paths, asserted separately.

    The split is BR-TEN-064's and DEF-026's lesson: a guard that fires where the
    work is needed means the ruling never executes. This command mints no tenant,
    user, credential or subscription, and production is the only host where the
    tenants that need it exist.
    """
    provisioned_tenant()
    settings.SETTINGS_MODULE = "config.settings.production"

    sweep(dry_run=True)  # runs — no refusal, no exception

    with pytest.raises(CommandError) as caught:
        call_command("seed_demo")
    assert "refuses under production settings" in str(caught.value)


# ── TC-16 · the BR-TEN-077 content guard ────────────────────────────────────
def test_us_ten_020_tc16__fixture_edited_without_a_bump_is_refused(
    growth_plan, identity_seam, audit_rows, pg_vendor, staged_fixture
):
    """US-TEN-020 TC-16 — the guard BR-TEN-077 demands, proved in both directions.

    A fixture edited without a version bump reaches NOBODY and looks like it
    worked: every tenant already has a seed-run row at that version, so the
    seeder skips every list. That is the failure this refuses, before any tenant
    is touched (exit 1), and the message names both digests so the fix is
    mechanical.
    """
    provisioned_tenant()

    def add_an_asset_type(payload):
        payload["asset_types"].append({"code": "sensor", "name": "Sensor"})

    staged_fixture(mutate=add_an_asset_type, pin=False)  # content moved, version did not

    with pytest.raises(CommandError) as caught:
        sweep()
    assert caught.value.returncode == 1
    message = str(caught.value)
    assert "BR-TEN-077" in message
    assert f"content changed but `version` is still '{SHIPPED}'" in message  # DEF-213

    # …and the same content WITH a bump and a recorded digest is accepted.
    staged_fixture(mutate=add_an_asset_type, version=NEXT)
    sweep()


# ── the version grammar and ordering (BR-TEN-077 / BR-TEN-079) ─────────────
def test_us_ten_020_tc16b__version_ordering_is_numeric_not_lexical():
    """CR-010 item 9 (PO 2026-08-17): the grammar is `V<a>.<b>.<c>.<d>`.

    Three ordering facts, each load-bearing:
      · V-versions increment numerically, so V1.0.0.9 < V1.0.0.10 — the
        `2026.9`-after-`2026.10` lexical trap, dead in the new grammar too.
      · EVERY legacy version sorts BELOW every V-version. Without the epoch
        element this is numerically backwards (1 < 2026), and a tenant seeded
        at 2026.08.x would read as AHEAD of V1.0.0.0 forever — the sweep would
        never deliver the new grammar to anybody.
      · Legacy spellings still ORDER (ledger rows carry them) but are REFUSED
        as the fixture's own declared version.
    """
    assert reference_sweep.version_key("V1.0.0.0") < reference_sweep.version_key("V1.0.0.1")
    assert reference_sweep.version_key("V1.0.0.9") < reference_sweep.version_key("V1.0.0.10")
    assert reference_sweep.version_key("V1.0.0.1") < reference_sweep.version_key("V1.0.1.0")
    assert reference_sweep.version_key("V1.9.0.0") < reference_sweep.version_key("V1.10.0.0")
    # every legacy version < every V-version — the epoch element's whole job
    assert reference_sweep.version_key("2026.08") < reference_sweep.version_key("V1.0.0.0")
    assert reference_sweep.version_key("2026.10.99") < reference_sweep.version_key("V1.0.0.0")
    # legacy still orders internally, for the behind-report over old rows
    assert reference_sweep.version_key("2026.08") < reference_sweep.version_key("2026.08.2")
    assert reference_sweep.version_key("2026.9") < reference_sweep.version_key("2026.10")
    # the fixture's own version speaks ONLY the new grammar
    assert reference_sweep.FIXTURE_VERSION_RE.match("V1.0.0.0")
    assert reference_sweep.FIXTURE_VERSION_RE.match("V2.14.7.3")
    assert not reference_sweep.FIXTURE_VERSION_RE.match("2026.08")
    assert not reference_sweep.FIXTURE_VERSION_RE.match("2026.08.2")
    assert not reference_sweep.FIXTURE_VERSION_RE.match("V1.0.0")
    assert not reference_sweep.FIXTURE_VERSION_RE.match("v1.0.0.0")
    assert reference_sweep.LEGACY_FIXTURE_VERSION_RE.match("2026.08.2")


def test_us_ten_020_tc16c__the_shipped_fixture_matches_its_declared_version():
    """The pin, asserted against the REAL file: if a lane edits
    `lookup_defaults.json` without bumping `version`, this goes red naming the
    digest to record. That is BR-TEN-077's "guard test" clause."""
    assert reference_sweep.assert_fixture_version_matches_content() == SHIPPED


# ── the plan read (BR-TEN-076) ──────────────────────────────────────────────
def test_us_ten_020_tc1b__plan_names_every_list_with_its_category_and_verb(
    growth_plan, identity_seam, audit_rows, staged_fixture
):
    """The dry-run's data, asserted directly: every declared list appears with a
    category and an action, so nothing can be quietly omitted from the plan."""
    tenant, _ = provisioned_tenant()
    staged_fixture(version=NEXT)
    with tenant_ctx(tenant):
        plan = reference_sweep.plan_for_tenant(tenant)

    assert plan["from_version"] == SHIPPED
    assert plan["to_version"] == NEXT
    by_code = {row["list"]: row for row in plan["lists"]}
    assert set(by_code) == {code for code, _ in services.SEED_LIST_OWNERS}
    for list_code in STRUCTURAL:
        assert by_code[list_code]["category"] == "structural"
        assert by_code[list_code]["action"] == reference_sweep.ACTION_SEED
    for list_code in DISCRETIONARY:
        assert by_code[list_code]["category"] == "discretionary"
        assert by_code[list_code]["action"] == reference_sweep.ACTION_DEFERRED
        assert reference_sweep.DISCRETIONARY_DEFERRAL_OQ in by_code[list_code]["detail"]
    # …and the PLATFORM list is neither, because the S111 toggle never governed
    # it: calling it discretionary would read as "the PO owes a ruling here".
    assert by_code["account_types"]["category"] == "platform"
    assert by_code["account_types"]["action"] == reference_sweep.ACTION_PLATFORM
    assert reference_sweep.DISCRETIONARY_DEFERRAL_OQ not in by_code["account_types"]["detail"]


def test_us_ten_020_tc1c__would_seed_is_exact_where_a_handler_exists(
    growth_plan, identity_seam, audit_rows, staged_fixture
):
    """`would_seed` is a real count where the owning module registered a lookup
    handler, and None — never 0 — where it did not. Reporting 0 for a list this
    process cannot count is the false claim `reference_data_report()` grew its
    `uncounted` state to avoid."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        for row in list(services.LOOKUP_LISTS["asset_types"].handler.search(None))[:3]:
            row.delete()
    staged_fixture(version=NEXT)
    with tenant_ctx(tenant):
        plan = reference_sweep.plan_for_tenant(tenant)

    by_code = {row["list"]: row for row in plan["lists"]}
    assert by_code["asset_types"]["would_seed"] == 3
    # `premises_types` HAS a handler since DEF-236's fix (2026-08-17), so the
    # answer this case exists for — exactness where a handler exists — now
    # covers it too: the tenant holds all six, so the plan owes zero. The
    # "unknown"/None state this block used to pin died with the fix; the
    # machinery for it stays for the next handler-less list.
    assert services.LOOKUP_LISTS["premises_types"].handler is not None
    assert by_code["premises_types"]["would_seed"] == 0


# ── the audit half (BR-TEN-075) ─────────────────────────────────────────────
def test_us_ten_020_tc7b__a_seeded_list_writes_the_existing_audit_action(
    growth_plan, identity_seam, audit_rows, pg_vendor, staged_fixture
):
    """BR-TEN-075: no NEW audit action for the seed half — the sweep writes the
    same `reference.seeded` row provisioning does, so one trail answers "where
    did this row come from" regardless of which path put it there."""
    tenant, _ = provisioned_tenant()
    forget_list(tenant, "premises_types", rows_model=PremisesType)
    audit_rows.clear()

    sweep()

    seeded = [row for row in audit_rows if row["action"] == "reference.seeded"]
    assert [row["after"]["list"] for row in seeded] == ["premises_types"]
    assert seeded[0]["after"]["fixture_version"] == SHIPPED
    assert "reference.swept" not in audit_actions(audit_rows)


def test_us_ten_020_tc7c__an_unresolvable_owner_yields_a_system_actor(
    growth_plan, identity_seam, audit_rows, monkeypatch
):
    """BR-TEN-075's fallback: `actor_user_id = NULL` (a system action) rather
    than an invented id or a foreign-key violation."""
    tenant, _ = provisioned_tenant()
    monkeypatch.setattr("apps.tenancy.seams.owner_email_for", lambda tenant_id: None, raising=False)
    actor = reference_sweep.owner_actor(tenant)
    assert actor.id is None and actor.pk is None


# ── the target selection (BR-TEN-074) ───────────────────────────────────────
def test_us_ten_020_tc11b__unknown_tenant_is_refused_naming_the_known_set(
    growth_plan, identity_seam, audit_rows, pg_vendor
):
    """An unknown `--tenant` is exit 1 — refused BEFORE anything is swept —
    naming what does exist, exactly as `seed_demo --tenant` already does."""
    provisioned_tenant()

    with pytest.raises(CommandError) as caught:
        sweep(tenant=["nosuchtenant"])

    assert caught.value.returncode == 1
    assert "nosuchtenant" in str(caught.value)
    assert "brazosbend" in str(caught.value)


def test_us_ten_020_tc11c__limit_caps_the_blast_radius(
    growth_plan, identity_seam, audit_rows, pg_vendor, staged_fixture
):
    """`--limit N` stops after N tenants — the same motive as --dry-run."""
    brazos, _ = provisioned_tenant(brazosbend_payload())
    lonestar, _ = provisioned_tenant(lonestarridge_payload())
    forget_list(brazos, "premises_types", rows_model=PremisesType)
    forget_list(lonestar, "premises_types", rows_model=PremisesType)

    sweep(limit=1, allow_empty_reference_lists=True)

    # Ordered by subdomain: brazosbend is swept, lonestarridge is not reached.
    assert seed_run_versions(lonestar, "premises_types") == []


def test_us_ten_020_tc1d__dry_run_and_report_are_not_the_same_report(
    growth_plan, identity_seam, audit_rows, pg_vendor
):
    """Two different reads; naming both is a mistake, not a combination."""
    provisioned_tenant()
    with pytest.raises(CommandError) as caught:
        sweep(dry_run=True, report=True)
    assert caught.value.returncode == 1


# ── the audit-log table itself, on the real sink (BR-TEN-075) ──────────────
def test_us_ten_020_tc7d__sweep_failure_row_reaches_the_audit_store(
    growth_plan, identity_seam, pg_vendor, staged_fixture, monkeypatch
):
    """The capture sink proves the CALL; this proves the ROW lands in
    `audit_log` through the real store, which is what an operator reads.

    The suite's autouse `audit_rows` fixture swaps the BE-03 sink for a list, so
    this TC puts the REAL store back for its own duration — otherwise it would
    assert an empty table and pass for the wrong reason."""
    from core import audit as core_audit

    tenant, _ = provisioned_tenant()
    monkeypatch.setattr(core_audit, "_sink", audit_services.store_row)
    staged_fixture(version=NEXT)

    def explode(list_code, entries, fixture_version):
        raise ValueError("seam blew up")

    monkeypatch.setattr(metering_services, "seed_reference_list", explode)

    with pytest.raises(CommandError):
        sweep()

    rows = AuditLog.objects.filter(tenant_id=tenant.id, action="reference.sweep_failed")
    assert rows.count() == 1
    assert rows.first().after == {"subdomain": "brazosbend", "error": "ValueError"}

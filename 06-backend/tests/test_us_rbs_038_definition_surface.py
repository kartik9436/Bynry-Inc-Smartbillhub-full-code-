# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-038 · US-RBS-040 (EP-RBS-01) — CR-075 wave E tasks E1, E2 and
#           E3, and wave D task D5. Screens: RBS-002 · RBS-003 · RBS-004.
# Rules:    BR-RBS-038 (every edit makes a new version; a run pins the version
#           that produced it; a change to a shipped template is OFFERED and
#           never applied without a person accepting it) · BR-RBS-036 (the trust
#           ratchet) · BR-RBS-043 (add once, then clone) · BR-RBS-024 clause 2 /
#           RB-050 (role visibility defaults from the category, widenable per
#           runbook) · BR-RBS-026 (Onboarding & Cutover sorts first while a plan
#           is open and last once it closes) · BR-RBS-001 (kind is immutable) ·
#           BR-RBS-002 (a Check is CONSTRUCTED with no writer) · NFR-5 (no hard
#           caps) · CLAUDE.md hard rule 1 (a cross-tenant write is a 404) ·
#           B14 rule 31 (no database id is the visible value of a field)
# Tests:    this file, on SQLite. The PostgreSQL half — the append-only trigger
#           and the cross-tenant write under the non-superuser probe role — is
#           06-backend/tests/test_us_rbs_038_pg.py, which SKIPS here rather than
#           passing vacuously (hard-won law 14).
# Impacts:  apps/runbooks/api.py · services.py · selectors.py · models.py ·
#           migrations/0003_cr075_wave_e_definition_surface.py
# ───────────────────────────────────────────────────────
"""US-RBS-038 — add, clone, edit, and the update that is offered and not applied.

**EVERY CASE HERE ASSERTS A RULE, NEVER AN IMPRESSION.** A 409 with its message
key, a refused clone, a version list that only ever grows, a run that still
reads v1 while the definition moves to v2, a template bump that changes NOTHING
on the copy until somebody presses accept, a Finance user who cannot see
Platform, and a cross-tenant write that answers the same 404 an absent runbook
does.

⚠ **THE CENTRAL CASE IS A NEGATIVE ONE AND IT IS WORTH SAYING WHY.**
`BR-RBS-038` says a template change is *offered, never applied*, so the test
that proves it is the one that **bumps the template, runs everything a person
would run, and asserts that nothing moved**. `DEF-RBS-4306` is what the opposite
test looks like: wave B's conformance suite asserted *running edited code twice
mints v2* as a PASS, so the check that should have caught the rule being
inverted had been written to require it.

⚠ **AND THE OTHER HALF OF THAT DEFECT IS ASSERTED AT THE SCREEN'S PAYLOAD, NOT
AT THE SERVICE.** `selectors.runbook_detail` used to read the REGISTRY first, so
a template bump silently changed what every tenant's setup screen drew. The case
below reads `definition.steps` off the payload and counts them, because that is
the number a clerk sees.
"""

from __future__ import annotations

import pytest
from django.urls import resolve

from apps.runbooks import api, models, selectors, services
from apps.runbooks.contract import MODE_SET, Block, RunbookDefinition, Step, SubjectRef
from apps.runbooks.registry import registry
from core import errors, permissions
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

TEMPLATE_KEY = "configuration_check"


# ── fixtures ─────────────────────────────────────────────────────────────────


def _subjects(ctx, **params):
    return [SubjectRef(subject_type="tenant", subject_id=str(ctx.tenant_id), label="This utility")]


def _report(ctx, outcome):
    return [Block(block="kpis", payload={"tiles": []})]


def _definition(**overrides) -> RunbookDefinition:
    """A stand-in shipped module: a Check with one set-mode step and no ports."""
    fields = dict(
        key="stand_in",
        name="Stand in",
        kind=models.KIND_CHECK,
        category="platform",
        subject_type="tenant",
        unit_of_work="config graph",
        resolve=_subjects,
        report=_report,
        steps=(
            Step(key="one", label="One", mode=MODE_SET, run=lambda ctx, subjects: "ok"),
        ),
    )
    fields.update(overrides)
    return RunbookDefinition(**fields)


def _runbook(tenant, **overrides) -> models.Runbook:
    fields = dict(
        key="stand_in",
        name="Stand in",
        kind=models.KIND_CHECK,
        category="platform",
        subject_type="tenant",
        unit_of_work="config graph",
        template_key="stand_in",
        cap=100,
        current_version=1,
        trusted_version=1,
    )
    fields.update(overrides)
    return models.Runbook.objects.create(tenant=tenant, **fields)


@pytest.fixture()
def registered(request):
    """Register a throwaway definition on the LIVE registry and take it out after.

    ⚠ **THE LIVE REGISTRY AND NOT A THROWAWAY ONE, DELIBERATELY.**
    `services.add_template`, `accept_template_update` and
    `selectors.pending_template_update` each reach `apps.runbooks.registry` by
    name — `G115` rule 3 permits a dynamic import only of a string literal
    beginning `apps.runbooks.`, so there is no seam to inject a registry
    through. A test that built its own would be testing a code path the product
    does not take.
    """
    added: list[str] = []

    def _register(definition: RunbookDefinition) -> RunbookDefinition:
        registry._by_key[definition.key] = definition
        added.append(definition.key)
        return definition

    yield _register
    for key in added:
        registry._by_key.pop(key, None)


def _call(view, method, tenant, actor, path, *, role=None, **kwargs):
    return api_call(
        view,
        method,
        f"/api/{tenant.subdomain}{path}",
        user=actor.user,
        role=role or permissions.SYSTEM_ADMIN,
        tenant=tenant,
        **kwargs,
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 — THE THREE WRITE ROUTES ARE MOUNTED, AND `clone` IS NOT A RUNBOOK KEY
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_038_the_write_routes_resolve_through_config_urls():
    """`G27`'s question for a write: a route nobody mounted is a route nobody wrote.

    Resolved through the ROOT URLconf, because the defect this guards against is
    a missing `include()` — which a module-local assertion cannot see. Compared
    by IDENTITY: `@api_view` gives every view in the product the name `view`, so
    a name comparison is vacuous (the D1 suite records finding that out).
    """
    assert resolve("/api/brazosbend/runbooks").func is api.runbooks_list
    assert resolve("/api/brazosbend/runbooks/dunning").func is api.runbook_detail
    assert resolve("/api/brazosbend/runbooks/dunning/clone").func is api.runbook_clone
    # And the three-segment clone path is not read as a runbook whose key is
    # `dunning/clone`, nor swallowed by the two-segment key pattern.
    assert resolve("/api/brazosbend/runbooks/dunning/clone").kwargs == {"key": "dunning"}


def test_us_rbs_038_the_read_routes_still_refuse_a_write_verb(brazos, dana):
    """`BR-RBS-002` at the door: only the three named addresses take a write.

    ⚠ **THIS CASE REPLACES `test_us_rbs_003_every_route_is_read_only`'s CLAIM
    ABOUT `runbooks_list`, AND THE REPLACEMENT IS NARROWER ON PURPOSE.** That
    case asserted *none of the eight accepts a write verb*, which was true in
    wave D and is now false for exactly two of them by `07-endpoints.md` rows 3
    and 5. Everything else must still refuse, and a suite that dropped the
    assertion instead of narrowing it would have stopped asking.
    """
    for view in (api.runbook_templates, api.runs_list, api.run_detail, api.run_records):
        response = api_call(
            view,
            "post",
            f"/api/{brazos.subdomain}/runbooks/runs",
            user=dana.user,
            role=permissions.SYSTEM_ADMIN,
            tenant=brazos,
            data={},
            run_id="00000000-0000-0000-0000-000000000000",
        )
        assert response.status_code == 405, f"{view} accepted a POST"


# ═══════════════════════════════════════════════════════════════════════════
# 2 — E1: ADD A TEMPLATE (`07-endpoints.md` row 5) · `BR-RBS-043`
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_038_e1_adding_a_template_writes_the_runbook_and_its_first_version(brazos, dana):
    """`POST /runbooks` → 201, `origin = shipped`, version 1, and NO cap.

    Four rules in one row, and the last one is the interesting one:
    `OQ-RBS-1731` is CLOSED at **100** and **wave `L4` carries the change**, so
    `cap` is still `None` here. A cap shipped from this wave would be `L4`'s work
    arriving from the wrong file and would make `L4` a no-op nobody notices.
    """
    with tenant_ctx(brazos):
        response = _call(
            api.runbooks_list,
            "post",
            brazos,
            dana,
            "/runbooks",
            data={"template_key": TEMPLATE_KEY},
        )
    assert response.status_code == 201, response.data
    body = response.data
    assert body["key"] == TEMPLATE_KEY
    assert body["name"] == "Can we bill?"
    assert body["origin"] == models.ORIGIN_SHIPPED
    assert body["template_key"] == TEMPLATE_KEY
    assert body["current_version"] == 1
    assert body["cap"] is None, "OQ-RBS-1731 ships 100 in wave L4, not here"

    row = models.Runbook.objects.get(tenant=brazos, key=TEMPLATE_KEY)
    versions = list(models.RunbookVersion.objects.filter(runbook=row).order_by("version"))
    assert [v.version for v in versions] == [1]
    assert versions[0].summary == [{"field": "origin", "to": "shipped"}]
    assert versions[0].changed_by_id == dana.user.id
    # `BR-RBS-036` — the ratchet is satisfied on day one: the rule restricts an
    # EDITED Action, and this definition is the one we shipped.
    assert row.trusted_version == row.current_version == 1
    assert body["dry_run_only"] is False


def test_us_rbs_038_e1_adding_the_same_template_twice_is_refused_by_name(brazos, dana):
    """`BR-RBS-043` — add once, then clone. A second add is a 409, not a 201.

    The library's whole state vocabulary is **Added · Not added**, so a second
    add is a stale screen or a double click. Answering `201` over the row that
    already existed would tell the caller something was created that was not.
    """
    with tenant_ctx(brazos):
        first = _call(
            api.runbooks_list, "post", brazos, dana, "/runbooks",
            data={"template_key": TEMPLATE_KEY},
        )
        assert first.status_code == 201
        second = _call(
            api.runbooks_list, "post", brazos, dana, "/runbooks",
            data={"template_key": TEMPLATE_KEY},
        )
    assert second.status_code == 409
    assert second.data["code"] == errors.BIZ_STATE
    assert second.data["message_key"] == "runbooks.refusal.already_added"
    assert second.data["br_ref"] == "BR-RBS-043"
    assert models.Runbook.objects.filter(tenant=brazos, template_key=TEMPLATE_KEY).count() == 1


def test_us_rbs_038_e1_an_unknown_template_key_is_refused_with_a_sentence(brazos, dana):
    """A key we do not ship answers 422 with a key the eleven catalogues hold.

    ⚠ **THE `message_key` IS THE ASSERTION, NOT THE STATUS.** PO ruling
    2026-08-19: a refusal's words come from the catalogue entry for its
    `message_key` and from nowhere else, so an unresolved key renders as
    **nothing at all** — the clerk presses Add and the click appears to do
    nothing. A status assertion passes over that silence.
    """
    with tenant_ctx(brazos):
        response = _call(
            api.runbooks_list, "post", brazos, dana, "/runbooks",
            data={"template_key": "no_such_template"},
        )
    assert response.status_code == 422
    assert response.data["message_key"] == "runbooks.refusal.unknown_template"


def test_us_rbs_038_e1_a_billing_clerk_may_read_the_catalogue_and_may_not_add(brazos, dana):
    """`07-endpoints.md` §1 — **Staff reads; Admin writes**, and the read is all three.

    ⚠ **BOTH HALVES, BECAUSE GETTING THE READ WRONG COSTS MORE THAN GETTING THE
    WRITE WRONG.** `DEF-SHL-4272`: a Billing Clerk could not use the product at
    all for sixteen days because a read was served under a class whose
    `allowed_roles` excluded them, and every test passed because they all asked
    about the write.
    """
    with tenant_ctx(brazos):
        read = _call(
            api.runbooks_list, "get", brazos, dana, "/runbooks",
            role=permissions.BILLING_CLERK,
        )
        write = _call(
            api.runbooks_list, "post", brazos, dana, "/runbooks",
            role=permissions.BILLING_CLERK, data={"template_key": TEMPLATE_KEY},
        )
    assert read.status_code == 200
    assert write.status_code == 403
    assert not models.Runbook.objects.filter(tenant=brazos).exists()


# ═══════════════════════════════════════════════════════════════════════════
# 3 — E1: CLONE AND VARY (`07-endpoints.md` row 6, `RB-040`)
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_038_e1_a_clone_gets_its_own_key_version_and_settings(brazos, dana):
    """Wave E's goal sentence: *both rows appear with their own schedule and cap.*

    And the half that is a fact about the SOURCE — *the previous run still reads
    v3 with its report unchanged* — is asserted here too: cloning writes nothing
    on the source at all.
    """
    with tenant_ctx(brazos):
        source = _runbook(brazos, key="dunning", name="Dunning", cap=250, template_key="dunning")
        services.ensure_version(source, _definition(key="dunning", name="Dunning"))
        run = models.RunbookRun.objects.create(
            tenant=brazos, runbook=source, version=source.current_version,
            status=models.RUN_STATUS_DONE, report=[{"block": "kpis", "payload": {"tiles": []}}],
        )
        before_report = list(run.report)

        response = _call(
            api.runbook_clone, "post", brazos, dana, "/runbooks/dunning/clone",
            data={"name": "Commercial accounts"}, key="dunning",
        )
    assert response.status_code == 201, response.data
    body = response.data
    assert body["key"] == "commercial-accounts"
    assert body["name"] == "Commercial accounts"
    assert body["origin"] == models.ORIGIN_CLONED
    assert body["current_version"] == 1
    assert body["cap"] == 250, "the copy carries the source's settings"
    assert body["enabled"] is False, "a clone arrives paused so it can be varied first"
    # The pointer to the CODE. Without it a clone is a runbook nothing can run:
    # its own key is new and the registry holds nothing under it.
    assert body["template_key"] == "dunning"

    copy = models.Runbook.objects.get(tenant=brazos, key="commercial-accounts")
    assert copy.cloned_from_id == source.pk
    assert models.RunbookRun.objects.filter(runbook=copy).count() == 0, "history is not copied"

    source.refresh_from_db()
    run.refresh_from_db()
    assert source.current_version == 1, "cloning writes nothing on the source"
    assert list(run.report) == before_report


def test_us_rbs_038_e1_two_clones_of_the_same_name_get_different_keys(brazos, dana):
    """The NAME is the person's and may repeat; the KEY is the address and may not.

    Refusing the second with *pick another name* would make the product argue
    about a field the person does not know exists.
    """
    with tenant_ctx(brazos):
        source = _runbook(brazos, key="dunning", name="Dunning", template_key="dunning")
        services.ensure_version(source, _definition(key="dunning", name="Dunning"))
        first = services.clone_runbook(source, name="Commercial accounts")
        second = services.clone_runbook(source, name="Commercial accounts")
    assert first.key == "commercial-accounts"
    assert second.key == "commercial-accounts-2"
    assert first.name == second.name == "Commercial accounts"


def test_us_rbs_038_e1_a_clone_of_another_tenants_runbook_is_the_same_404(brazos, lonestar, dana):
    """`HR-1` — a cross-tenant write and an absent one answer identically.

    The lookup is filtered by tenant before the key is looked at, so neither the
    status nor the body can be used to ask whether a runbook exists elsewhere in
    the product.
    """
    with tenant_ctx(lonestar):
        _runbook(lonestar, key="theirs", name="Theirs", template_key="theirs")
    with tenant_ctx(brazos):
        theirs = _call(
            api.runbook_clone, "post", brazos, dana, "/runbooks/theirs/clone",
            data={"name": "Mine"}, key="theirs",
        )
        absent = _call(
            api.runbook_clone, "post", brazos, dana, "/runbooks/nothing/clone",
            data={"name": "Mine"}, key="nothing",
        )
    assert theirs.status_code == absent.status_code == 404
    strip = lambda body: {k: v for k, v in body.items() if k != "trace_id"}  # noqa: E731
    assert strip(theirs.data) == strip(absent.data)
    assert not models.Runbook.objects.filter(tenant=brazos).exists()


# ═══════════════════════════════════════════════════════════════════════════
# 4 — E1/E2: THE EDIT WRITES A VERSION, AND THE VERSION LIST ONLY GROWS
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_038_e2_an_edit_writes_a_new_version_naming_what_moved(brazos, dana):
    """`07-endpoints.md` row 3 — *change schedule, cap, gate or enabled; writes a new version.*

    The summary is a list of FACTS and never a sentence: `RBS-004.7` draws *Cap
    raised to 400* and `[{"field": "cap", "from": 100, "to": 400}]` is what
    eleven catalogues can each say in their own language (B14 rule 35).
    `DEF-RBS-4285`'s engine half.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, cap=100)
        services.ensure_version(runbook, _definition())
        response = _call(
            api.runbook_detail, "put", brazos, dana, "/runbooks/stand_in",
            data={"cap": 400, "enabled": False}, key="stand_in",
        )
    assert response.status_code == 200, response.data
    assert response.data["cap"] == 400
    assert response.data["current_version"] == 2

    versions = list(models.RunbookVersion.objects.filter(runbook=runbook).order_by("version"))
    assert [v.version for v in versions] == [1, 2]
    moved = {change["field"]: change for change in versions[1].summary}
    assert moved["cap"] == {"field": "cap", "from": 100, "to": 400}
    assert moved["enabled"] == {"field": "enabled", "from": True, "to": False}
    assert versions[1].changed_by_id == dana.user.id
    # `runbook_versions` is APPEND-ONLY: v1's document is byte-identical to what
    # it was before the edit, and the settings it froze are the OLD ones.
    assert versions[0].definition["settings"]["cap"] == 100
    assert versions[1].definition["settings"]["cap"] == 400


def test_us_rbs_038_e2_an_edit_that_changes_nothing_writes_no_version(brazos, dana):
    """*Every EDIT makes a new version* — and setting the cap to what it already is edits nothing.

    A version per request turns the Activity tab into a log of who opened the
    settings sheet, which is the one screen an auditor asks for first.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, cap=100)
        services.ensure_version(runbook, _definition())
        response = _call(
            api.runbook_detail, "put", brazos, dana, "/runbooks/stand_in",
            data={"cap": 100}, key="stand_in",
        )
    assert response.status_code == 200
    assert models.RunbookVersion.objects.filter(runbook=runbook).count() == 1
    runbook.refresh_from_db()
    assert runbook.current_version == 1


@pytest.mark.parametrize(
    "body,status,message_key",
    [
        # `BR-RBS-001` — a Check that could become an Action would end
        # `BR-RBS-002`, which is the sentence that lets two people press Run ▶
        # on a thousand accounts.
        ({"kind": "action"}, 409, "runbooks.refusal.not_editable"),
        ({"key": "something-else"}, 409, "runbooks.refusal.not_editable"),
        ({"origin": "cloned"}, 409, "runbooks.refusal.not_editable"),
        # An unknown field name is a caller bug, not a clerk's refusal.
        ({"colour": "blue"}, 422, "errors.val-005"),
        # A cap of zero is not a limit — it is a runbook that can never run.
        ({"cap": 0}, 422, "errors.val-003"),
        ({"gate_mode": "whenever"}, 422, "errors.val-005"),
        ({"visible_to_roles": ["wizard"]}, 422, "errors.val-005"),
    ],
)
def test_us_rbs_038_e2_a_frozen_or_unknown_field_is_refused_rather_than_ignored(
    brazos, dana, body, status, message_key
):
    """Silently dropping either leaves the caller believing the change landed.

    That is the failure this repository keeps paying for, and it is why the
    frozen fields are refused **by name** rather than filtered out.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, cap=100)
        services.ensure_version(runbook, _definition())
        response = _call(
            api.runbook_detail, "put", brazos, dana, "/runbooks/stand_in",
            data=body, key="stand_in",
        )
    assert response.status_code == status, response.data
    assert response.data["message_key"] == message_key
    runbook.refresh_from_db()
    assert runbook.current_version == 1, "a refused edit writes no version"
    assert runbook.kind == models.KIND_CHECK


def test_us_rbs_038_nfr5_a_cap_has_no_ceiling(brazos, dana):
    """`NFR-5` — no hard caps anywhere, and CLAUDE.md makes that the deliverable.

    A ceiling typed into the validator would be exactly the *account maximum
    that would have to be removed when T4 arrives* the instruction forbids. Half
    a million is refused by nothing.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, cap=100)
        services.ensure_version(runbook, _definition())
        response = _call(
            api.runbook_detail, "put", brazos, dana, "/runbooks/stand_in",
            data={"cap": 500_000}, key="stand_in",
        )
    assert response.status_code == 200
    assert response.data["cap"] == 500_000


# ═══════════════════════════════════════════════════════════════════════════
# 5 — E2: THE TRUST RATCHET (`BR-RBS-036`)
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_038_e2_an_edited_action_is_dry_run_only_and_a_check_never_is(brazos, dana):
    """`BR-RBS-036` — *an edited Action drops back to dry-run only.*

    Three assertions, and the third is what keeps the rule from being a blanket
    stop: a **Check** is never held, whatever its version numbers say, because
    it writes nothing in either mode (`BR-RBS-002`).

    ⚠ **THE REFUSAL IS AT `open_run` AND NOT AT AN HTTP ROUTE.**
    `POST /runbooks/{key}/runs` is wave `L`; a rule enforced only there would be
    a rule enforced nowhere for a whole phase. Every run in the product goes
    through this function, so wave `L` inherits it by calling it.
    """
    definition = _definition()
    action_definition = _definition(key="ladder", name="Ladder", kind=models.KIND_ACTION)
    with tenant_ctx(brazos):
        action = _runbook(brazos, key="ladder", name="Ladder", kind=models.KIND_ACTION,
                          template_key="ladder")
        services.ensure_version(action, action_definition)
        # Unedited: the shipped definition is the one WE reviewed, so live runs.
        assert services.open_run(action, action_definition, mode=models.MODE_LIVE).mode == "live"

        services.update_runbook(action, {"cap": 400}, actor_id=dana.user.id)
        action.refresh_from_db()
        assert action.trusted_version == 1 and action.current_version == 2

        with pytest.raises(errors.BizError) as refused:
            services.open_run(action, action_definition, mode=models.MODE_LIVE)
        assert refused.value.message_key == "runbooks.refusal.dry_run_first"
        assert refused.value.br_ref == "BR-RBS-036"
        # *Dry-run only* means dry-run ALLOWED — not stopped.
        assert services.open_run(action, action_definition, mode=models.MODE_DRY).mode == "dry"

        check = _runbook(brazos)
        services.ensure_version(check, definition)
        services.update_runbook(check, {"cap": 400}, actor_id=dana.user.id)
        check.refresh_from_db()
        assert services.open_run(check, definition, mode=models.MODE_LIVE).mode == "live"


def test_us_rbs_038_e2_the_setup_payload_states_the_ratchet_as_a_fact(brazos, dana):
    """`RBS-004.5` needs *this runs dry until a clean dry run is reviewed* as data.

    A screen that had to compare `trusted_version` with `current_version` itself
    would be a second place the rule lives, and the two would eventually
    disagree.
    """
    with tenant_ctx(brazos):
        action = _runbook(brazos, key="ladder", name="Ladder", kind=models.KIND_ACTION,
                          template_key="ladder")
        services.ensure_version(action, _definition(key="ladder", name="Ladder",
                                                    kind=models.KIND_ACTION))
        assert selectors.runbook_detail(brazos.pk, "ladder")["dry_run_only"] is False
        services.update_runbook(action, {"cap": 400}, actor_id=dana.user.id)
        assert selectors.runbook_detail(brazos.pk, "ladder")["dry_run_only"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 6 — E3: A TEMPLATE UPDATE IS OFFERED AND CHANGES NOTHING UNTIL PRESSED
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_038_e3_a_template_bump_changes_nothing_on_the_copy_until_accepted(
    brazos, dana, registered
):
    """`BR-RBS-038` · `E5`'s `TC-RBS-24` — *the copy's steps unchanged after a template bump.*

    ⚠ **THIS IS THE NEGATIVE CASE `DEF-RBS-4306` EXISTS FOR.** The old behaviour
    minted a version and pinned it at the next run — our edit reaching every
    tenant with nobody asked. So the assertion is that after the bump, and after
    everything a person would do short of pressing accept, **nothing moved**:
    the version is still 1, the stored steps are still 1, and the payload the
    setup screen draws still says 1.
    """
    registered(_definition())
    with tenant_ctx(brazos):
        runbook = services.add_template(brazos.pk, "stand_in", actor_id=dana.user.id)
        assert runbook.current_version == 1
        assert selectors.runbook_detail(brazos.pk, "stand_in")["template_update"] is None

        # We ship a second step.
        registered(
            _definition(
                steps=(
                    Step(key="one", label="One", mode=MODE_SET, run=lambda ctx, s: "ok"),
                    Step(key="two", label="Two", mode=MODE_SET, run=lambda ctx, s: "ok"),
                )
            )
        )
        payload = selectors.runbook_detail(brazos.pk, "stand_in")

    offer = payload["template_update"]
    assert offer is not None, "the bump must be OFFERED"
    assert offer["available"] is True
    assert offer["steps_added"] == 1, "the screen says 'Template updated · 1 new step · Review →'"
    assert offer["steps_removed"] == 0
    assert offer["other_changed"] is False

    # NOTHING MOVED. Not the version, not the stored document, and not the
    # number of steps the setup screen draws.
    assert payload["current_version"] == 1
    assert len(payload["definition"]["steps"]) == 1
    assert models.RunbookVersion.objects.filter(runbook__key="stand_in").count() == 1


def test_us_rbs_038_e3_accepting_the_offer_is_the_only_thing_that_applies_it(
    brazos, dana, registered
):
    """*Changing nothing until pressed* — and pressing keeps the tenant's settings.

    Accepting *1 new step* must not reset a cap somebody raised to 400, which is
    the whole reason a version document holds the shipped half and the tenant
    half separately.
    """
    registered(_definition())
    with tenant_ctx(brazos):
        services.add_template(brazos.pk, "stand_in", actor_id=dana.user.id)
        _call(api.runbook_detail, "put", brazos, dana, "/runbooks/stand_in",
              data={"cap": 400}, key="stand_in")
        registered(
            _definition(
                steps=(
                    Step(key="one", label="One", mode=MODE_SET, run=lambda ctx, s: "ok"),
                    Step(key="two", label="Two", mode=MODE_SET, run=lambda ctx, s: "ok"),
                )
            )
        )
        response = _call(
            api.runbook_detail, "put", brazos, dana, "/runbooks/stand_in",
            data={"accept_template_update": True}, key="stand_in",
        )
    assert response.status_code == 200, response.data
    assert response.data["template_update"] is None, "the offer is gone once taken"
    assert len(response.data["definition"]["steps"]) == 2
    assert response.data["cap"] == 400, "accepting our change keeps their settings"
    assert response.data["current_version"] == 3  # v1 add · v2 the cap · v3 the acceptance


def test_us_rbs_038_e3_accepting_when_there_is_nothing_on_offer_is_a_no_op(
    brazos, dana, registered
):
    """A double click is not an error a clerk should be shown.

    Idempotent rather than a refusal: accepting an update that has already been
    accepted returns the runbook unchanged and writes no version.
    """
    registered(_definition())
    with tenant_ctx(brazos):
        services.add_template(brazos.pk, "stand_in", actor_id=dana.user.id)
        response = _call(
            api.runbook_detail, "put", brazos, dana, "/runbooks/stand_in",
            data={"accept_template_update": True}, key="stand_in",
        )
    assert response.status_code == 200
    assert response.data["current_version"] == 1
    assert models.RunbookVersion.objects.filter(runbook__key="stand_in").count() == 1


def test_us_rbs_038_e3_a_run_is_refused_while_an_update_is_pending(brazos, dana, registered):
    """Pinning v1 while the executor walks v2's steps is a lie in the audit record.

    ⚠ **THERE IS NO THIRD HONEST OPTION AND THAT IS WORTH SAYING.** The steps are
    Python, so *run the old steps* is not something this engine can do. Either
    the run stops or the version on the report did not produce it. It stops, in
    five words a clerk can act on, and the act is the *Review →* the setup screen
    already draws over the same fact.
    """
    registered(_definition())
    with tenant_ctx(brazos):
        runbook = services.add_template(brazos.pk, "stand_in", actor_id=dana.user.id)
        bumped = _definition(
            steps=(
                Step(key="one", label="One", mode=MODE_SET, run=lambda ctx, s: "ok"),
                Step(key="two", label="Two", mode=MODE_SET, run=lambda ctx, s: "ok"),
            )
        )
        registered(bumped)
        with pytest.raises(errors.BizError) as refused:
            services.open_run(runbook, bumped)
        assert refused.value.message_key == "runbooks.refusal.update_pending"
        assert refused.value.br_ref == "BR-RBS-038"
        assert models.RunbookRun.objects.filter(runbook=runbook).count() == 0

        # Accept, and the same call goes through.
        services.accept_template_update(runbook, actor_id=dana.user.id)
        runbook.refresh_from_db()
        assert services.open_run(runbook, bumped).version == runbook.current_version


def test_us_rbs_038_e5_a_past_run_keeps_its_version_and_its_report_byte_for_byte(brazos, dana):
    """`TC-RBS-13` — *the old run still reads v1 and its report is unchanged.*

    Wave E's goal sentence ends *and the previous run still reads v3 with its
    report unchanged*. Asserted by comparing the stored report to a copy taken
    before the edit, rather than by re-reading it twice — two reads of a value
    nothing touched agree even when the rule is broken.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, cap=100)
        services.ensure_version(runbook, _definition())
        run = models.RunbookRun.objects.create(
            tenant=brazos, runbook=runbook, version=runbook.current_version,
            status=models.RUN_STATUS_DONE,
            report=[{"block": "verdict", "payload": {"word": "Go", "tone": "good"}}],
        )
        frozen = list(run.report)
        services.update_runbook(runbook, {"cap": 400}, actor_id=dana.user.id)
        services.update_runbook(runbook, {"enabled": False}, actor_id=dana.user.id)
        runbook.refresh_from_db()
        run.refresh_from_db()
    assert runbook.current_version == 3
    assert run.version == 1
    assert list(run.report) == frozen


def test_us_rbs_038_e2_the_activity_tab_reads_newest_first_and_draws_no_database_id(brazos, dana):
    """`RBS-004.7` — the tab an auditor asks for first (`DEF-RBS-4285`'s engine half).

    B14 rule 31: no database id is ever the visible value of a field. The `id`
    on an activity row is the version NUMBER, which
    `08-screen-layouts.md`'s own escape clause allows (*`4` renders as `v4`*),
    and the row's uuid is not on the payload at all — a field that does not
    exist cannot be rendered by accident.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, cap=100)
        services.ensure_version(runbook, _definition())
        services.update_runbook(runbook, {"cap": 400}, actor_id=dana.user.id)
        activity = selectors.runbook_detail(brazos.pk, "stand_in")["activity"]
    assert [row["version"] for row in activity] == [2, 1]
    assert activity[0]["changes"] == [{"field": "cap", "from": 100, "to": 400}]
    assert activity[0]["actor"] == {"name": dana.user.full_name}
    assert activity[1]["actor"] is None, "the bootstrap version was written by the code"
    for row in activity:
        assert row["id"] == row["version"]
        assert set(row) == {"id", "version", "changes", "actor", "when"}


# ═══════════════════════════════════════════════════════════════════════════
# 7 — D5: ROLE VISIBILITY FROM THE CATEGORY (`RB-050`, `BR-RBS-024` clause 2)
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_038_d5_the_role_codes_match_the_a4_matrix():
    """`models.VISIBILITY_ROLES` is `A4`'s ratified three and cannot drift from them.

    Held as a literal in `models.py` rather than imported from
    `core.permissions`, for the reason `api.py`'s `CsvRenderer` gives about a
    four-line cross-module import — so the two are asserted against each other
    here, which is the check that makes the duplication safe.
    """
    assert set(models.VISIBILITY_ROLES) == set(permissions.ROLES)


def test_us_rbs_038_d5_a_finance_user_sees_finance_payments_and_collections_not_platform(brazos):
    """`07-endpoints.md`'s own worked example, asserted as a sentence about roles.

    *A Finance user's Templates page shows Finance, Payments and Collections
    runbooks and not Platform.* Read `executive` down
    `ROLE_VISIBILITY_BY_CATEGORY` and that is exactly what comes back —
    asserted against the SENTENCE rather than against the dict, so a lane that
    edits the dict meets a red naming the example it broke.
    """
    seen = {
        category
        for category in models.CATEGORIES
        if permissions.EXECUTIVE in models.roles_that_see(category)
    }
    assert {"finance", "payments", "collections"} <= seen
    assert "platform" not in seen
    assert "onboarding_cutover" not in seen
    # And *Owner and Admin see every runbook* is the fixed half of the sentence.
    for category in models.CATEGORIES:
        assert permissions.SYSTEM_ADMIN in models.roles_that_see(category)


def test_us_rbs_038_d5_the_catalogue_is_narrowed_by_role_and_widened_per_runbook(brazos):
    """A filter on what a reader is SHOWN, and an admin's override that widens it.

    ⚠ **THE OVERRIDE HOLDS THE WHOLE ANSWER RATHER THAN A DELTA**, so a later
    change to a category's default cannot silently re-widen a runbook somebody
    deliberately narrowed.
    """
    with tenant_ctx(brazos):
        _runbook(brazos, key="platform_one", name="Platform one", category="platform")
        _runbook(brazos, key="reads_one", name="Reads one", category="reads")
        _runbook(brazos, key="finance_one", name="Finance one", category="finance")

        def keys(role):
            page = selectors.catalogue_page(brazos.pk, role=role)
            return {row["key"] for row in page["rows"]}

        assert keys(permissions.SYSTEM_ADMIN) == {"platform_one", "reads_one", "finance_one"}
        assert keys(permissions.BILLING_CLERK) == {"reads_one"}
        assert keys(permissions.EXECUTIVE) == {"finance_one"}

        # An admin widens ONE platform runbook to the clerk.
        models.Runbook.objects.filter(tenant=brazos, key="platform_one").update(
            visible_to_roles=["billing_clerk"]
        )
        assert keys(permissions.BILLING_CLERK) == {"reads_one", "platform_one"}
        # …and narrowing cannot hide it from the person who has to fix it.
        models.Runbook.objects.filter(tenant=brazos, key="finance_one").update(
            visible_to_roles=[]
        )
        assert "finance_one" in keys(permissions.SYSTEM_ADMIN)
        assert keys(permissions.EXECUTIVE) == set()


def test_us_rbs_038_the_override_is_stored_normalised(brazos, dana):
    """Sorted and de-duplicated on the way in — and the role filter depends on it.

    ⚠ **THIS CASE IS LOAD-BEARING RATHER THAN TIDY.** `selectors._visible_to`
    matches an override by EXACT LIST, because Django's `JSONField` `contains`
    lookup is PostgreSQL-only and answers 500 on the SQLite test database. That
    enumeration is only correct while every stored value is a sorted,
    de-duplicated subset of the three role codes, which is what this asserts. A
    lane that "simplified" the normalisation away would leave a filter that
    silently stops matching — a runbook widened to a clerk would just quietly
    stop appearing for them, with nothing red anywhere.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        services.ensure_version(runbook, _definition())
        response = _call(
            api.runbook_detail, "put", brazos, dana, "/runbooks/stand_in",
            data={"visible_to_roles": ["executive", "billing_clerk", "executive"]},
            key="stand_in",
        )
    assert response.status_code == 200, response.data
    runbook.refresh_from_db()
    assert runbook.visible_to_roles == ["billing_clerk", "executive"]
    # And the resolved answer always carries the admin, whatever was stored.
    assert response.data["roles"] == ["system_admin", "billing_clerk", "executive"]


def test_us_rbs_038_d5_a_chip_is_never_offered_over_an_empty_list(brazos):
    """`BR-RBS-025` and hard-won law 2, arriving from a second direction.

    `TC-RBS-20` covers a chip row built from the fixed sixteen. This is the
    other way to draw a dead chip: build it from every template we SHIP and
    serve it to a reader who cannot see half of them.

    ⚠ **THE FIRST DRAFT OF THIS CASE ASSERTED A FINANCE USER SEES *ZERO*
    TEMPLATES, AND IT WENT RED WITHIN THE HOUR — MY OWN BRITTLENESS, AND THE
    SAME ONE `TC-RBS-20` HAD.** It was true when written: the library held one
    Platform runbook, so an Executive saw nothing. Wave P then shipped cash
    application and bank reconciliation and `US-RBS-042` shipped the accounting
    export — Payments and Finance, all three of which an Executive is SUPPOSED
    to see — and the assertion failed on the product working. **A number that
    counts how many runbooks we have written so far is not a rule**, and a check
    that goes red when a colleague ships something is a check the next lane
    learns to skip past.

    So the rule is what is asserted, and it holds at one template or fifty:
    every row a Finance user is served is in a category their role sees, every
    chip they are offered filters to at least one of those rows, Platform is in
    neither, and what they see is a SUBSET of what an admin sees.
    """
    with tenant_ctx(brazos):
        admin = selectors.templates_page(brazos.pk, role=permissions.SYSTEM_ADMIN)
        finance = selectors.templates_page(brazos.pk, role=permissions.EXECUTIVE)
    admin_chips = {chip["category"] for chip in admin["category_chips"]}
    finance_chips = {chip["category"] for chip in finance["category_chips"]}

    assert "platform" in admin_chips, "the fixture needs at least one runbook a clerk cannot see"
    assert "platform" not in finance_chips, "a chip that filters to nothing is dead UI"
    assert finance_chips <= admin_chips
    assert finance["total"] == len(finance["rows"])
    assert finance["total"] <= admin["total"]

    # Every ROW a Finance user gets is one their role is shown — the chips and
    # the page cannot disagree about who sees what.
    for row in finance["rows"]:
        assert permissions.EXECUTIVE in models.roles_that_see(row["category"]), row["template_key"]
        assert row["category"] != "platform"
    # …and every chip they are offered filters to at least one of those rows.
    served = {row["category"] for row in finance["rows"]}
    for chip in finance["category_chips"]:
        assert chip["count"] > 0, "a chip that filters to nothing is dead UI"
        assert chip["category"] in served or finance["total"] == 0


def test_us_rbs_038_d5_onboarding_and_cutover_sorts_first_while_a_plan_is_open(
    brazos, registered
):
    """`BR-RBS-026` — first while a cutover plan is open, **last once it closes**.

    *No other category carries an order rule*, and this is the one list in the
    product that re-orders itself on the state of a different table. Both
    directions are asserted: a rule that only ever moved something to the top
    would pass a test that checked one of them.
    """
    registered(_definition(key="a_platform", name="A platform", category="platform"))
    registered(
        _definition(key="z_cutover", name="Z cutover", category="onboarding_cutover")
    )
    with tenant_ctx(brazos):
        # No plan at all — closed behaviour: cutover sorts last.
        rows = selectors.templates_page(brazos.pk)["rows"]
        assert [row["template_key"] for row in rows][-1] == "z_cutover"

        plan = models.CutoverPlan.objects.create(tenant=brazos, name="Go live", status="open")
        rows = selectors.templates_page(brazos.pk)["rows"]
        assert [row["template_key"] for row in rows][0] == "z_cutover"

        models.CutoverPlan.objects.filter(pk=plan.pk).update(status="closed")
        rows = selectors.templates_page(brazos.pk)["rows"]
        assert [row["template_key"] for row in rows][-1] == "z_cutover"


def test_us_rbs_038_d5_the_added_state_reads_the_shipped_copy_and_not_a_clone(
    brazos, dana, registered
):
    """A tenant that has only ever CLONED must still see **Add** on the template.

    `services.clone_runbook` copies `template_key` onto the copy because that
    pointer is the only thing that finds the copy's code. A library filtering on
    `template_key` alone would answer *Added* for a template they never added,
    and the Add button would vanish.
    """
    registered(_definition())
    with tenant_ctx(brazos):
        added = services.add_template(brazos.pk, "stand_in", actor_id=dana.user.id)
        clone = services.clone_runbook(added, name="A copy", actor_id=dana.user.id)
        assert clone.template_key == "stand_in"
        added.delete()

        state = {
            row["template_key"]: row["state"]
            for row in selectors.templates_page(brazos.pk)["rows"]
        }
    assert state["stand_in"] == "not_added"
    assert selectors.runbook_by_template(brazos.pk, "stand_in") is None


# ═══════════════════════════════════════════════════════════════════════════
# 8 — THE VERSION DOCUMENT'S TWO HALVES
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_038_a_version_document_holds_the_shipped_half_and_the_tenant_half(brazos, dana):
    """`03-field-map.md` §2 — *the whole seven-part object … gate, cap …*

    The shipped half is the definition's; the tenant half is under `settings`.
    The split is what lets *we changed the steps* and *you raised your cap* be
    told apart, and a document written before the key existed still compares
    equal because every comparison strips it.
    """
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, cap=100)
        version = services.ensure_version(runbook, _definition())
    document = version.definition
    assert document["settings"]["cap"] == 100
    assert document["settings"]["gate_mode"] == models.GATE_APPROVE_EACH_RUN
    assert [step["key"] for step in document["steps"]] == ["one"]
    # Stripping the key gives back exactly the shipped definition document.
    assert services.shipped_half(document) == _definition().as_definition_document()
    # And a legacy document with no `settings` key survives the strip unchanged.
    legacy = {"key": "stand_in", "steps": []}
    assert services.shipped_half(legacy) == legacy


def test_us_rbs_038_the_gate_vocabulary_is_br_rbs_041s_two_values(brazos, dana):
    """`BR-RBS-041` — permission granted up front, per runbook, and nothing else.

    ⚠ **THE THREE-CLEAN-RUN RATCHET WAS RECOMMENDED AND NOT TAKEN**, so a third
    value here would be a new ruling rather than this one. Asserted as a count so
    a lane adding one meets a red.
    """
    assert models.GATE_MODES == ("approve_each_run", "approved_up_front")
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        services.ensure_version(runbook, _definition())
        response = _call(
            api.runbook_detail, "put", brazos, dana, "/runbooks/stand_in",
            data={"gate_mode": "approved_up_front"}, key="stand_in",
        )
    assert response.status_code == 200
    assert response.data["gate_mode"] == "approved_up_front"


def test_us_rbs_038_nothing_in_this_wave_composes_an_idempotency_key():
    """`OQ-RBS-1737` is OPEN — and the cost of guessing is 496 notices, not 248.

    ⚠ **A GREP IS THE ONLY CHECK THAT CAN ASK THIS QUESTION**, because the defect
    is the ABSENCE of a rule: nothing goes red when a key is composed, it simply
    starts being wrong. So the assertion is that the three files this wave
    touched write no `runbook_run_records` row and mint no key.
    """
    import inspect

    for module in (services, selectors, api):
        source = inspect.getsource(module)
        assert "idempotency_key=" not in source, f"{module.__name__} composes a key"
        assert "RunbookRunRecord.objects.create" not in source


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-038 · US-RBS-040 (EP-RBS-01; CR-075 wave E tasks E1·E2·E3 + wave D task D5)
# generated: 2026-09-06 by the CR-075 wave E build lane
# checklist: A✔ B✔ C✔ D✔(three write routes, resolved through config/urls.py) E=deferred(no-frontend-half — RBS-002/003/004 are three sibling lanes'; DEF-RBS-4308 records the mapper they owe) F✔ G✔ H=n/a(no 🔒 path — no idempotency key, no rating math, no ledger line)
# gates: pytest tests/test_us_rbs_038_definition_surface.py · tests/test_us_rbs_038_pg.py (PostgreSQL) · G6 · G9 · G15 · G32 · G114 · G115
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

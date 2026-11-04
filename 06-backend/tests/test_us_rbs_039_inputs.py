# ── Trace ──────────────────────────────────────────────
# Story:    US-RBS-039 (EP-RBS-05) — CR-075 wave T. Screens: RBS-004.3.
# Rules:    BR-RBS-042 (a runbook is one fixed process with declared inputs; a
#           DOMAIN per input, resolved PER TENANT; one value, several, or *all*;
#           *all* stored as the WORD and resolved at run start) · BR-RBS-009
#           (scope resolved once and pinned) · BR-RBS-036 (an edited Action is
#           dry-run only until one clean dry run is reviewed) · BR-RBS-038
#           (every edit makes a new version) · NFR-3 (server pagination) ·
#           NFR-5 (no hard caps) · B14 rule 31 (no database id is the visible
#           value of a field)
# Cases:    TC-RBS-039.1 · .2 · .3 · .4 · .5
# Impacts:  apps/runbooks/domains.py · contract.py · services.py · selectors.py
#           · api.py · migrations/0004_cr075_wave_t_parameter_values.py
# ───────────────────────────────────────────────────────
"""US-RBS-039 — the inputs a utility sets, and the word *all* that is a rule.

**THE CASE THIS WHOLE FILE EXISTS FOR IS `TC-RBS-039.1`**, and it is a test
about the FUTURE rather than about today: a utility sets *services = all* while
it sells two, enables a third next month, and the next run must cover **three**.
The failing version of this feature passes every other test in this file — it
expands the word at configure time, which is correct in every observable way
until the day a service is added, and then it silently drops that service out of
every runbook set to *all* with nothing on any screen to see.

⚠ **`TC-RBS-039.5` IS THE NEGATIVE ONE AND IT IS DELIBERATELY BLUNT.** PO ruling
2026-09-06: a tenant sets input VALUES and nothing else — no step list, no
filter builder, no condition syntax. It is asserted as an absence at the edit
route, because that is the only door a tenant's change comes through.
"""

from __future__ import annotations

import pytest

from apps.runbooks import api, contract, domains, models, selectors, services
from apps.runbooks.contract import (
    DOMAIN_ACCOUNT,
    DOMAIN_SERVICE,
    MODE_SET,
    PARAM_ALL,
    PARAM_ENUM,
    PARAM_MONEY,
    Block,
    Parameter,
    RunbookDefinition,
    RunbookContractError,
    Step,
    SubjectRef,
)
from apps.runbooks.registry import registry
from core import errors, permissions
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


# ── fixtures ─────────────────────────────────────────────────────────────────


def _subjects(ctx, **params):
    return [SubjectRef(subject_type="tenant", subject_id=str(ctx.tenant_id), label="This utility")]


def _report(ctx, outcome):
    return [Block(block="kpis", payload={"tiles": []})]


def _definition(**overrides) -> RunbookDefinition:
    fields = dict(
        key="input_stand_in",
        name="Input stand in",
        kind=models.KIND_CHECK,
        category="platform",
        subject_type="tenant",
        unit_of_work="config graph",
        resolve=_subjects,
        report=_report,
        parameters=(
            Parameter(
                name="services",
                type=PARAM_ENUM,
                label="Services",
                default=PARAM_ALL,
                multi=True,
                domain=DOMAIN_SERVICE,
            ),
            Parameter(
                name="past_due_more_than",
                type=PARAM_MONEY,
                label="Past due more than",
                default="5.0000",
            ),
        ),
        steps=(Step(key="one", label="One", mode=MODE_SET, run=lambda ctx, subjects: "ok"),),
    )
    fields.update(overrides)
    return RunbookDefinition(**fields)


def _runbook(tenant, **overrides) -> models.Runbook:
    fields = dict(
        key="input_stand_in",
        name="Input stand in",
        kind=models.KIND_CHECK,
        category="platform",
        subject_type="tenant",
        unit_of_work="config graph",
        template_key="input_stand_in",
        cap=100,
        current_version=1,
        trusted_version=1,
    )
    fields.update(overrides)
    return models.Runbook.objects.create(tenant=tenant, **fields)


@pytest.fixture()
def registered():
    """Register a throwaway definition on the LIVE registry and take it out after.

    The live one, for `test_us_rbs_038_definition_surface.py`'s reason:
    `services.definition_for` reaches `apps.runbooks.registry` by name and there
    is no seam to inject one through, so a test with its own registry would be
    testing a path the product never takes.
    """
    added: list[str] = []

    def _register(definition: RunbookDefinition) -> RunbookDefinition:
        registry._by_key[definition.key] = definition
        added.append(definition.key)
        return definition

    yield _register
    for key in added:
        registry._by_key.pop(key, None)


def _call(view, method, tenant, actor, path, **kwargs):
    return api_call(
        view,
        method,
        f"/api/{tenant.subdomain}{path}",
        user=actor.user,
        role=permissions.SYSTEM_ADMIN,
        tenant=tenant,
        **kwargs,
    )


def _enable(service: str) -> None:
    """Turn a service on for the tenant in context — the tenant's own switch."""
    from apps.tenancy import models as tenancy_models

    row = tenancy_models.TenantService.objects.filter(service__code=service).first()
    assert row is not None, f"{service} is not in this tenant's service list at all"
    row.enabled = True
    row.save(update_fields=["enabled"])


# ═══════════════════════════════════════════════════════════════════════════
# 1 — THE DECLARATION: A DOMAIN IS PART OF THE CONTRACT AND IS REFUSED WHEN
#     IT CANNOT BE HONOURED
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_039_a_domain_outside_the_closed_list_is_refused_at_construction():
    with pytest.raises(RunbookContractError) as raised:
        Parameter(name="services", type=PARAM_ENUM, label="Services", domain="plans")
    assert "plans" in str(raised.value)
    # The message names the whole vocabulary, so the fix is in the failure.
    for name in contract.DOMAINS:
        assert name in str(raised.value)


def test_us_rbs_039_choices_and_a_domain_together_are_refused():
    """One input, one list. Two sources for one list can disagree."""
    with pytest.raises(RunbookContractError) as raised:
        Parameter(
            name="services",
            type=PARAM_ENUM,
            label="Services",
            choices=("water",),
            domain=DOMAIN_SERVICE,
        )
    assert "choices" in str(raised.value) and DOMAIN_SERVICE in str(raised.value)


def test_us_rbs_039_all_on_a_single_value_input_is_refused():
    """`all` is a rule about SEVERAL — `BR-RBS-042` clause 1."""
    with pytest.raises(RunbookContractError) as raised:
        Parameter(
            name="account",
            type=PARAM_ENUM,
            label="Account",
            default=PARAM_ALL,
            domain=DOMAIN_ACCOUNT,
        )
    assert PARAM_ALL in str(raised.value)


def test_us_rbs_039_several_values_with_nothing_to_pick_them_from_is_refused():
    with pytest.raises(RunbookContractError):
        Parameter(name="services", type=PARAM_ENUM, label="Services", multi=True)


def test_us_rbs_039_the_shipped_ladder_declares_its_services_input():
    """The runbook the story is written about actually carries the input.

    A mechanism nothing uses is the shape hard-won law 2 names: it renders, it
    tests, and the feature does not exist.
    """
    ladder = registry.get("collections_ladder")
    services_input = next(p for p in ladder.parameters if p.name == "services")
    assert services_input.domain == DOMAIN_SERVICE
    assert services_input.multi is True
    assert services_input.default == PARAM_ALL


# ═══════════════════════════════════════════════════════════════════════════
# 2 — TC-RBS-039.2 · .3 — THE DOMAIN IS THE TENANT'S OWN, AND AN EMPTY ONE
#     SAYS SO
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_039_tc_2_the_services_domain_offers_this_tenant_s_own(brazos):
    """*A two-service utility's list offers two* — not the platform's eleven."""
    with tenant_ctx(brazos):
        page = domains.page(DOMAIN_SERVICE)
        offered = {row["value"] for row in page["rows"]}
        from apps.runbooks.seams import tenancy_seam

        assert offered == set(tenancy_seam.enabled_services())
        assert page["total"] == len(offered)
        # The chip shows a NAME, never a code by itself (B14 rule 31's spirit:
        # what a field renders is a word a clerk uses).
        assert all(row["label"] for row in page["rows"])
        # And it is smaller than the catalogue: eleven services exist.
        assert len(offered) < 11


def test_us_rbs_039_tc_3_an_empty_domain_says_so_rather_than_erroring(brazos):
    """Zero rows and a total of zero — never a 404 and never an exception.

    A utility mid-setup is not a bad request. The screen draws a sentence; an
    empty dropdown reads as broken.
    """
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        tenancy_models.TenantService.objects.update(enabled=False)
        page = domains.page(DOMAIN_SERVICE)
        assert page["rows"] == []
        assert page["total"] == 0
        # And the word *all* over an empty domain expands to nothing rather
        # than raising: the run matches nobody and says so.
        assert domains.members(DOMAIN_SERVICE) == ()


def test_us_rbs_039_the_account_domain_pages_and_is_never_read_whole(brazos):
    """`NFR-3` — 40,000 accounts at the top of T5 is not a dropdown.

    ⚠ **`members()` REFUSES IT BY NAME**, so a later lane cannot make an
    unbounded domain `multi` and have *all* quietly mean *read every account
    row into a pinned set*.
    """
    with tenant_ctx(brazos):
        assert domains.DOMAIN_IS_BOUNDED[DOMAIN_ACCOUNT] is False
        one = domains.page(DOMAIN_ACCOUNT, page=1, per=1)
        assert len(one["rows"]) <= 1
        assert one["per"] == 1
        with pytest.raises(domains.UnknownDomain):
            domains.members(DOMAIN_ACCOUNT)


def test_us_rbs_039_the_domain_route_pages_and_a_parameter_without_one_is_404(
    brazos, dana, registered
):
    definition = registered(_definition())
    with tenant_ctx(brazos):
        _runbook(brazos)
        ok = _call(
            api.runbook_parameter_domain,
            "get",
            brazos,
            dana,
            "/runbooks/input_stand_in/domains/services",
            key="input_stand_in",
            parameter="services",
        )
        assert ok.status_code == 200
        # The FOUR wire keys, never the selector's own (`DEF-WRK-4119`).
        assert set(ok.data) == {"count", "next", "previous", "results"}

        missing = _call(
            api.runbook_parameter_domain,
            "get",
            brazos,
            dana,
            "/runbooks/input_stand_in/domains/past_due_more_than",
            key="input_stand_in",
            parameter="past_due_more_than",
        )
        # *There is no list behind this input* and *this list is empty* are
        # different facts, and a screen must be able to tell them apart.
        assert missing.status_code == 404
    assert definition.key == "input_stand_in"


# ═══════════════════════════════════════════════════════════════════════════
# 3 — SAVING A VALUE: WHAT IS REFUSED, AND *all* IS STORED AS THE WORD
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_039_a_service_this_tenant_does_not_sell_is_refused_by_name(
    brazos, registered
):
    """`BR-RBS-042` clause 2 read as a REFUSAL rather than as a list.

    The same request is lawful at a utility that sells the service and refused
    at one that does not — which a hardcoded list of eleven could never do.
    """
    registered(_definition())
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        from apps.runbooks.seams import tenancy_seam

        sold = tenancy_seam.enabled_services()
        with pytest.raises(errors.ValidationError):
            services.update_runbook(runbook, {"parameters": {"services": ["not_sold"]}})
        version = services.update_runbook(
            runbook, {"parameters": {"services": [sold[0]]}}
        )
        assert version is not None
        runbook.refresh_from_db()
        assert runbook.parameters == {"services": [sold[0]]}


def test_us_rbs_039_all_is_stored_as_the_word_and_never_as_a_list(brazos, registered):
    """Clause 1, asserted on the STORED bytes rather than on behaviour.

    This is the assertion that fails on the tempting implementation — expanding
    at save time — and it is the only one that does, because an expanded list
    behaves identically until the domain changes.
    """
    registered(_definition())
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        services.update_runbook(runbook, {"parameters": {"services": PARAM_ALL}})
        runbook.refresh_from_db()
        assert runbook.parameters["services"] == "all"
        assert not isinstance(runbook.parameters["services"], list)


def test_us_rbs_039_an_input_the_runbook_does_not_declare_is_refused_by_name(
    brazos, registered
):
    registered(_definition())
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        with pytest.raises(errors.ValidationError):
            services.update_runbook(runbook, {"parameters": {"invented": "x"}})


def test_us_rbs_039_tc_5_no_step_list_and_no_filter_syntax_reaches_a_tenant(
    brazos, registered
):
    """PO 2026-09-06: a tenant sets input values and NOTHING else.

    Asserted at the one door a tenant's change comes through: the edit route
    refuses `steps`, `guards` and anything else that is not one of the nine
    editable settings, and `parameters` is the only one of the nine that is
    about the runbook's own logic at all.
    """
    registered(_definition())
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        for forbidden in ("steps", "guards", "resolve", "ports", "filter"):
            with pytest.raises(errors.ValidationError):
                services.update_runbook(runbook, {forbidden: []})
        assert "steps" not in services.EDITABLE_SETTINGS
        assert "guards" not in services.EDITABLE_SETTINGS


# ═══════════════════════════════════════════════════════════════════════════
# 4 — TC-RBS-039.1 — *ALL* MEANS ALL, INCLUDING WHAT ARRIVES AFTERWARDS
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_039_tc_1_a_service_enabled_after_setup_is_inside_all_on_the_next_run(
    brazos, registered
):
    """**THE CASE THIS WAVE EXISTS FOR.**

    A utility saves *services = all* today. A service is enabled next month. The
    run after that must cover the LARGER set — and the version that expands the
    word at save time passes every other test in this file and fails only this
    one, silently, in production, a month later.
    """
    definition = registered(_definition())
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        services.update_runbook(runbook, {"parameters": {"services": PARAM_ALL}})
        runbook.refresh_from_db()

        before = services.run_parameters(runbook, definition)["services"]
        assert isinstance(before, list) and before

        # The utility adds a service it did not sell at setup.
        added = next(
            code
            for code in ("trash", "storm_water", "solar", "broadband")
            if code not in before
        )
        _enable(added)

        after = services.run_parameters(runbook, definition)["services"]
        assert set(after) == set(before) | {added}
        assert len(after) == len(before) + 1
        # And nothing was reconfigured: the stored value is still the word.
        runbook.refresh_from_db()
        assert runbook.parameters["services"] == PARAM_ALL


def test_us_rbs_039_a_value_a_tenant_set_beats_the_declared_default(brazos, registered):
    """`DEF-RBS-4338` — the default and the tenant's answer are two things."""
    definition = registered(_definition())
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        assert services.run_parameters(runbook, definition)["past_due_more_than"] == "5.0000"
        services.update_runbook(
            runbook, {"parameters": {"past_due_more_than": "25.0000"}}
        )
        runbook.refresh_from_db()
        assert services.run_parameters(runbook, definition)["past_due_more_than"] == "25.0000"


def test_us_rbs_039_a_value_left_behind_by_a_dropped_input_is_ignored(brazos, registered):
    """A template update that drops an input must not leave a live value behind."""
    registered(_definition())
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        services.update_runbook(runbook, {"parameters": {"past_due_more_than": "9.0000"}})
        runbook.refresh_from_db()
        narrower = _definition(
            parameters=(
                Parameter(
                    name="services",
                    type=PARAM_ENUM,
                    label="Services",
                    default=PARAM_ALL,
                    multi=True,
                    domain=DOMAIN_SERVICE,
                ),
            )
        )
        assert "past_due_more_than" not in services.run_parameters(runbook, narrower)


# ═══════════════════════════════════════════════════════════════════════════
# 5 — TC-RBS-039.4 — THE TRUST RATCHET BITES ON AN INPUT CHANGE
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_039_tc_4_changing_an_input_drops_an_action_to_dry_run_only(
    brazos, registered
):
    """`BR-RBS-036`, now fired by a changed INPUT rather than a composition.

    The edit itself is never refused — a person narrowing a scope after a bad
    run must not be stopped from doing exactly that — and the LIVE run is.
    """
    definition = registered(
        _definition(kind=models.KIND_ACTION, ports=("queue_notice",))
    )
    with tenant_ctx(brazos):
        runbook = _runbook(brazos, kind=models.KIND_ACTION)
        # Trusted before the edit: a live run is allowed.
        services.open_run(runbook, definition, mode=models.MODE_LIVE)

        services.update_runbook(runbook, {"parameters": {"services": PARAM_ALL}})
        runbook.refresh_from_db()
        assert runbook.current_version != runbook.trusted_version

        with pytest.raises(errors.BizError) as refused:
            services.open_run(runbook, definition, mode=models.MODE_LIVE)
        assert refused.value.br_ref == "BR-RBS-036"
        # …and a DRY run of the same runbook is not held. *Dry-run only* is
        # what it says: the first thing a widened runbook can do is show you
        # what it would do.
        services.open_run(runbook, definition, mode=models.MODE_DRY)


def test_us_rbs_039_an_input_change_writes_a_version_and_shows_on_activity(
    brazos, registered
):
    """`BR-RBS-038` — every edit makes a new version, input changes included."""
    registered(_definition())
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        services.ensure_version(runbook, registry.get("input_stand_in"))
        before = runbook.current_version
        version = services.update_runbook(runbook, {"parameters": {"services": PARAM_ALL}})
        assert version is not None and version.version > before
        assert [row["field"] for row in version.summary] == ["parameters"]
        # The tenant's answer is inside the version document's settings half, so
        # a run can pin what it ran with.
        assert version.definition[services.SETTINGS_KEY]["parameters"] == {"services": "all"}
        # A no-op edit writes nothing (the Activity tab is not a log of who
        # opened the sheet).
        assert services.update_runbook(runbook, {"parameters": {"services": PARAM_ALL}}) is None


# ═══════════════════════════════════════════════════════════════════════════
# 6 — WHAT THE SETUP SCREEN IS HANDED
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_039_the_setup_payload_carries_the_tenant_s_value_not_the_default(
    brazos, registered
):
    registered(_definition())
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        services.update_runbook(runbook, {"parameters": {"past_due_more_than": "25.0000"}})
        payload = selectors.runbook_detail(brazos.id, "input_stand_in")
        rows = {row["name"]: row for row in payload["parameters"]}
        assert rows["past_due_more_than"]["value"] == "25.0000"
        assert rows["past_due_more_than"]["is_set"] is True
        # An input nobody touched reads its default and SAYS it is the default.
        assert rows["services"]["value"] == PARAM_ALL
        assert rows["services"]["is_set"] is False
        assert rows["services"]["domain"] == DOMAIN_SERVICE
        assert rows["services"]["multi"] is True


def test_us_rbs_039_a_chosen_value_travels_with_its_own_word_never_an_id(
    brazos, registered
):
    """B14 rule 31 — a saved `ref:object` value is an id and must not be drawn.

    `value_labels` is what the screen prints; the id is what is stored.
    """
    registered(_definition())
    with tenant_ctx(brazos):
        runbook = _runbook(brazos)
        from apps.runbooks.seams import tenancy_seam

        sold = tenancy_seam.enabled_services()[0]
        services.update_runbook(runbook, {"parameters": {"services": [sold]}})
        payload = selectors.runbook_detail(brazos.id, "input_stand_in")
        row = next(r for r in payload["parameters"] if r["name"] == "services")
        assert row["value_labels"][sold]
        assert row["value_labels"][sold] != sold or sold.istitle()


# ═══════════════════════════════════════════════════════════════════════════
# 7 — TENANT SCOPING (CLAUDE.md hard rule 1)
# ═══════════════════════════════════════════════════════════════════════════


def test_us_rbs_039_another_tenant_s_runbook_is_the_same_404_as_one_that_never_existed(
    brazos, lonestar, erin, registered
):
    registered(_definition())
    with tenant_ctx(brazos):
        _runbook(brazos)
    with tenant_ctx(lonestar):
        answer = _call(
            api.runbook_parameter_domain,
            "get",
            lonestar,
            erin,
            "/runbooks/input_stand_in/domains/services",
            key="input_stand_in",
            parameter="services",
        )
        assert answer.status_code == 404


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RBS-039 (EP-RBS-05; CR-075 wave T) · BR-RBS-042 (PO 2026-09-06) · BR-RBS-009 · BR-RBS-036 · BR-RBS-038 · NFR-3 · NFR-5
# generated: 2026-09-07 by the CR-075 wave T build lane
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_us_rbs_039_inputs.py
# exceptions: the PostgreSQL half — RLS on the new column — is tests/test_us_rbs_039_pg.py, which SKIPS here rather than passing vacuously
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

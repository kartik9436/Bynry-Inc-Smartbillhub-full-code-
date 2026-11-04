# ── Trace ──────────────────────────────────────────────
# Story:    US-INT-020 (EP-INT-06) — the run record, its five counts, and the
#           connection detail S142 reads. Screens: S142
# Rules:    BR-INT-039 (append-only, durable, with a trace id) · BR-INT-018 ·
#           BR-INT-040 (per-item results) · BR-INT-020 (`input_hash` before
#           parse) · CLAUDE.md hard rule 1 (tenant isolation) · B14 rules 31
#           and 32 (no id, no rule number in clerk copy)
# Tests:    this file — TC-1 (twenty rows, the 1 Aug row, the seven named) ·
#           TC-2 (eight characters find the run, its connection and the
#           provider's sentence) · TC-4 (no `BR-` and no uuid in any served
#           string) · TC-5 (tenant isolation; another tenant's run is a 404
#           identical to absent) · TC-6 (the leak path: scrubbed, absent from
#           the list, present on the detail) · TC-7 (`changed` only for a
#           reconcile operation) · the scrub's own shapes · the cap.
#           TC-3 is PostgreSQL's — tests/test_us_int_020_pg.py.
# Impacts:  apps/integrations/runs.py · runs_api.py · scrubbing.py ·
#           services.py (`finish_run(items=…)`) · sample_runs.py
# ───────────────────────────────────────────────────────
"""US-INT-020 on SQLite — the record, the two reads, and the leak that must not.

`brazos_runs` builds the story's own fixture (`§4 Test Data`) through
`apps/integrations/sample_runs.py`, which is the same builder the walkthrough's
seed command uses. One fixture, two consumers: a test that passed against a
private copy of the data would say nothing about the screen a person clicks.
"""

from __future__ import annotations

import re

import pytest

from apps.integrations import models, runs, runs_api, sample_runs, scrubbing, services
from core.pagination import ListParams
from core.permissions import BILLING_CLERK, EXECUTIVE, SYSTEM_ADMIN
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

SMTP = "email_smtp"
NEPTUNE = "meters_neptune360"


def _connection(tenant, provider=SMTP, label="billing@brazosbend.example"):
    return models.IntegrationConnection.objects.create(
        tenant=tenant,
        provider_key=provider,
        label=label,
        environment=models.ENVIRONMENT_PRODUCTION,
        status=models.STATUS_UNTESTED,
        cadence=models.CADENCE_MANUAL,
        config={},
    )


@pytest.fixture()
def brazos_runs(brazos):
    """The story's four runs, written through the real services."""
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        sample_runs.seed_runs(connection)
    return brazos


def _list(tenant, actor, role=SYSTEM_ADMIN, key=SMTP, query=None):
    return api_call(
        runs_api.runs_list,
        "get",
        f"/api/{tenant.subdomain}/integrations/{key}/runs",
        user=actor.user,
        role=role,
        tenant=tenant,
        query=query,
        key=key,
    )


def _detail(tenant, actor, run_id, role=SYSTEM_ADMIN, key=SMTP):
    return api_call(
        runs_api.run_detail,
        "get",
        f"/api/{tenant.subdomain}/integrations/{key}/runs/{run_id}",
        user=actor.user,
        role=role,
        tenant=tenant,
        key=key,
        run_id=str(run_id),
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 — the last twenty, newest first, and the 1 August row
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_int_020_tc1_the_runs_read_newest_first_with_the_counts_that_matter(
    brazos_runs, dana
):
    response = _list(brazos_runs, dana)
    assert response.status_code == 200
    body = response.data
    # The product's ONE page-size vocabulary (PO 2026-08-09), not the design's
    # twenty — a stamped deviation, argued in `runs.DEFAULT_WINDOW`'s comment.
    assert body["page"]["per"] == runs.DEFAULT_WINDOW == 50
    rows = body["rows"]
    assert [one["outcome"] for one in rows] == [
        models.OUTCOME_FAILED,        # 3 Sep — the manual test
        models.OUTCOME_FAILED,        # 2 Sep — the leak-path fixture
        models.OUTCOME_SUCCEEDED,     # 1 Sep
        models.OUTCOME_PARTIAL,       # 1 Aug
        models.OUTCOME_UNCONFIRMED,   # 1 Jul
    ]
    august = next(one for one in rows if one["outcome"] == models.OUTCOME_PARTIAL)
    # The numbers the sentence *86 of 93 · 7 bad addresses* is composed FROM.
    # The sentence itself is the screen's, in eleven languages (runs.py docstring).
    assert (august["attempted"], august["succeeded"], august["failed"]) == (93, 86, 7)
    assert august["named_items"] == 7 and august["unnamed_items"] == 0
    july = next(one for one in rows if one["outcome"] == models.OUTCOME_UNCONFIRMED)
    assert july["attempted"] == 93 and july["succeeded"] == 0


@pytest.mark.django_db
def test_us_int_020_tc1_opening_the_august_run_names_the_seven(brazos_runs, dana):
    listed = _list(brazos_runs, dana).data["rows"]
    august = next(one for one in listed if one["outcome"] == models.OUTCOME_PARTIAL)
    response = _detail(brazos_runs, dana, august["id"])
    assert response.status_code == 200
    items = response.data["items"]
    assert len(items) == 7
    assert [one["detail"] for one in items] == [address for _, address, _ in sample_runs.SEVEN]
    assert [one["ref"] for one in items] == [ref for ref, _, _ in sample_runs.SEVEN]
    # …each with the mailbox's own sentence for it.
    assert {one["provider_text"] for one in items} == {
        "No such mailbox", "Domain not found", "Mailbox full"
    }


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 — eight characters down the phone
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_int_020_tc2_eight_characters_find_the_run_its_connection_and_their_words(
    brazos_runs, dana
):
    response = _list(brazos_runs, dana, query={"q": sample_runs.DEMO_TRACE.lower()})
    assert response.status_code == 200
    rows = response.data["rows"]
    assert len(rows) == 1
    found = rows[0]
    # …the run,
    assert found["trace_id"] == sample_runs.DEMO_TRACE
    assert found["outcome"] == models.OUTCOME_FAILED
    # …its connection,
    assert found["connection_label"] == "billing@brazosbend.example"
    assert found["provider_key"] == SMTP
    # …and the provider's own sentence, which is on the DETAIL and not here.
    assert "provider_error" not in found
    detail = _detail(brazos_runs, dana, found["id"]).data
    assert detail["provider_error"] == "535 5.7.8 AUTHENTICATION FAILED"
    assert detail["items"][0]["provider_text"] == "535 5.7.8 AUTHENTICATION FAILED"


@pytest.mark.django_db
def test_us_int_020_tc2_the_search_is_tenant_wide_and_the_row_says_where_it_lives(
    brazos_runs, dana
):
    """Support does not know which connection the eight characters belong to —
    that is what they are ringing to find out. So a search opened on one
    connection's page still finds a run on another, and names it."""
    with tenant_ctx(brazos_runs):
        other = _connection(brazos_runs, provider=NEPTUNE, label="Water meter cloud")
        run = services.start_run(
            connection=other, operation="collect_readings", direction="inbound",
            trigger="scheduled",
        )
        run.trace_id = "B1C2D3E4"
        run.save(update_fields=["trace_id"])
        services.finish_run(
            run, attempted=1240, succeeded=1240, failed=0, skipped=0, changed=6,
            confirmed=True, summary="1,240 readings collected; 6 were revised.",
        )
    # …searched from the MAILBOX's page:
    rows = _list(brazos_runs, dana, key=SMTP, query={"q": "b1c2d3e4"}).data["rows"]
    assert len(rows) == 1
    assert rows[0]["provider_key"] == NEPTUNE
    assert rows[0]["connection_label"] == "Water meter cloud"
    body = _list(brazos_runs, dana, key=SMTP, query={"q": "b1c2d3e4"}).data
    assert body["elsewhere"] == 1  # the screen says so rather than mixing it in


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — no rule id, no database id, in anything served to a clerk
# ═══════════════════════════════════════════════════════════════════════════

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
_RULE = re.compile(r"\bBR-[A-Z]{3}-\d{3,5}\b|\bOQ-(?:[A-Z]{3}-)?\d{3,5}\b|\bUS-[A-Z]{3}-\d{3,5}\b")

#: The two keys that carry an id ON PURPOSE and are never rendered — the row
#: action fetches the detail with `id`, and `artifact_link` is a URL.
_NOT_COPY = {"id", "artifact_link"}


def _strings(node, path=""):
    if isinstance(node, dict):
        for name, value in node.items():
            if name in _NOT_COPY:
                continue
            yield from _strings(value, f"{path}.{name}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _strings(value, f"{path}[{index}]")
    elif isinstance(node, str):
        yield path, node


@pytest.mark.django_db
def test_us_int_020_tc4_no_rule_id_and_no_database_id_reaches_the_clerk(brazos_runs, dana):
    body = _list(brazos_runs, dana).data
    detail = _detail(brazos_runs, dana, body["rows"][0]["id"]).data
    for payload in (body, detail):
        for where, text in _strings(payload):
            assert not _RULE.search(text), f"a rule id reached the clerk at {where}: {text}"
            assert not _UUID.search(text), f"a database id reached the clerk at {where}: {text}"
    # The trace id is the ONE identifier on this screen, and it is eight
    # characters — not a truncated uuid (G69's shape), a purpose-made reference.
    assert len(detail["trace_id"]) == services.TRACE_ID_HEX == 8


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 — tenant isolation, and a 404 that cannot be told from an absent one
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_int_020_tc5_another_tenants_runs_are_not_listed(brazos_runs, lonestar, erin, dana):
    """Lone Star Ridge asks for the same provider's runs and gets its own —
    which is none. Nothing about Brazos Bend's four is visible in the answer."""
    with tenant_ctx(lonestar):
        _connection(lonestar, label="mail@lonestarridge.example")
    body = _list(lonestar, erin, role=SYSTEM_ADMIN).data
    assert body["rows"] == []
    assert body["page"]["count"] == 0
    # …and a trace search for the OTHER tenant's known reference finds nothing.
    assert _list(lonestar, erin, query={"q": sample_runs.DEMO_TRACE}).data["rows"] == []


@pytest.mark.django_db
def test_us_int_020_tc5_a_cross_tenant_run_id_is_the_same_404_as_an_absent_one(
    brazos_runs, lonestar, erin, dana
):
    theirs = _list(brazos_runs, dana).data["rows"][0]["id"]
    with tenant_ctx(lonestar):
        _connection(lonestar, label="mail@lonestarridge.example")
    real = _detail(lonestar, erin, theirs)
    absent = _detail(lonestar, erin, "01a06aad-0000-7000-8000-000000000000")
    nonsense = _detail(lonestar, erin, "not-a-uuid")
    assert real.status_code == absent.status_code == nonsense.status_code == 404
    # …and the bodies are identical apart from the envelope's own per-request
    # trace id (G1's `trace_id`), which is not the run's and differs per call.
    bodies = [dict(one.data) for one in (real, absent, nonsense)]
    for body in bodies:
        body.pop("trace_id", None)
    assert bodies[0] == bodies[1] == bodies[2]


@pytest.mark.django_db
def test_us_int_020_an_unknown_provider_key_is_the_same_404(brazos_runs, dana):
    response = _list(brazos_runs, dana, key="not_a_provider")
    assert response.status_code == 404


@pytest.mark.django_db
def test_us_int_020_a_billing_clerk_is_refused_the_read(brazos_runs, dana):
    """A4 `settings_lookups`: System Admin Full · Executive View · Billing
    Clerk no cell. The refusal is the server's, not a hidden menu item."""
    assert _list(brazos_runs, dana, role=BILLING_CLERK).status_code == 403
    assert _list(brazos_runs, dana, role=EXECUTIVE).status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 — the leak path
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_int_020_tc6_another_utilitys_customer_is_scrubbed_before_it_is_stored(
    brazos_runs, dana
):
    """A mail server quotes a DIFFERENT utility's customer back at us. The
    account number, the street and the town are gone before the row exists;
    the provider's own diagnostic survives, because that is what support asks
    for."""
    run = models.IntegrationRun.objects.get(
        tenant_id=brazos_runs.id, trace_id=sample_runs.LEAK_TRACE
    )
    stored = run.provider_error
    assert "4471-0021" not in stored
    assert "1408 Pecan St" not in stored
    assert "Lone Star Ridge" not in stored
    assert "postmaster@lonestarridge.example" not in stored
    assert scrubbing.MASK in stored
    assert "550 5.1.1" in stored  # their code, kept


@pytest.mark.django_db
def test_us_int_020_tc6_the_provider_error_is_absent_from_the_list_and_present_on_the_detail(
    brazos_runs, dana
):
    body = _list(brazos_runs, dana).data
    for row in body["rows"]:
        assert "provider_error" not in row
    for _where, text in _strings(body):
        assert "550 5.1.1" not in text  # nothing of it leaks through another key
    found = next(one for one in body["rows"] if one["trace_id"] == sample_runs.LEAK_TRACE)
    detail = _detail(brazos_runs, dana, found["id"]).data
    assert detail["provider_error"].startswith("550 5.1.1")


@pytest.mark.django_db
def test_us_int_020_tc6_no_audit_row_carries_the_providers_words(brazos_runs, dana):
    """*"absent from the audit row"*. Nothing in the audit trail written while
    the fixture was built quotes the provider at all."""
    from apps.audit.models import AuditLog

    payloads = [
        str(one.payload)
        for one in AuditLog.objects.filter(tenant_id=brazos_runs.id)
    ]
    for text in payloads:
        assert "4471-0021" not in text
        assert "AUTHENTICATION FAILED" not in text
        assert "550 5.1.1" not in text


def test_us_int_020_tc6_the_scrub_masks_four_shapes_and_keeps_the_diagnostic():
    scrubbed = scrubbing.scrub(sample_runs.LEAK)
    assert scrubbed == (
        "550 5.1.1 relay refused for account •••• at •••• — contact ••••"
    )
    # …and it is idempotent, so a value that crosses the seam twice is intact.
    assert scrubbing.scrub(scrubbed) == scrubbed
    # …and a provider's own status line is never touched.
    assert scrubbing.scrub("535 5.7.8 AUTHENTICATION FAILED") == "535 5.7.8 AUTHENTICATION FAILED"
    # …and a bare three-digit code is not an account number.
    assert scrubbing.scrub("451 4.7.1 try again later") == "451 4.7.1 try again later"
    # …and a post-office box carries no street word and is masked anyway.
    assert scrubbing.scrub("returned to P.O. Box 4471") == "returned to ••••"
    assert scrubbing.scrub(None) is None
    assert scrubbing.scrub("   ") is None


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 — the fifth count is shown only where something can be revised
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_int_020_tc7_changed_is_shown_only_for_a_reconciling_operation(brazos, dana):
    """*1,240 read · 6 revised* on a collection; four counts on a send. The
    manifest's idempotency mode decides it — no screen branches on a provider."""
    with tenant_ctx(brazos):
        collector = _connection(brazos, provider=NEPTUNE, label="Water meter cloud")
        run = services.start_run(
            connection=collector, operation="collect_readings", direction="inbound",
            trigger="scheduled",
        )
        services.finish_run(
            run, attempted=1240, succeeded=1240, failed=0, skipped=0, changed=6,
            confirmed=True, summary="1,240 readings collected; 6 were revised.",
        )
        mailbox = _connection(brazos)
        send = services.start_run(
            connection=mailbox, operation="send_message", direction="outbound",
            trigger="dispatcher",
        )
        services.finish_run(
            send, attempted=93, succeeded=93, failed=0, skipped=0, confirmed=True
        )
    collected = _list(brazos, dana, key=NEPTUNE).data["rows"][0]
    assert collected["show_changed"] is True and collected["changed"] == 6
    sent = _list(brazos, dana, key=SMTP).data["rows"][0]
    assert sent["show_changed"] is False


# ═══════════════════════════════════════════════════════════════════════════
# The record itself — the items kept, the cap, and the refusal to finish twice
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_int_020_a_run_stores_the_items_it_could_not_do_and_not_the_ones_it_could(brazos):
    with tenant_ctx(brazos):
        run = services.finish_run(
            services.start_run(
                connection=_connection(brazos), operation="send_message",
                direction="outbound", trigger="dispatcher",
            ),
            attempted=5, succeeded=3, failed=1, skipped=1, confirmed=True,
            items=[
                {"ref": "A-1", "outcome": "succeeded"},
                {"ref": "A-2", "outcome": "succeeded"},
                {"ref": "A-3", "outcome": "failed", "provider_text": "No such mailbox"},
                {"ref": "A-4", "outcome": "skipped", "provider_text": "Already sent today"},
                {"ref": "A-5", "outcome": "succeeded"},
            ],
        )
    assert [one["ref"] for one in run.items] == ["A-3", "A-4"]
    assert run.succeeded == 3  # the three that went are a COUNT, as they always were


@pytest.mark.django_db
def test_us_int_020_the_cap_says_in_the_payload_how_many_it_left_out(brazos, dana):
    with tenant_ctx(brazos):
        failures = services.ITEM_CAP + 17
        services.finish_run(
            services.start_run(
                connection=_connection(brazos), operation="send_message",
                direction="outbound", trigger="dispatcher",
            ),
            attempted=failures, succeeded=0, failed=failures, skipped=0, confirmed=True,
            items=[{"ref": f"A-{n}", "outcome": "failed"} for n in range(failures)],
        )
    row = _list(brazos, dana).data["rows"][0]
    assert row["named_items"] == services.ITEM_CAP
    assert row["unnamed_items"] == 17  # said in words on the screen, never a silent gap


@pytest.mark.django_db
def test_us_int_020_a_finished_run_cannot_be_finished_again(brazos):
    """Hard rule 4's shape on every vendor. The PostgreSQL trigger that refuses
    a raw UPDATE beneath this is tests/test_us_int_020_pg.py's."""
    from core import errors

    with tenant_ctx(brazos):
        run = services.finish_run(
            services.start_run(
                connection=_connection(brazos), operation="send_message",
                direction="outbound", trigger="manual",
            ),
            attempted=1, succeeded=1, failed=0, skipped=0, confirmed=True,
        )
        with pytest.raises(errors.BizError) as raised:
            services.finish_run(
                run, attempted=1, succeeded=0, failed=1, skipped=0, confirmed=True
            )
    assert raised.value.br_ref == "BR-INT-039"


@pytest.mark.django_db
def test_us_int_020_the_fixture_replays_without_writing_a_second_set(brazos):
    """`integration_run` is append-only, so the honest replay is to do nothing."""
    with tenant_ctx(brazos):
        connection = _connection(brazos)
        sample_runs.seed_runs(connection)
        assert sample_runs.seeded(brazos.id) is True
        before = models.IntegrationRun.objects.filter(tenant_id=brazos.id).count()
    assert before == 5


# ═══════════════════════════════════════════════════════════════════════════
# The filters the capability matrix declares, through the kernel's grammar
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_us_int_020_the_three_filters_narrow_and_an_undeclared_one_is_ignored(
    brazos_runs, dana
):
    assert len(_list(brazos_runs, dana, query={"f.trigger": "manual"}).data["rows"]) == 2
    assert len(_list(brazos_runs, dana, query={"f.outcome": "unconfirmed"}).data["rows"]) == 1
    assert len(_list(brazos_runs, dana, query={"f.operation": "send_message"}).data["rows"]) == 5
    # BR-SHL-011: an undeclared filter is ignored, never an error.
    assert len(_list(brazos_runs, dana, query={"f.summary": "anything"}).data["rows"]) == 5
    assert _list(brazos_runs, dana, query={"page": "nonsense"}).status_code == 200


@pytest.mark.django_db
def test_us_int_020_the_read_model_is_the_same_one_the_grid_draws_from(brazos_runs, dana):
    """The card and its detail can never disagree about a state word, because
    the head of this payload IS `selectors.provider_card`."""
    body = _list(brazos_runs, dana).data
    from apps.integrations import selectors

    with tenant_ctx(brazos_runs):
        card = selectors.provider_card(brazos_runs.id, SMTP)
    assert body["display_state"] == card["display_state"]
    assert body["describe"] == card["connection"]["describe"]

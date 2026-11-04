# ── Trace ──────────────────────────────────────────────
# Change:   CR-083 (PO 2026-09-07 — *"Im okay with this - please add- Step 30,
#           Integrations"*). The four-part plan that sentence approved is
#           written out in 12-governance/02-decision-log.md of the same day.
# Story:    US-INT-020 §4 · US-INT-021 §4 (the five runs) · US-TEN-019
# Rules:    BR-INT-018 (the outcome is COMPUTED, never typed) · BR-INT-039
#           (a run is append-only) · BR-TEN-056/057/060/063/066 · BR-LED-004
#           (one handover per period + target) · CLAUDE.md hard-won law 1
#           (no claim the product cannot support, on a screen) · law 2
#           (built is not wired) · law 5 (one seeder for one set of rows)
# Impacts:  apps/integrations/sample_data.py · apps/integrations/services.py ·
#           apps/tenancy/sample_data.py · apps/integrations/seams/ledger.py
# ───────────────────────────────────────────────────────
"""The Integrations block of the sample set, and the wiring that was missing.

⚠ **WHY A TEST FILE FOR A FIXTURE.** Nothing went red while
`apps/integrations/sample_runs.py` sat finished and unreached for three days —
every integrations table read 0 on every tenant provisioned through the real
sign-up path and the whole suite was green over it. The properties asserted
here are the ones that would hurt somebody other than this lane: the block is
IN the registry, it is in the position the ruling put it, nothing on a
connection card claims a capability this release does not have, and no outcome
word in the fixture is typed by the fixture.

⚠ **THE ROW-WRITING HALF IS PROVED ON POSTGRESQL, NOT HERE.** `integration_run`
is a partitioned, RLS-forced, append-only table and `config/settings/test.py`
hardcodes in-memory SQLite (CLAUDE.md law 14), so a green run of this file says
nothing about the writes. The walkthrough on a real database is what proves
those, and its figures are in the decision-log row: a freshly provisioned
tenant reports `integrations seed_sample_records seeded 10` — three
connections, five runs, one landed payment notification and one recorded
accounting handover.
"""

from __future__ import annotations

from apps.integrations import models as integration_models
from apps.integrations import registry as integration_registry
from apps.integrations import sample_data, sample_runs, services
from apps.tenancy import sample_data as tenancy_sample
from apps.tenancy import seams as tenancy_seams

BLOCK = "integrations:seed_sample_records"


# ══ the registry — hard-won law 2, which is the whole reason this exists ════


def test_the_registry_carries_the_integrations_block():
    keys = [spec.key for spec in tenancy_sample.SAMPLE_MODULES]
    assert BLOCK in keys, (
        "`integrations` owns five tables and seeded none of them: the run fixture had been "
        "finished and unreached since 2026-09-04, so every provisioned tenant read 0"
    )


def test_the_orchestrator_can_actually_resolve_the_seam():
    """The registry row and the seam land in ONE commit or the branch is
    merge-blocked in between — a row whose module publishes no such function is
    a NAMED not-loaded line and `run_summary()` then answers succeeded=False."""
    assert tenancy_seams.resolve("integrations", "seed_sample_records") is not None
    assert tenancy_seams.resolve("integrations", "remove_sample_records") is not None
    assert tenancy_seams.resolve("integrations", "sample_record_count") is not None
    assert tenancy_seams.resolve("integrations", "seed_sample_records_note") is not None


def test_the_block_is_last_because_the_handover_needs_a_finished_month():
    """The POSITION is the feature. The block records one accounting handover,
    and a handover is refused over a month that is not closed and over books
    that do not foot — both of which are made by the money blocks above it."""
    keys = [spec.key for spec in tenancy_sample.SAMPLE_MODULES]
    assert keys.index(BLOCK) > keys.index("billing:seed_sample_records")
    assert keys.index(BLOCK) > keys.index("billing:seed_sample_second_cycle")
    assert keys.index(BLOCK) > keys.index("payments:seed_sample_records")


def test_the_block_declares_that_dependency_verbatim():
    edges = tenancy_sample.BLOCK_DEPENDENCIES.get(BLOCK) or ()
    assert [upstream for upstream, _f, _q in edges] == ["billing:seed_sample_records"]
    _upstream, path, quote = edges[0]
    import io

    assert quote in io.open(path, encoding="utf-8").read(), (
        "a dependency declared from prose stays true only while the prose does"
    )


def test_the_screen_names_the_same_steps_the_orchestrator_walks():
    """`PROVISIONING_STEPS` is a hand-typed copy of this tuple and it has now
    been left behind FOUR times. The frontend suite parses the Python; this is
    the same assertion in the suite lanes actually run."""
    import io
    import re
    from pathlib import Path

    here = Path(__file__).resolve().parents[2]
    source = io.open(
        here / "07-frontend/src/features/tenancy/SignupWizard.tsx", encoding="utf-8"
    ).read()
    block = re.search(
        r"export const PROVISIONING_STEPS: readonly string\[\] = \[(.*?)\n\];", source, re.S
    )
    assert block is not None, "PROVISIONING_STEPS not found in SignupWizard.tsx"
    typed = re.findall(r'"([a-z_]+:[a-z_]+)"', block.group(1))
    assert typed == [spec.key for spec in tenancy_sample.SAMPLE_MODULES]


def test_every_step_has_a_clerk_facing_label_in_english():
    import io
    import json
    from pathlib import Path

    here = Path(__file__).resolve().parents[2]
    catalogue = json.loads(
        io.open(here / "07-frontend/src/i18n/locales/en.json", encoding="utf-8").read()
    )
    for spec in tenancy_sample.SAMPLE_MODULES:
        key = f"tenancy.signup.provisioning.block.{spec.module}.{spec.seam}"
        assert catalogue.get(key), f"{spec.key} has no label in en.json"


# ══ what the fixture claims ════════════════════════════════════════════════


def test_three_connections_and_every_provider_has_an_adapter_behind_it():
    """One row is not a list — and a demo must never invent a provider."""
    keys = [str(spec["provider_key"]) for spec in sample_data.SEEDED_CONNECTIONS]
    assert len(keys) == 3 and len(set(keys)) == 3
    for key in keys:
        manifest = integration_registry.REGISTRY.get(key)
        assert manifest is not None, f"{key} is not a registered provider"
        assert not manifest.disposition.coming_soon, (
            f"{key} is coming-soon, and `services.connect` refuses one (BR-INT-001)"
        )


def test_the_fixture_writes_no_secret_into_the_non_secret_column():
    """`services.connect` refuses a secret-kind field by name (BR-INT-003) —
    which means a config here that carried one would refuse EVERY tenant's
    plant. Asserted against the manifest rather than against a list of names."""
    for spec in sample_data.SEEDED_CONNECTIONS:
        manifest = integration_registry.REGISTRY.require(str(spec["provider_key"]))
        secrets = {one.name for one in manifest.fields if one.is_secret}
        assert not (secrets & set(spec["config"])), (
            f"{spec['provider_key']}'s fixture config carries a secret field"
        )


def test_every_config_key_is_a_field_the_provider_actually_declares():
    for spec in sample_data.SEEDED_CONNECTIONS:
        manifest = integration_registry.REGISTRY.require(str(spec["provider_key"]))
        declared = {one.name for one in manifest.fields}
        unknown = sorted(set(spec["config"]) - declared)
        assert not unknown, f"{spec['provider_key']} has no field(s) {unknown}"


def test_no_seeded_connection_claims_to_work():
    """Hard-won law 1, on a screen. No adapter is registered in this release, so
    a green tick on a connection card would be a claim the product cannot
    support. `services.connect` writes `untested` and nothing here overrides
    it — asserted because a later `status=` in the fixture would be silent."""
    import inspect

    body = inspect.getsource(sample_data)
    for word in ("STATUS_WORKING", "STATUS_NOT_WORKING", '"working"'):
        assert word not in body, f"the fixture must not set a connection status ({word})"


def test_the_fixture_never_types_an_outcome_word():
    """BR-INT-018: the outcome is computed by `finish_run` from the counts and
    the far end's confirmation. `US-INT-021` TC-2 calls the alternative
    *trivially satisfied by a stub* — a fixture that wrote the word would be
    green while the rule it exists to demonstrate was broken."""
    import ast
    import inspect

    # ⚠ **THE DOCSTRING IS STRIPPED, AND THE FIRST DRAFT OF THIS CHECK WAS RED
    # BECAUSE OF ITS OWN SUBJECT.** `sample_runs`' module docstring explains the
    # rule by QUOTING the thing it forbids — *"a fixture that wrote
    # `outcome="unconfirmed"` directly would make the walkthrough green"* — so a
    # naive substring search over the source finds the warning and calls it the
    # offence. A check that cannot tell a prohibition from its own explanation is
    # a check that fails wrongly, which is the mirror of the false pass CLAUDE.md
    # law 7 asks about. The CODE is what is searched.
    tree = ast.parse(inspect.getsource(sample_runs))
    code = "\n".join(
        ast.unparse(node)
        for node in tree.body
        if not (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant))
    )
    for word in ('outcome="', "outcome='", "outcome=models."):
        assert word not in code, f"the run fixture types an outcome ({word})"
    # …and the calls that DO decide it are the real services, not a local stub.
    assert "services.finish_run(" in code and "services.start_run(" in code


def test_the_demo_keeps_a_run_that_failed():
    """DELIBERATE, and nobody should "fix" it. A demo where everything succeeded
    teaches a clerk nothing about the screen they will actually need — the same
    principle that leaves the third billing cycle unbilled."""
    import inspect

    body = inspect.getsource(sample_runs)
    assert "535 5.7.8 AUTHENTICATION FAILED" in body
    assert sample_runs.DEMO_TRACE == "A7F3C9E1", (
        "the demo is a support agent being read eight characters over the telephone; "
        "a random reference cannot be written into a walkthrough"
    )


def test_there_is_one_seeder_and_the_block_reuses_it():
    """Hard-won law 5. Two seeders for one set of rows is two sources of truth,
    so the block CALLS `sample_runs.seed_runs` rather than writing runs."""
    import inspect

    body = inspect.getsource(sample_data)
    assert "sample_runs.seed_runs(" in body
    assert "finish_run(" not in body, "the block must not write a run itself"
    assert "start_run(" not in body


def test_removal_keys_narrower_than_the_provider_and_names_what_it_keeps():
    """`integration_connection` has no `is_sample` column, so removal keys on
    the fixture's own labels — a mail server the utility connected itself is
    never touched — and every append-only row is RETAINED BY NAME
    (BR-TEN-066)."""
    assert sample_data.SEEDED_LABELS == {
        str(spec["label"]) for spec in sample_data.SEEDED_CONNECTIONS
    }
    import inspect

    body = inspect.getsource(sample_data.remove_sample_records)
    assert "retained" in body and "IntegrationRun.objects.filter" in body


def test_the_accounting_month_is_the_month_the_first_cycle_billed_IN():
    """⚠ NOT the month it MEASURED, and the difference was measured rather than
    reasoned about. The demo bills June and ISSUES those bills on 2 July, so a
    seeded tenant's earliest journal entry is 2026-07-02 and June holds none at
    all: a June batch came back with 0 rows and the content hash of an empty
    list — lawful, useless, and invisible to every check in this repository."""
    from datetime import date

    period = sample_data._accounting_month()
    assert period == (date(2026, 7, 1), date(2026, 7, 31))


def test_the_delivery_key_is_built_by_the_rule_and_not_typed():
    """BR-INT-020 D — the key is the provider's event id COMPOSITE with the
    payment/return marker, and the marker comes from the operation's DECLARED
    natural key. `K-88231|payment` and `K-88231|return` are two keys, which is
    the whole of why a return is not mistaken for a duplicate."""
    from apps.integrations import inbound

    manifest = integration_registry.REGISTRY.require(sample_data.KIOSK_PROVIDER)
    operation = next(
        one for one in manifest.operations if one.name == sample_data.KIOSK_OPERATION
    )
    key = inbound.dedupe_key(operation, sample_data.KIOSK_EVENT_ID)
    assert key.startswith(sample_data.KIOSK_EVENT_ID) and key != sample_data.KIOSK_EVENT_ID
    import inspect

    body = inspect.getsource(sample_data)
    assert "inbound.dedupe_key(" in body
    assert f'"{key}"' not in body, "the composite key is computed, never typed"


def test_the_body_carries_the_field_the_manifest_says_the_id_lives_in():
    manifest = integration_registry.REGISTRY.require(sample_data.KIOSK_PROVIDER)
    operation = next(
        one for one in manifest.operations if one.name == sample_data.KIOSK_OPERATION
    )
    assert operation.idempotency.key_field in sample_data.KIOSK_BODY


def test_the_ledger_seam_writes_nothing_itself():
    """BR-TEN-013 — the seam is the ADDRESS and ledger's own service is the
    writer. A seam file holding an ORM write would be the boundary violation
    the seam exists to avoid."""
    import inspect

    from apps.integrations.seams import ledger as ledger_seam

    body = inspect.getsource(ledger_seam)
    for forbidden in (".objects.", ".save(", ".create(", ".delete("):
        assert forbidden not in body, f"the ledger seam performs a write ({forbidden})"
    assert "ledger_close.close_period(" in body
    assert "ledger_exports.create_export_batch(" in body


def test_the_seeded_labels_are_clerk_facing_and_carry_no_internal_code():
    """B14 rules 31 and 32 — a label is what a person reads on a card."""
    import re

    forbidden = re.compile(r"\b(BR-[A-Z]{3}-\d+|OQ-\d+|DEF-\d+|US-[A-Z]{3}-\d+|S\d{1,3})\b")
    for label in sample_data.SEEDED_LABELS:
        assert not forbidden.search(label), label


def test_the_status_the_fixture_expects_is_the_one_connect_writes():
    assert integration_models.STATUS_UNTESTED == "untested"
    import inspect

    body = inspect.getsource(services.connect)
    assert "status=models.STATUS_UNTESTED" in body


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-083 (PO 2026-09-07) · US-INT-020 §4 · US-TEN-019
# generated: 2026-09-07 by the CR-083 integrations sample-data lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: pytest tests/test_cr083_integrations_sample_data.py · the PostgreSQL walkthrough (the writes, which SQLite cannot prove)
# exceptions: no row-writing case here — `integration_run` is partitioned, RLS-forced and append-only and the suite runs on in-memory SQLite (law 14)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

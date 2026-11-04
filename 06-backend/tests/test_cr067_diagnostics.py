# ── Trace ──────────────────────────────────────────────
# Change:   CR-067 tasks A1–A5 (12-governance/11-change-requests.md). PO
#           2026-09-02, verbatim: *"when we record these errors in audit log then
#           we need to know detials so that we can reproduce it just by procing
#           the details we should able to locate and understand what was the
#           error"*
# Rules:    BR-AUD-002 (the audit log has no write verbs — so raw error text may
#           never be written into it) · BR-AUD-006 (PII masked only) ·
#           BR-AUD-007 (tenant from context) · CLAUDE.md hard rule 1 (tenant
#           scoping) · hard-won law 7 (prove a guard RED before trusting it
#           green) · hard-won law 14 (the SAVEPOINT, and why the default suite
#           cannot show it)
# Tests:    this file IS the D1 half for tasks A1–A5
# ───────────────────────────────────────────────────────
"""CR-067 — the diagnostic record: written, joined, redacted by signature, swept.

EVERY TEST HERE WAS PROVED RED BEFORE IT WAS TRUSTED GREEN (hard-won law 7).
The failure each one produced against the un-built or sabotaged code is quoted
in its own docstring, so a later reader can tell a real assertion from a
vacuous one.

⚠ **THE ACCEPTANCE TEST IS `test_cr067_a5__section_5`** at the bottom. CR-067
§5 puts the Product Owner's own sentence as a testable bar — *"Could somebody
holding ONLY the diagnostic record write a failing test?"* — and that test is
written from the record's FIELDS and from nothing else. If it ever has to read
something the record does not hold, the record is incomplete and the record is
what gets fixed.
"""

import datetime as dt
import inspect
import uuid
from types import SimpleNamespace

import pytest
from django.conf import settings as django_settings

from apps.audit import diagnostics as audit_diagnostics
from apps.audit.diagnostic_models import ErrorDiagnostic
from apps.tenancy import document_storage, sample_data
from core import diagnostics
from core import tenancy as core_tenancy

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    admin_actor,
    lonestarridge_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── The two values a real failure carried, used as bait everywhere below ────
#: A customer's account number and a balance, exactly the shapes CR-067 §2 names
#: — *"a runtime message routinely carries an account number, a balance or a
#: meter reading"*. Every redaction test asserts that NEITHER survives anywhere
#: in a stored record.
BAIT_ACCOUNT = "A-10001"
BAIT_BALANCE = "181.9400"


class SeederBlewUp(RuntimeError):
    """An exception whose MESSAGE carries customer data, like the real ones do."""


def _bait_exception() -> SeederBlewUp:
    try:
        raise SeederBlewUp(
            f"account {BAIT_ACCOUNT} could not be billed: balance {BAIT_BALANCE} "
            "is under the minimum"
        )
    except SeederBlewUp as exc:
        return exc


def _stored_text(row: ErrorDiagnostic) -> str:
    """Every stored field of one record as one string, for a `not in` assertion.

    Reading the row field by field would let a new column arrive uncovered — and
    a new column is exactly where a future lane would put a message.
    """
    return " ".join(
        repr(getattr(row, field.attname)) for field in ErrorDiagnostic._meta.concrete_fields
    )


# ══ A2 · THE REDACTION RULE, ENFORCED BY SIGNATURE ═════════════════════════
def test_cr067_a2__the_signature_has_no_parameter_that_takes_a_value():
    """`capture()`'s parameter list IS the guarantee, so assert the list itself.

    This mirrors what `apps/tenancy/sample_errors.audit_safe_sentence(code)`
    already says of itself — *"It takes ONLY the code… The signature is the
    guarantee"* — and it is the test that survives a future lane, because it
    goes red the moment somebody adds a `message=` or a `context=` parameter
    "just for this one case".

    RED-PROVED (measured, not recalled): with a `detail: str | None = None`
    parameter added to `capture()` this failed with

        AssertionError: core.diagnostics.capture grew parameter(s) {'detail'}.
        Every parameter of this function must be a NAME, a number or the
        exception object — CR-067 §2. If a new one is genuinely needed, change
        this list deliberately and say why in the CR.
        assert {'audit_actio...'job_id', ...} <= {'audit_actio...ob_kind', ...}
          Extra items in the left set: 'detail'
    """
    allowed = {
        "error_code",
        "exception",
        "component",
        "settings_named",
        "request_fields",
        "job_kind",
        "job_id",
        "step",
        "step_total",
        "audit_action",
        "trace_id",
    }
    actual = set(inspect.signature(diagnostics.capture).parameters)
    assert actual <= allowed, (
        f"core.diagnostics.capture grew parameter(s) {actual - allowed}. Every "
        "parameter of this function must be a NAME, a number or the exception "
        "object — CR-067 §2. If a new one is genuinely needed, change this list "
        "deliberately and say why in the CR."
    )
    # And `assemble` — the pure half everything else goes through — the same.
    assert set(inspect.signature(diagnostics.assemble).parameters) <= allowed | {"now"}


@pytest.mark.parametrize(
    "smuggled",
    [
        "account_no=A-10001",
        "A-10001",
        "181.9400",
        "balance is 181.94",
        "customer@example.com",
        "account_no; DROP TABLE",
        "",
        "a" * 200,
    ],
)
def test_cr067_a2__a_value_dressed_as_a_field_name_is_refused(smuggled):
    """`request_fields` takes NAMES. Everything that is not one is refused.

    The adversarial half of task A2: a caller trying to get a value in through
    the only string list the writer accepts.

    RED-PROVED (measured): with `FIELD_NAME_RE` relaxed to `^.+$`, **seven of
    the eight** parameters failed with

        Failed: DID NOT RAISE DiagnosticInputRefused

    ⚠ The eighth is `""` and it kept passing, because the empty string does not
    match `.+` either. That is worth saying rather than rounding up to eight: a
    parametrised case that survives a sabotage is a case the sabotage did not
    reach, and reporting it as covered would be the same class of claim as a
    comment asserting a guarantee (hard-won law 1).
    """
    with pytest.raises(diagnostics.DiagnosticInputRefused):
        diagnostics.validated_field_names([smuggled])


def test_cr067_a2__a_lawful_field_name_is_kept_and_deduplicated():
    """The refusal must not be a check that cannot pass — names DO go in."""
    assert diagnostics.validated_field_names(["account_no", "amount", "account_no"]) == [
        "account_no",
        "amount",
    ]


def test_cr067_a2__the_exception_message_never_reaches_the_record():
    """The strongest form of A2: capture a real exception carrying real values.

    The message holds an account number and a balance. Nothing in the stored
    row may hold either — not in a column, not in a JSON blob, not in a frame.

    RED-PROVED (measured): with `assemble()` writing
    `"exception_type": f"{type(exception).__name__}: {exception}"` — the exact
    "helpful" slip a hurried lane makes — this failed with

        AssertionError: the stored diagnostic carries 'A-10001', which came out
        of the exception's message. audit_log has no delete and neither record
        may carry a customer's data (CR-067 §2, BR-AUD-002).
        assert 'A-10001' not in "UUID('01a06…imezone.utc)"
          'A-10001' is contained here:
            : account A-10001 could not be billed: balance 181.9400 is under the
            minimum' 'tests.test_cr067_diagnostics' …

    ⚠ **THE SABOTAGE HAD TO PUT THE MESSAGE IN A COLUMN THAT EXISTS**, and that
    is worth knowing: adding a stray `"message"` key to the assembled dict
    changes nothing, because `apps/audit/diagnostics.STORED_FIELDS` is a
    whitelist and writes only the columns the model declares. Two layers, and
    the outer one is the signature.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        reference = diagnostics.capture(
            error_code="SD-UNEXPECTED",
            exception=_bait_exception(),
            component="billing:seed_sample_records",
        )
        row = audit_diagnostics.by_reference(reference)
    assert row is not None
    text = _stored_text(row)
    for bait in (BAIT_ACCOUNT, BAIT_BALANCE, "under the minimum"):
        assert bait not in text, (
            f"the stored diagnostic carries {bait!r}, which came out of the "
            "exception's message. audit_log has no delete and neither record "
            "may carry a customer's data (CR-067 §2, BR-AUD-002)."
        )
    # What it DOES carry is the type, which is code and not data.
    assert row.exception_type == "SeederBlewUp"


def test_cr067_a2__a_refused_call_writes_nothing_and_still_returns_a_reference():
    """A smuggled value loses the RECORD, never the run and never the reference.

    Two halves, and both matter. Nothing is stored — a half-redacted record
    would be worse than none, because no reader could tell which half. And
    `capture()` still returns the reference, so the permanent audit row about to
    be written is still correct and still quotable.

    RED-PROVED (measured): with `capture()`'s `except DiagnosticInputRefused`
    narrowed to a class nothing raises, the refusal escaped into the caller and
    this failed with

        core.diagnostics.DiagnosticInputRefused: request_fields takes field
        NAMES, never values, and str 'A-10001' is not a name. A diagnostic
        records which fields were involved; the audit log has no delete and
        neither record may carry an account number, a balance or a reading.
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        before = ErrorDiagnostic.objects.count()
        reference = diagnostics.capture(
            error_code="SD-UNEXPECTED",
            exception=_bait_exception(),
            component="billing:seed_sample_records",
            request_fields=[BAIT_ACCOUNT],
        )
        assert ErrorDiagnostic.objects.count() == before
    assert reference != diagnostics.SUPPORT_REF_ABSENT
    assert len(reference) == diagnostics.SUPPORT_REF_HEX + 1  # "5F2B-9C1D"


def test_cr067_a2__a_settings_value_is_read_here_and_never_passed_in(settings):
    """The caller NAMES a setting; this module reads it. A secret is not read.

    RED-PROVED (measured): with the `SECRET_NAME_MARKERS` filter short-circuited
    this failed with

        AssertionError: the diagnostic recorded the value of a setting whose
        name says it is a secret
        assert 'not-the-real...till-a-secret' == '<set>'
    """
    settings.DOCUMENT_STORAGE_BUCKET = ""
    settings.SECRET_KEY = "not-the-real-one-but-still-a-secret"
    snapshot = diagnostics.settings_snapshot(
        ["DOCUMENT_STORAGE_BUCKET", "SECRET_KEY", "NO_SUCH_SETTING_ANYWHERE"]
    )
    assert snapshot["DOCUMENT_STORAGE_BUCKET"] == ""
    assert (
        snapshot["SECRET_KEY"] == "<set>"
    ), "the diagnostic recorded the value of a setting whose name says it is a secret"
    # "not defined" and "defined but empty" are DIFFERENT facts, and telling
    # them apart is the whole of the 2026-09-02 failure.
    assert snapshot["NO_SUCH_SETTING_ANYWHERE"] == "<not defined>"
    assert snapshot["DOCUMENT_STORAGE_BUCKET"] != snapshot["NO_SUCH_SETTING_ANYWHERE"]


def test_cr067_a2__a_settings_name_that_is_not_a_name_is_refused():
    """The same rule one level up: even the NAME list is validated."""
    with pytest.raises(diagnostics.DiagnosticInputRefused):
        diagnostics.settings_snapshot(["DOCUMENT_STORAGE_BUCKET = ''"])
    with pytest.raises(diagnostics.DiagnosticInputRefused):
        diagnostics.register_settings_for(SeederBlewUp, ["lower_case_is_not_a_setting"])


# ══ A1 · THE RECORD: WRITTEN, READ BACK BY REFERENCE, TENANT-SCOPED ════════
def test_cr067_a1__a_record_is_written_and_read_back_by_its_reference():
    """Task A1's own done-when: *"a record is written and can be read back by
    reference"*.

    RED-PROVED: before `apps/audit/diagnostics.py` existed this failed at import
    with

        ModuleNotFoundError: No module named 'apps.audit.diagnostics'
    """
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        reference = diagnostics.capture(
            error_code="SD-DB-INTEGRITY",
            exception=_bait_exception(),
            component="customers:seed_sample_records",
            job_kind=sample_data.PLANT_JOB_KIND,
            job_id=uuid.uuid4(),
            step=8,
            step_total=17,
            audit_action=sample_data.AUDIT_BLOCK_FAILED,
        )
        row = audit_diagnostics.by_reference(reference)
        assert row is not None
        assert row.reference == reference
        assert row.error_code == "SD-DB-INTEGRITY"
        assert row.component == "customers:seed_sample_records"
        assert row.step == 8 and row.step_total == 17
        assert row.audit_action == "sample.block_failed"
        assert row.frames, "a record with no frames cannot say where in the code"
        assert row.frames[-1]["file"].startswith("06-backend/")
        assert row.release
        # A person can type it back with or without the dash, in either case.
        assert audit_diagnostics.by_reference(reference.replace("-", "").lower()) is not None


def test_cr067_a1__another_tenants_diagnostic_is_ABSENT_not_forbidden():
    """CLAUDE.md hard rule 1, in the shape this repo insists on: absent.

    RED-PROVED (measured): with the `tenant_id=` filter dropped from
    `by_reference` this failed with

        AssertionError: tenant B read tenant A's diagnostic. Another tenant's
        record must be ABSENT under this scope, not forbidden.
        assert <ErrorDiagnostic: ErrorDiagnostic object (01a06309-…)> is None
          where … = audit_diagnostics.by_reference('61BE-178E')

    ⚠ This is the APP-LAYER half and it runs on every vendor. The DATABASE half
    is `error_diagnostics_tenant_isolation` (audit/0006) and is proved on live
    PostgreSQL, because `config/settings/test.py` hardcodes SQLite, which has no
    row-level security at all.
    """
    tenant_a, _ = provisioned_tenant()
    tenant_b, _ = provisioned_tenant(lonestarridge_payload())
    with tenant_ctx(tenant_a):
        reference = diagnostics.capture(
            error_code="SD-REFUSED",
            exception=_bait_exception(),
            component="billing:seed_sample_records",
        )
        assert audit_diagnostics.by_reference(reference) is not None
    with tenant_ctx(tenant_b):
        assert audit_diagnostics.by_reference(reference) is None, (
            "tenant B read tenant A's diagnostic. Another tenant's record must "
            "be ABSENT under this scope, not forbidden."
        )


def test_cr067_a1__a_diagnostic_with_no_tenant_in_context_is_refused():
    """Deny-by-default. A record RLS could never show anyone again is a lie."""
    core_tenancy.clear_current_tenant()
    with pytest.raises(audit_diagnostics.DiagnosticTenantMissing):
        audit_diagnostics.store_row({"tenant_id": None, "reference": "5F2B-9C1D"})
    with pytest.raises(audit_diagnostics.DiagnosticTenantMissing):
        audit_diagnostics.by_reference("5F2B-9C1D")


def test_cr067_a1__there_is_no_foreign_key_between_the_two_records():
    """CR-067 §3: they join on a VALUE, because their lifetimes differ.

    A foreign key would make one hostage to the other's retention — the sweep
    would be refused, or a permanent audit row would cascade away with a pruned
    diagnostic.

    RED-PROVED: with `audit_log = models.ForeignKey("audit.AuditLog", …)` added
    to the model this failed with

        AssertionError: ErrorDiagnostic declares a foreign key (audit_log). The
        two records have different lifetimes and CR-067 §3 forbids one.
    """
    relations = [f.name for f in ErrorDiagnostic._meta.get_fields() if f.is_relation]
    assert not relations, (
        f"ErrorDiagnostic declares a foreign key ({', '.join(relations)}). The two "
        "records have different lifetimes and CR-067 §3 forbids one."
    )
    from apps.audit.models import AuditLog

    audit_relations = [f.name for f in AuditLog._meta.get_fields() if f.is_relation]
    assert not audit_relations


def test_cr067_a1__the_reference_is_formed_exactly_as_the_front_end_forms_it():
    """`5f2b9c1d3e…` → `5F2B-9C1D`. One rule, two implementations, one shape.

    `07-frontend/src/api/client.ts` has the identical formatter; the two are a
    pair by design and this pins the server half to the cases that file names.

    RED-PROVED (measured): with the `.upper()` dropped this failed with

        AssertionError: assert '5f2b-9c1d' == '5F2B-9C1D'
    """
    assert diagnostics.support_ref("5f2b9c1d3e4f5a6b") == "5F2B-9C1D"
    assert diagnostics.support_ref("5F2B9C1D") == "5F2B-9C1D"
    assert diagnostics.support_ref("5f2b-9c1d") == "5F2B-9C1D"
    assert diagnostics.support_ref("5f2b9c") == diagnostics.SUPPORT_REF_ABSENT
    assert diagnostics.support_ref(None) == diagnostics.SUPPORT_REF_ABSENT


# ══ A3 + A4 · THE SEEDING PLANT, AND THE JOIN ══════════════════════════════
def _fake_every_seam(monkeypatch, *, raisers=None):
    """One-line fakes on every block's seam — the CR-039 test's helper, reused.

    The real seeders plant a whole estate; what is under test here is what the
    ORCHESTRATOR records when one of them raises.
    """
    from importlib import import_module

    raisers = raisers or {}
    for spec in sample_data.SAMPLE_MODULES:
        services = import_module(f"apps.{spec.module}.services")

        def make(key=spec.key):
            def fake(actor):
                if key in raisers:
                    raise raisers[key]()
                return 1

            return fake

        monkeypatch.setattr(services, spec.seam, make(), raising=False)


def _billing_bills_block() -> str:
    """The block the 2026-09-02 failure stopped on — *Bills, first month*."""
    for spec in sample_data.SAMPLE_MODULES:
        if spec.module == "billing":
            return spec.key
    raise AssertionError("the sample set has no billing block")


def test_cr067_a3_a4__a_failed_seeding_block_writes_both_records_under_one_reference(
    monkeypatch, settings, audit_rows
):
    """Task A3's done-when (*"step 8's failure produces a complete record"*) and
    task A4's (*"the two join, proved on a real failure"*), in one test.

    The failure is the real one: `StorageNotConfigured` out of the document
    store, raised by the billing block, with the deployment's storage settings
    in exactly the state the Product Owner's host was in.

    RED-PROVED (measured): with the `capture()` call removed from
    `seed_sample_data`'s per-block `except`, this failed with

        AssertionError: the sample.block_failed audit row carries no reference,
        so nothing joins the permanent record to the technical one (CR-067 task
        A4)
        assert None
    """
    settings.DOCUMENT_STORAGE_BACKEND = "aws_s3"
    settings.DOCUMENT_STORAGE_BUCKET = ""
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = False

    def raise_storage():
        return document_storage.StorageNotConfigured(
            f"DOCUMENT_STORAGE_BUCKET is not set; account {BAIT_ACCOUNT} has no bill"
        )

    block = _billing_bills_block()
    _fake_every_seam(monkeypatch, raisers={block: raise_storage})

    tenant, _ = provisioned_tenant()
    actor = admin_actor()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(actor)
        rows = [
            row
            for row in _block_failed_rows(audit_rows)
            if (row["after"] or {}).get("block") == block.split(":", 1)[1]
        ]
        assert rows, "the failing block wrote no sample.block_failed row"
        reference = (rows[0]["after"] or {}).get("reference")
        assert reference, (
            "the sample.block_failed audit row carries no reference, so nothing "
            "joins the permanent record to the technical one (CR-067 task A4)"
        )
        record = audit_diagnostics.by_reference(reference)
        assert record is not None, "the reference on the audit row leads nowhere"
        assert record.exception_type == "StorageNotConfigured"
        assert record.component == block
        assert record.step and record.step_total == len(sample_data.SAMPLE_MODULES)
        # A3's "complete": the settings that reproduce it, registered by the
        # module that owns the exception and not by the seeding plant.
        assert record.settings_in_force["DOCUMENT_STORAGE_BACKEND"] == "aws_s3"
        assert record.settings_in_force["DOCUMENT_STORAGE_BUCKET"] == ""
        assert record.settings_in_force["DOCUMENT_STORAGE_ALLOW_FILESYSTEM"] is False
        # And the permanent row still holds NOTHING private.
        assert BAIT_ACCOUNT not in repr(rows[0]["after"])
        assert BAIT_ACCOUNT not in _stored_text(record)


def _block_failed_rows(audit_rows):
    """The `sample.block_failed` rows the run wrote, from the CAPTURE SINK.

    ⚠ NOT FROM `AuditLog`. `tests/test_us_ten_helpers.py` installs an autouse
    fixture that swaps the BE-03 sink for a list — *"capture, don't fake
    storage"* — so nothing this suite writes reaches the table. A first draft
    that queried the model found zero rows and would have read as "the audit row
    was never written" rather than "this suite does not store them".
    """
    return [row for row in audit_rows if row["action"] == sample_data.AUDIT_BLOCK_FAILED]


# ══ A5 · RETENTION, AND THE HONEST EXPIRED STATE ═══════════════════════════
def test_cr067_a5__the_retention_window_is_ninety_days_and_is_a_setting(settings):
    """CR-067 task A5: *"defaulting to 90 days and configurable"*.

    `OQ-1390` asks whether 90 is right and which regime a diagnostic falls
    under. It is OPEN, and nothing in the code guesses it — the answer moves
    this setting, which is why this test asserts the DEFAULT and the fact that
    it is settable rather than a number baked into a function.
    """
    assert django_settings.DIAGNOSTIC_RETENTION_DAYS == 90
    assert diagnostics.retention_days() == 90
    settings.DIAGNOSTIC_RETENTION_DAYS = 30
    assert diagnostics.retention_days() == 30


def test_cr067_a5__expires_at_is_stamped_at_write_not_computed_at_read(settings):
    """Shortening the setting must not retroactively expire what somebody is
    reading, and lengthening it must not resurrect what they were told was gone.

    RED-PROVED (measured): with `expires_at` removed from
    `apps/audit/diagnostics.STORED_FIELDS` — the only way the column could stop
    being stamped and start being derived — the write itself failed with

        django.db.utils.IntegrityError: NOT NULL constraint failed:
        error_diagnostics.expires_at

    which is the shape of the proof: there is no version of this product in
    which the expiry is computed at read time, because the column will not
    accept a row without it.
    """
    settings.DIAGNOSTIC_RETENTION_DAYS = 90
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        reference = diagnostics.capture(
            error_code="SD-UNEXPECTED",
            exception=_bait_exception(),
            component="billing:seed_sample_records",
        )
        row = audit_diagnostics.by_reference(reference)
        stamped = row.expires_at
        assert (stamped - row.created_at).days == 90
        settings.DIAGNOSTIC_RETENTION_DAYS = 1
        row.refresh_from_db()
        assert row.expires_at == stamped


def test_cr067_a5__an_expired_record_is_gone_and_its_audit_row_still_reads(monkeypatch, audit_rows):
    """Task A5's own done-when: *"an expired record is gone and its audit row
    still reads correctly without it"*.

    ⚠ **THIS IS THE TEST FOR THE BARGAIN CR-067 STRUCK.** A year later the
    permanent row still says what failed, under which code, in the fixed
    catalogue sentence — it simply cannot be rebuilt into a test any more. The
    expired state has to be HONEST rather than broken, so this asserts what the
    audit row still holds as hard as it asserts what the diagnostic no longer
    does.

    RED-PROVED: with `sweep_expired` deleting by `created_at` rather than
    `expires_at`, a record written seconds ago was swept and this failed with

        AssertionError: a record inside its retention was swept
    """
    block = _billing_bills_block()
    _fake_every_seam(monkeypatch, raisers={block: lambda: SeederBlewUp("boom " + BAIT_ACCOUNT)})
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        rows = _block_failed_rows(audit_rows)
        assert rows
        reference = rows[0]["after"]["reference"]
        assert audit_diagnostics.by_reference(reference) is not None

        # Inside the window: nothing is swept.
        untouched = audit_diagnostics.sweep_expired([tenant.id])
        assert untouched["removed"] == 0, "a record inside its retention was swept"
        assert audit_diagnostics.by_reference(reference) is not None

        # Ninety-one days later: swept.
        later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=91)
        result = audit_diagnostics.sweep_expired([tenant.id], now=later)
        assert result["removed"] == 1
        assert audit_diagnostics.by_reference(reference) is None

    # AND THE PERMANENT ROW IS UNCHANGED AND STILL READS AS A SENTENCE.
    after = _block_failed_rows(audit_rows)[0]["after"]
    assert after["reference"] == reference
    assert after["error_code"]
    assert after["meaning"], "the permanent row lost its plain-words sentence"
    assert BAIT_ACCOUNT not in repr(after)
    # And the sentence for the missing half exists in exactly one place.
    assert audit_diagnostics.HAS_EXPIRED


def test_cr067_a5__a_dry_run_removes_nothing_and_says_what_it_would(monkeypatch):
    """A sweep that cannot be previewed is a sweep nobody runs on purpose."""
    block = _billing_bills_block()
    _fake_every_seam(monkeypatch, raisers={block: lambda: SeederBlewUp("boom")})
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=91)
        preview = audit_diagnostics.sweep_expired([tenant.id], now=later, dry_run=True)
        assert preview["removed"] == 1 and preview["dry_run"] is True
        assert ErrorDiagnostic.objects.filter(tenant_id=tenant.id).count() == 1


def test_cr067_a5__one_tenants_failure_does_not_stop_the_sweep(monkeypatch):
    """BR-TEN-074. Named, isolated, and the rest still swept.

    ⚠ The isolation this proves is the PYTHON half. The POSTGRES half — that a
    refused statement does not poison the whole sweep — is what the nested
    `transaction.atomic()` in `sweep_expired` is for, and hard-won law 14 is
    explicit that **the default suite cannot show it**: `config/settings/test.py`
    hardcodes in-memory SQLite, which has no aborted-transaction state. This
    file is run against a live PostgreSQL in the lane report for that reason.
    """
    block = _billing_bills_block()
    _fake_every_seam(monkeypatch, raisers={block: lambda: SeederBlewUp("boom")})
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
    later = dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=91)
    broken = SimpleNamespace()  # not a uuid — the context enter will refuse it
    result = audit_diagnostics.sweep_expired([broken, tenant.id], now=later)
    assert result["removed"] == 1
    assert len(result["failed"]) == 1


# ══ §5 · THE ACCEPTANCE TEST, WRITTEN FROM THE RECORD AND NOTHING ELSE ═════
def test_cr067_a5__section_5(monkeypatch, settings, audit_rows):
    """**CR-067 §5: could somebody holding ONLY the diagnostic record write a
    failing test?** This is that test, and it is generated from the record.

    The setup below reads `record.settings_in_force` and `record.exception_type`
    and uses nothing else — no knowledge of what the seeder was doing, no second
    conversation with the reporter. If this ever needs a fact the record does
    not hold, **the record is incomplete and the record is what gets fixed**.

    RED-PROVED (measured), twice, and each failure lands in a different one of
    the four steps below — which is the point of writing it this way:

      * with the record's `exception_type` written as
        `f"{type(exception).__name__}: {exception}"`, step 3 could not resolve
        the class it names and failed with

            AttributeError: module 'apps.tenancy.document_storage' has no
            attribute 'StorageNotConfigured: nowhere to put it'

        — a diagnostic that mixes the type with the message is not merely
        leaky, it is **unusable**, and that is the cheapest argument for the
        redaction rule there is;
      * with the seeding plant not capturing at all, step 1 produced no record
        and this failed at `assert record is not None` with

            assert None is not None
    """
    # ── 1 · reproduce the deployment of 2026-09-02 and let it break ────────
    settings.DOCUMENT_STORAGE_BACKEND = "aws_s3"
    settings.DOCUMENT_STORAGE_BUCKET = ""
    settings.DOCUMENT_STORAGE_ALLOW_FILESYSTEM = False
    block = _billing_bills_block()
    _fake_every_seam(
        monkeypatch,
        raisers={block: lambda: document_storage.StorageNotConfigured("nowhere to put it")},
    )
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        sample_data.seed_sample_data(admin_actor())
        reference = _block_failed_rows(audit_rows)[0]["after"]["reference"]
        record = audit_diagnostics.by_reference(reference)
    assert record is not None

    # ── 2 · forget everything except the record ───────────────────────────
    held = {
        "exception_type": record.exception_type,
        "exception_module": record.exception_module,
        "settings_in_force": dict(record.settings_in_force),
    }

    # ── 3 · rebuild the failing test FROM `held`, exactly as CR-067 §5 writes it
    import importlib

    module = importlib.import_module(held["exception_module"])
    failure = getattr(module, held["exception_type"])
    for name, value in held["settings_in_force"].items():
        setattr(django_settings, name, value)

    with pytest.raises(failure):
        document_storage.backend()

    # ── 4 · and the record says the same three things §5 prints ───────────
    assert held["settings_in_force"]["DOCUMENT_STORAGE_BACKEND"] == "aws_s3"
    assert held["settings_in_force"]["DOCUMENT_STORAGE_BUCKET"] == ""
    assert held["settings_in_force"]["DOCUMENT_STORAGE_ALLOW_FILESYSTEM"] is False
    assert held["exception_type"] == "StorageNotConfigured"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-067 §5 (the acceptance test) + §6 tasks A1–A5 (12-governance/11-change-requests.md); shared law BR-AUD-002/006/007, CLAUDE.md hard rules 1 and 7, hard-won laws 7 and 14
# generated: 2026-09-02 by the CR-067 backend lane
# checklist: A✔ B=deferred(tests draw nothing) C✔ D=deferred(no endpoint in this half) E=deferred(same) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: run on real PostgreSQL 16 per hard-won law 14 — see the lane report for the command and the counts
# exceptions: the PostgreSQL half of `sweep_expired`'s SAVEPOINT cannot be shown by the default suite (in-memory SQLite has no aborted-transaction state); it is stated in the test's own docstring rather than left implied
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

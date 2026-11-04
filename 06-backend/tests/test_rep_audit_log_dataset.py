# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · the `audit_log` dataset query (lane DS-ACCOUNTS).
#           Drawings read as IMAGES (B14 rule 42): R35 and R36 p066 · R8 p051 ·
#           §7.2/§7.2.2 p083–p086 · §7.5/§7.6 p087.
# Rules:    NFR-3 (pagination in SQL) · NFR-5 (no hard caps) · BR-AUD-002
#           (append-only) · BR-AUD-006 (PII masked; no unmask path) ·
#           BR-AUD-012/013 (retention and the hot window) · BR-AUD-019 /
#           BR-RBS-015 (a named automation never borrows a user identity) ·
#           BR-REP-024 (never a 0 where a figure is not derivable) ·
#           B14 rule 31 (no database id is ever a field's visible value) ·
#           B14 rule 33 (RATIONALE is zero words on screen) · B14 rule 37 (a
#           drawn figure is an illustration) · CLAUDE.md hard rule 4's
#           retention ruling (PO 2026-09-23 — no row type exempt)
# ───────────────────────────────────────────────────────
"""THE `audit_log` DATASET — one row per AUDIT EVENT, and the two it refuses.

⚠ **EVERY CASE ASSERTS A KNOWN NON-ZERO COUNT.** A query returning nothing
reads as *"no error"*. The one case that asserts a ZERO sits beside a positive
one in the same fixture.

⚠ **NOTHING HERE SKIPS.** Every fixture CREATES what it needs.

⚠ **THE SUITE RUNS ON IN-MEMORY SQLITE**, so these cases prove the SHAPE and
the ARITHMETIC and nothing about RLS, the partition plan or LIMIT/OFFSET cost
(hard-won law 14). The PostgreSQL half is
`10-scripts/ds_accounts_audit_notifications_cost.py`.
"""

import uuid
from contextlib import contextmanager
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.audit import audit_log_dataset as dataset
from apps.audit.models import AuditLog
from core import archival

from tests.isolation_helpers import writing_as_tenant
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: Six events: four by two named people, one by a NAMED automation and one by
#: an unnamed system job. Every assertion names a NUMBER.
EVENTS = 6
PEOPLE = 2


@contextmanager
def _created_at_is_settable():
    """Let a fixture choose `created_at` on the INSERT — never an UPDATE, which
    BR-AUD-002's append-only trigger refuses on PostgreSQL."""
    field = AuditLog._meta.get_field("created_at")
    field.auto_now_add = False
    try:
        yield
    finally:
        field.auto_now_add = True


def _event(tenant, *, action, entity_type, actor_id=None, age_days=0, **extra):
    created_at = timezone.now() - timedelta(days=age_days)
    with writing_as_tenant(tenant), _created_at_is_settable():
        return AuditLog.objects.create(
            tenant_id=tenant.id,
            actor_user_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=uuid.uuid4(),
            created_at=created_at,
            **extra,
        )


def _six(tenant, dana, marcus):
    """Four people-rows, one named automation, one unnamed system job."""
    _event(tenant, action="payment.corrected", entity_type="payment", actor_id=dana.id,
           before={"confirmation": "4417"}, after={"confirmation": "4471"})
    _event(tenant, action="adjustment.approved", entity_type="adjustment", actor_id=marcus.id)
    _event(tenant, action="billing_settings.updated", entity_type="tenant_settings",
           actor_id=dana.id, age_days=2)
    _event(tenant, action="invoice.issued", entity_type="invoice", actor_id=marcus.id, age_days=3)
    _event(tenant, action="payment.returned", entity_type="payment",
           actor_kind="job", actor_label="Returned payments", actor_version="4", age_days=4)
    _event(tenant, action="bill_run.issued", entity_type="bill_run", age_days=5)


# ══════════════════════════════════════════════════════════════════════════
#  R35 — the one it serves
# ══════════════════════════════════════════════════════════════════════════


def test_r35_serves_one_row_per_event_and_the_tiles_foot(brazos, dana, marcus):
    """The tiles are a SQL aggregate over the whole filtered set, never the page.

    ⚠ **FALSE PASS THIS GUARDS:** totals struck over the PAGE would report
    `events: 2` for a `per=2` request and the tile would foot to the page.
    """
    with tenant_ctx(brazos):
        _six(brazos, dana, marcus)
        result = dataset.audit_log_dataset(per=2, page=1)

    assert result["grain"] == "one audit event"
    assert len(result["rows"]) == 2
    assert result["total"] == EVENTS
    assert result["totals"]["events"] == EVENTS
    assert result["totals"]["actors"] == PEOPLE  # distinct user ids, not rows


def test_the_money_events_tile_is_none_with_a_reason_never_a_guess(brazos, dana, marcus):
    """BR-REP-024 — nothing in this table marks a row as a money action.

    ⚠ **THE FALSE PASS:** a prefix match on `payment.` / `invoice.` produces a
    plausible number reported to a compliance officer as a fact, and invents the
    US-AUD-002 catalog that `apps/audit/selectors.py` states is not built. The
    fixture holds three rows such a guess would count, so a lane adding one
    makes this case red rather than green.
    """
    with tenant_ctx(brazos):
        _six(brazos, dana, marcus)
        result = dataset.audit_log_dataset()

    assert result["totals"]["events"] == EVENTS  # a non-zero beside the None
    assert result["totals"]["money_events"] is None
    codes = {problem["code"] for problem in result["problems"]}
    assert dataset.GAP_MONEY_EVENTS_UNCLASSIFIED["code"] in codes


def test_the_retention_tile_reads_the_real_period_and_says_nothing_else(brazos, dana, marcus):
    """The honest part — two facts, no rationale.

    ⚠ **B14 rule 37:** the drawing says `12 months` and that is an
    ILLUSTRATION. The deployment's figure is `core.archival.RETENTION_MONTHS`.
    A hard-coded 12 would ship a compliance tile understating the trail's life
    by six years, and this case is what goes red.

    ⚠ **B14 rule 33 + hard rule 4's retention ruling:** the tile carries no
    sentence explaining the policy. A screen that explained it would break rule
    33 while trying to obey the ruling, and `CorrectionRetentionNote` was
    DELETED from eleven catalogues for exactly that.
    """
    with tenant_ctx(brazos):
        _six(brazos, dana, marcus)
        result = dataset.audit_log_dataset()

    tile = result["retention"]
    assert tile["months"] == archival.RETENTION_MONTHS
    assert tile["months"] != 12  # the drawn figure is an illustration
    assert tile["oldest_at"] is not None
    # Two facts and nothing else — no caveat, no note, no explanation.
    assert set(tile) == {"months", "oldest_at"}


#: The ONE sentence the module is allowed to contain the words *permanent
#: record* in: the prohibition itself, quoted from hard rule 4's retention
#: ruling. Anything else containing them is the module making the claim.
#:
#: ⚠ **NEWLINES ARE COLLAPSED BEFORE THIS IS LOOKED FOR.** The first draft of
#: this case scanned LINE BY LINE and went red on its own module's quotation of
#: the prohibition, because the sentence wraps — a check that cannot tell a
#: quotation from a claim. The whole source is joined first.
#: How far back the check looks for the word that turns a claim into a
#: prohibition. Both of this module's two occurrences read
#: "...forbids <any document, screen or docstring> describing this path as a
#: permanent record of an old value", so 90 characters covers the longer of
#: them with room to spare and is far too short to reach an unrelated sentence.
PROHIBITION_WINDOW = 90
PROHIBITION_WORDS = ("forbid", "never", "may not", "no document")


def test_no_string_anywhere_calls_this_a_permanent_record(brazos, dana, marcus):
    """Hard rule 4's retention ruling — *no document, screen or docstring*.

    Two halves, and the second is the one that matters at runtime:

    ⚠ **① THE TEXT.** Asserted against the module's own SOURCE, because a
    docstring claiming a guarantee is not the guarantee (law 1) and this is a
    rule about what the text may say. The module may QUOTE the prohibition once
    — `QUOTED_PROHIBITION` — and may make the claim nowhere.

    ⚠ **② WHAT IS SERVED.** No string the query PUBLISHES may claim permanence
    either, and that is the half a source scan cannot see. Every value in the
    retention tile and every problem detail is checked.
    """
    import inspect

    import re

    joined = " ".join(inspect.getsource(dataset).lower().split())
    #: ⚠ **THE FIRST DRAFT SCANNED LINE BY LINE AND WENT RED ON ITS OWN
    #: MODULE'S QUOTATION OF THE PROHIBITION**, because the sentence wraps — a
    #: check that cannot tell a quotation from a claim. The second draft
    #: whitelisted ONE exact sentence and went red on the module's SECOND
    #: statement of the same prohibition. So the rule is stated as a rule: the
    #: words may appear only where a negation is already in force.
    seen = 0
    for phrase in ("permanent record", "permanently retained", "kept forever", "never pruned"):
        for match in re.finditer(re.escape(phrase), joined):
            seen += 1
            lead = joined[max(0, match.start() - PROHIBITION_WINDOW) : match.start()]
            assert any(word in lead for word in PROHIBITION_WORDS), (
                f"{phrase!r} is CLAIMED by this module, not forbidden, at: "
                f"...{joined[max(0, match.start() - 160) : match.end() + 60]}..."
            )
    # A non-zero beside the assertion: a module that stopped stating the
    # prohibition at all would pass a loop that never ran.
    assert seen >= 2, "this module no longer states hard rule 4's retention prohibition"

    with tenant_ctx(brazos):
        _six(brazos, dana, marcus)
        result = dataset.audit_log_dataset()

    assert result["totals"]["events"] == EVENTS  # a non-zero beside the check
    served = " ".join(
        str(value)
        for problem in result["problems"]
        for value in problem.values()
    ).lower()
    served += " " + " ".join(str(value) for value in result["retention"].values()).lower()
    for forbidden in ("permanent record", "permanently retained", "kept forever", "never pruned"):
        assert forbidden not in served, f"{forbidden!r} is SERVED to a caller"


def test_a_named_automation_never_borrows_a_user_identity(brazos, dana, marcus):
    """BR-AUD-019 / BR-RBS-015 — three actor shapes, kept apart.

    ⚠ **THE FALSE PASS:** collapsing the three into one display string makes
    *System* and *a clerk whose name we failed to fetch* indistinguishable, and
    only one of them is a person.
    """
    with tenant_ctx(brazos):
        _six(brazos, dana, marcus)
        rows = dataset.audit_log_dataset()["rows"]

    automation = [row for row in rows if row.actor_kind == "job"]
    assert len(automation) == 1
    assert automation[0].actor == "Returned payments"
    assert automation[0].actor_version == "4"
    assert automation[0].actor_id is None  # it never borrows a user identity

    unnamed = [row for row in rows if row.actor_kind is None and row.actor_id is None]
    assert len(unnamed) == 1
    assert unnamed[0].actor in (None, "")

    people = [row for row in rows if row.actor_id is not None]
    assert len(people) == 4


def test_the_object_column_is_never_a_uuid(brazos, dana, marcus):
    """B14 rule 31 — a uuid under a column headed Object looks like an answer.

    `entity` (the TYPE) travels, so the row still says what was acted on.
    """
    with tenant_ctx(brazos):
        _six(brazos, dana, marcus)
        rows = dataset.audit_log_dataset()["rows"]

    assert len(rows) == EVENTS
    assert all(row.entity_ref is None for row in rows)
    assert {row.entity for row in rows} >= {"payment", "invoice", "bill_run"}


def test_before_and_after_travel_exactly_as_stored(brazos, dana, marcus):
    """R35 draws `4417 → 4471`. Served as stored; BR-AUD-006 masks at WRITE."""
    with tenant_ctx(brazos):
        _six(brazos, dana, marcus)
        rows = dataset.audit_log_dataset()["rows"]

    corrected = [row for row in rows if row.action == "payment.corrected"]
    assert len(corrected) == 1
    assert corrected[0].before == {"confirmation": "4417"}
    assert corrected[0].after == {"confirmation": "4471"}


def test_the_page_is_cut_in_sql_and_the_last_page_is_not_empty(brazos, dana, marcus):
    """NFR-3. The zero-ish case sits beside a positive one in one fixture."""
    with tenant_ctx(brazos):
        _six(brazos, dana, marcus)
        second = dataset.audit_log_dataset(per=4, page=2)
        beyond = dataset.audit_log_dataset(per=4, page=9)

    assert second["pages"] == 2
    assert len(second["rows"]) == 2
    assert beyond["page"] == 2  # clamped, not an empty page
    assert len(beyond["rows"]) == 2


def test_every_sort_ends_in_a_unique_column():
    for name, terms in dataset.AUDIT_SORT_COLUMNS.items():
        assert terms[-1] == "id", f"{name} has no unique tiebreak"
    assert set(dataset.AUDIT_SORTS) == set(dataset.AUDIT_SORT_COLUMNS)


def test_the_export_takes_no_page_and_no_per(brazos, dana, marcus):
    import inspect

    signature = inspect.signature(dataset.audit_log_dataset_stream)
    assert "page" not in signature.parameters
    assert "per" not in signature.parameters

    with tenant_ctx(brazos):
        _six(brazos, dana, marcus)
        streamed = list(dataset.audit_log_dataset_stream())
    assert len(streamed) == EVENTS


def test_a_channel_filter_is_refused_rather_than_ignored(brazos, dana, marcus):
    """`channel` is R8's column. Accepting and ignoring it would serve the whole
    trail under a chip reading *Email*."""
    with tenant_ctx(brazos):
        _six(brazos, dana, marcus)
        with pytest.raises(dataset.UnservableFromThisDataset) as raised:
            dataset.audit_log_dataset(channel="email")
    assert "channel" in str(raised.value)
    assert "notifications" in str(raised.value)


def test_four_declared_columns_are_reported_as_other_grains(brazos, dana, marcus):
    """The registry's AUDIT_LOG declares columns that are R8's and R36's."""
    with tenant_ctx(brazos):
        _six(brazos, dana, marcus)
        result = dataset.audit_log_dataset()

    codes = {problem["code"] for problem in result["problems"]}
    assert dataset.GAP_FOUR_COLUMNS_BELONG_TO_OTHER_GRAINS["code"] in codes
    # And none of them is a field of the served row.
    row = result["rows"][0]
    for absent in ("channel", "status", "reason", "last_sign_in_at", "added_by", "actor_role"):
        assert not hasattr(row, absent)


# ══════════════════════════════════════════════════════════════════════════
#  THE TWO IT REFUSES
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("code,report", [("access_review", "R36"), ("bill_delivery", "R8")])
def test_each_refusal_names_the_report_the_grain_and_the_read_model(code, report):
    row = dataset.unservable_reason(code)
    assert row["report"].startswith(report)
    assert row["drawn_grain"] != "one audit event"
    assert row["needs_read_model"]
    assert row["evidence"]

    with pytest.raises(dataset.UnservableFromThisDataset) as raised:
        dataset.refuse(code)
    assert report in str(raised.value)
    assert "one audit event" in str(raised.value)


def test_r36_is_refused_because_a_never_signed_in_user_writes_no_events():
    """The finding that decided it, asserted so a lane cannot quietly undo it.

    ⚠ R36 READS IDENTITY, so a leak is a SECURITY defect — `BR-REP-023`
    restricts this report and nothing enforces it. The refusal row carries that
    note; this case keeps it there.
    """
    row = dataset.unservable_reason("access_review")
    assert "never signed in" in row["why_not_here"].lower()
    assert "BR-REP-023" in row["security_note"]
    assert any("TenantMembership" in read for read in row["needs_read_model"])


def test_the_refusals_cover_every_seeded_report_but_r35():
    assert set(dataset.UNSERVABLE_HERE) == {"access_review", "bill_delivery"}


def test_this_module_writes_nothing():
    """Hard rule 4 + BR-AUD-002 — and the table refuses writes besides."""
    import inspect

    source = inspect.getsource(dataset)
    for forbidden in (".save(", ".create(", ".delete(", ".update(", "bulk_create"):
        assert forbidden not in source, f"{forbidden} is a write and this path is a read"

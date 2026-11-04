# ── Trace ──────────────────────────────────────────────
# Epics:    EP-LED-02 (chart of accounts & GL mapping) — CR-060 **C10**, T11
# Rules:    BR-LED-014 (where GL mappings live — AMENDED by C10: and WHO MAY
#           WRITE THEM through one screen) · BR-TEN-013 / B1 (no module touches
#           another module's ORM) · BR-BIL-010 · CLAUDE.md hard-won law 14
# ───────────────────────────────────────────────────────
"""CR-060 C10 — **one screen, one save, several owners underneath.**

C10's three proofs, verbatim: *"One save writes across modules · a partial
failure writes NOTHING · a test asserting no cross-module ORM write, which is
the rule the orchestration exists to respect."*

⚠ **AND ITS FOURTH LINE ASKS FOR A REAL DATABASE:** *"⚠ Prove the
partial-failure case on PostgreSQL (hard-won law 14)."* **These eight cases pass
on PostgreSQL 16.13**, and the command is below.

⚠ **WHAT THE POSTGRESQL RUN DID AND DID NOT SHOW — MEASURED, AND IT CONTRADICTS
THE FIRST DRAFT OF THIS FILE.** The expected story was law 14's: SQLite has no
aborted-transaction state, so a broken all-or-nothing save would pass the
default suite and fail on a real database. **That is not what happens here, and
saying so is worth more than the story.**

  * **The sabotage that was expected to bite did not.** Wrapping each half in
    its own nested `atomic()` — the tidy-looking mistake — **passed on
    PostgreSQL AND on SQLite**. Django's nested `atomic()` is a savepoint that
    rolls back with its parent; it cannot outlive it. A check that cannot
    distinguish pass from fail is worse than no check (DEF-182), so the claim
    that motivated it is corrected in `gl_mapping_save.py` rather than left
    standing.
  * **The sabotage that DOES bite is the simpler one:** remove the single
    `transaction.atomic()` and the role half commits behind a refused service
    half. It fails on **both** databases, verbatim:

        AssertionError: a refused service write left the ROLE half committed —
        the save is not all-or-nothing
        assert '01a06404-eaf5-7491-8948-0663f5def046' == None

**So law 14's specific trap does not apply to this code** — it catches no
database error and continues, which is the shape that law is about. The
PostgreSQL run is still worth having, for the smaller and honest reason that it
is the database this product runs on and C10 asked for it by name.

**HOW THE POSTGRESQL RUN WAS DONE**, so the next lane can repeat it rather than
take this on trust:

    /usr/lib/postgresql/16/bin/pg_ctl -D /tmp/pgdata_cr060 -o "-p 5433" start
    DATABASE_URL=postgres://postgres@127.0.0.1:5433/cr060 \\
      python3 -m pytest tests/test_cr060_c10_gl_mapping_save.py \\
      -o DJANGO_SETTINGS_MODULE=config.settings.local

⚠ **`-o` ON THE COMMAND LINE, NOT AN ENVIRONMENT VARIABLE.** `pyproject.toml`'s
`[tool.pytest.ini_options]` sets `DJANGO_SETTINGS_MODULE` too and **the ini
wins** — a run that exports it goes green on SQLite while reporting itself as
the PostgreSQL proof, which is law 14's trap wearing the costume of the check
for it. That false pass is recorded in the human-review ledger's CR-061 row and
is repeated here because it is the easiest mistake on this path.

⚠ **PROVED RED FIRST (law 7).** Before `apps/ledger/gl_mapping_save.py` existed:

    ModuleNotFoundError: No module named 'apps.ledger.gl_mapping_save'

and the partial-failure case was proved RED against the orchestrator with its
single transaction removed — on PostgreSQL and again on SQLite — with the
message quoted above.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from apps.ledger import chart, chart_api, gl_mapping_save
from apps.ledger import models as ledger_models
from apps.ledger import selectors as ledger_selectors
from apps.ledger import services as ledger_services
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx

pytestmark = pytest.mark.django_db

REPO = pathlib.Path(__file__).resolve().parents[2]


def an_account(actor, *, code, name, type_="asset"):
    return ledger_services.create_account(
        actor, code=code, name=name, type=type_, designation=None
    )


def a_service_row(tenant):
    """The tenant's first enabled service row — the half tenancy owns."""
    return (
        tenancy_models.TenantService.objects.filter(tenant_id=tenant.id)
        .select_related("service")
        .order_by("service__code")
        .first()
    )


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 1 — one save writes across modules
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_c10__one_save_writes_both_halves(brazos, dana):
    """A role in the LEDGER's table and a revenue account in TENANCY's, in one
    call, from what will be one press of one button."""
    with tenant_ctx(brazos):
        row = a_service_row(brazos)
        assert row is not None, "the tenant must sell something for this to mean anything"
        # A free designation: clear whatever holds it, so the re-point is the
        # only thing under test rather than the uniqueness rule.
        holder = ledger_models.LedgerAccount.objects.filter(
            tenant_id=brazos.id, designation=chart.BANK_FEES, deleted_at__isnull=True
        ).first()
        if holder is not None:
            ledger_services.update_account(dana, account_id=holder.id, designation=None)
        role_account = an_account(dana, code="9101", name="Bank charges (ours)", type_="expense")
        revenue_account = an_account(dana, code="9102", name="Water sales (ours)", type_="revenue")

        result = gl_mapping_save.save_gl_mappings(
            dana,
            {
                "roles": [
                    {"designation": chart.BANK_FEES, "account_id": role_account["account_id"]}
                ],
                "services": [
                    {
                        "service_code": row.service.code,
                        "revenue_account_id": revenue_account["account_id"],
                    }
                ],
            },
        )

        assert result["roles"] == [{"designation": chart.BANK_FEES, "changed": ["designation"]}]
        assert result["services"] == [
            {"service_code": row.service.code, "changed": ["revenue_account_id"]}
        ]
        # Both halves, read back from their OWN tables.
        assert ledger_selectors.designation_map()[chart.BANK_FEES] is not None
        row.refresh_from_db()
        assert str(row.revenue_account_id) == revenue_account["account_id"]


def test_cr060_c10__it_reports_what_changed_not_what_it_was_sent(brazos, dana):
    """Saving a value that is already set changes nothing and says so.

    A screen that reported *"13 roles saved"* over a payload where twelve were
    already correct tells a clerk something happened that did not, and the audit
    rows underneath would disagree with it.
    """
    with tenant_ctx(brazos):
        row = a_service_row(brazos)
        account = an_account(dana, code="9103", name="Water sales (ours)", type_="revenue")
        payload = {
            "roles": [],
            "services": [
                {"service_code": row.service.code, "revenue_account_id": account["account_id"]}
            ],
        }
        first = gl_mapping_save.save_gl_mappings(dana, payload)
        second = gl_mapping_save.save_gl_mappings(dana, payload)
        assert first["services"][0]["changed"] == ["revenue_account_id"]
        assert second["services"][0]["changed"] == []


def test_cr060_c10__an_empty_payload_is_a_no_op_not_a_refusal(brazos, dana):
    """A clerk who opens the page, changes nothing and presses Save has done
    nothing wrong."""
    with tenant_ctx(brazos):
        assert gl_mapping_save.save_gl_mappings(dana, {}) == {"roles": [], "services": []}


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 2 — a partial failure writes NOTHING  ⚠ THE POSTGRESQL CASE
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_c10__a_refused_service_half_undoes_the_role_half(brazos, dana):
    """**THE CASE C10 NAMES, and the one law 14 says must run on PostgreSQL.**

    The service half is refused — an unknown service code — AFTER the role half
    has already written. On a correct implementation nothing is left behind.

    ⚠ **PROVED RED BY REMOVING THE SINGLE `transaction.atomic()`**, which is the
    sabotage that actually discriminates: this case then fails on PostgreSQL 16
    AND on SQLite with the role half committed. A nested `atomic()` per half —
    the mistake this file first assumed — does NOT break it, and the module
    docstring records that measurement rather than the assumption.
    """
    with tenant_ctx(brazos):
        holder = ledger_models.LedgerAccount.objects.filter(
            tenant_id=brazos.id, designation=chart.BANK_FEES, deleted_at__isnull=True
        ).first()
        if holder is not None:
            ledger_services.update_account(dana, account_id=holder.id, designation=None)
        before = ledger_selectors.designation_map().get(chart.BANK_FEES)
        account = an_account(dana, code="9104", name="Bank charges (ours)", type_="expense")

        # ⚠ `NotFoundError` is NOT an `ApiError` subclass in this repo — the
        # 404-never-403 denial is its own class (core/errors.py:176). Naming
        # only `ApiError` here would let a refusal escape the `raises` and
        # fail the case for the wrong reason.
        with pytest.raises((errors.ApiError, errors.NotFoundError)):
            gl_mapping_save.save_gl_mappings(
                dana,
                {
                    "roles": [
                        {"designation": chart.BANK_FEES, "account_id": account["account_id"]}
                    ],
                    # No such service on this tenant — the second half refuses
                    # after the first has written.
                    "services": [
                        {"service_code": "no-such-service", "revenue_account_id": None}
                    ],
                },
            )

        after = ledger_selectors.designation_map().get(chart.BANK_FEES)
        assert after == before, (
            "a refused service write left the ROLE half committed — the save is not "
            "all-or-nothing"
        )


def test_cr060_c10__a_refused_role_half_undoes_the_service_half(brazos, dana):
    """The mirror, so the guarantee is not one-directional.

    The role half is the SECOND thing attempted here only in the sense that its
    refusal is what aborts; the point is that neither ordering can leave a
    half-written map.
    """
    with tenant_ctx(brazos):
        row = a_service_row(brazos)
        row.refresh_from_db()
        before = row.revenue_account_id
        account = an_account(dana, code="9105", name="Water sales (ours)", type_="revenue")

        with pytest.raises((errors.ApiError, errors.NotFoundError)):
            gl_mapping_save.save_gl_mappings(
                dana,
                {
                    # Refused by `_clean_role_changes` BEFORE the transaction —
                    # which is deliberate, and this case pins it: a payload
                    # naming a role that does not exist never reaches a write.
                    "roles": [{"designation": "not_a_designation", "account_id": account["account_id"]}],
                    "services": [
                        {
                            "service_code": row.service.code,
                            "revenue_account_id": account["account_id"],
                        }
                    ],
                },
            )

        row.refresh_from_db()
        assert row.revenue_account_id == before


# ═══════════════════════════════════════════════════════════════════════════
# PROOF 3 — no cross-module ORM write, asserted on the SOURCE
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_c10__the_orchestrator_touches_no_other_modules_orm(brazos, dana):
    """*"a test asserting no cross-module ORM write, which is the rule the
    orchestration exists to respect."*

    Asserted on the SOURCE rather than on behaviour, because behaviour cannot
    tell you HOW a column was written — a direct `TenantService.objects.filter`
    here would produce identical rows and identical test output, and would be
    the exact violation B1 forbids. `apps/ledger/reporting.py`'s own suite makes
    the same argument about its imports for the same reason.
    """
    source = (REPO / "06-backend/apps/ledger/gl_mapping_save.py").read_text()
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)

    foreign = {
        name
        for name in imported
        if name.startswith("apps.") and not name.startswith("apps.ledger")
    }
    assert foreign == set(), (
        f"the orchestrator imports another module's code directly: {sorted(foreign)} — "
        "every cross-module hop goes through a published seam (B1 / BR-TEN-013)"
    )
    # And it must not REACH tenancy's table. Asserted over the source with the
    # prose stripped out, because the docstring names `tenant_services` on
    # purpose — explaining which module owns what is the point of the file, and
    # a check that cannot tell an explanation from an ORM call would force the
    # explanation out to stay green.
    stripped = ast.parse(source)
    for node in ast.walk(stripped):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    node.body = body[1:] or [ast.Pass()]
    code_only = ast.unparse(ast.fix_missing_locations(stripped))
    for forbidden in ("TenantService", "tenant_services"):
        assert forbidden not in code_only, (
            f"the orchestrator reaches tenancy's own table ({forbidden}) — the write "
            "goes through the published seam (B1 / BR-TEN-013)"
        )


def test_cr060_c10__the_write_is_served_on_the_contracted_path(brazos, dana):
    """11b §2.10 names `PUT /ledger/gl-mappings`, and the route it was declined
    on is the route it is served on.

    ⚠ Django dispatches on the PATH, so a second `path("ledger/gl-mappings", …)`
    entry would never be reached and the read view would answer the PUT with a
    405 — a route that looks served and is not. One view, two methods.
    """
    from django.urls import resolve

    slug = brazos.subdomain
    match = resolve(f"/api/{slug}/ledger/gl-mappings")
    assert match.func is chart_api.gl_mappings
    # The decorator's own method list is the contract a 405 comes from.
    assert set(match.func.cls.http_method_names) >= {"get", "put"}


def test_cr060_c10__the_declined_note_is_retired_not_reworded(brazos, dana):
    """Hard-won law 1 — a file that quietly stops describing its own former hole.

    The read used to publish *"PUT /ledger/gl-mappings … is NOT served"* as a
    named gap. It is served now, so the note is renamed to `…_RETIRED`, stamped
    with what answered it, and read by nobody. A gate that finds it unreferenced
    is finding the truth.
    """
    source = (REPO / "06-backend/apps/ledger/chart_api.py").read_text()
    assert "UNSERVED_MAPPING_WRITE_RETIRED" in source
    # It must not be published on any response any more.
    assert '"unavailable": [UNSERVED_MAPPING_WRITE' not in source


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C10 + task T11 (12-governance/11-change-requests.md §CR-060) + 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-014 + 04-docs/01-spec/11b-api-audit.md §2.10
# generated: 2026-09-02 by the CR-060 finance-screens lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST (law 7) — `ModuleNotFoundError: No module named 'apps.ledger.gl_mapping_save'` before the orchestrator existed, and the partial-failure case proved RED again by removing the single `transaction.atomic()`, on PostgreSQL AND on SQLite · 8 passed on PostgreSQL 16.13 and 8 passed on the default SQLite suite · ⚠ the sabotage this file was FIRST written around (a nested `atomic()` per half) did NOT bite on either database, and the module docstring records that rather than the assumption
# exceptions: (1) `test_..._a_refused_role_half_undoes_the_service_half` refuses BEFORE the transaction opens, so on that ordering the guarantee is trivially met — it is kept because it pins the ORDER of validation, which is the thing that makes a refusal cheap and legible rather than a poisoned transaction · (2) there is no case for clearing a role: `save_gl_mappings` refuses that outright and the one-account-at-a-time path keeps its own coverage in `test_us_led_005_gl_designations.py`
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

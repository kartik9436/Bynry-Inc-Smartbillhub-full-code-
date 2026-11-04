# ── Trace ──────────────────────────────────────────────
# Change:   CR-199-BRC10 lane TPL-SRV-FACETS (DEF-NOT-10672)
# Rules:    BR-SHL-011 · A4 B · A1 C · NFR-3 · CLAUDE.md rule 1
# Tests:    this file
# ───────────────────────────────────────────────────────
"""The Templates list serves what its drawing draws (`01-list.png`).

The channel chips (`All · 6`, `Email · 5` …), each row's Languages cell
(*English* · *Español · not written*), the Status cell and the Language and
Status filters — each a fact of the server's, counted over the whole filtered
catalogue and never over a page.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.notifications import catalogs, customers_seam, template_list
from apps.notifications import template_models as tm
from apps.notifications import template_variants, templates_api
from core import tenancy as core_tenancy
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db



def _list(tenant, actor, query=None):
    query = {"per": "50", **(query or {})}
    first = api_call(
        templates_api.template_catalog, "get", user=getattr(actor, "user", None),
        role="system_admin", tenant=tenant, query=query,
    )
    assert first.status_code == 200, first.data
    data = dict(first.data)
    results = list(data["results"])
    page = 1
    while len(results) < data["count"]:
        page += 1
        more = api_call(
            templates_api.template_catalog, "get", user=getattr(actor, "user", None),
            role="system_admin", tenant=tenant, query={**query, "page": str(page)},
        )
        results.extend(more.data["results"])
    data["all"] = results
    return data


def _spanish_on(monkeypatch):
    monkeypatch.setattr(customers_seam, "preferred_languages_in_use", lambda: ("es",))


def _write_spanish(tenant, actor, code):
    made = api_call(
        templates_api.create_variant, "post", user=getattr(actor, "user", None),
        role="system_admin", tenant=tenant,
        data={"language": "es", "category": "default", "start_from": "published"}, code=code,
    )
    assert made.status_code == 201, made.data
    return made


def _row(data, code):
    return next(row for row in data["all"] if row["code"] == code)


def _no_spanish(tenant):
    """Classes with published All-customers wording and no Spanish variant, in
    list order. Chosen from the data: provisioning seeds Spanish for several
    classes (CR-188), so a fixed code would be a guess."""
    with tenant_ctx(tenant):
        tenant_id = core_tenancy.current_tenant_id()
        spanish = set(
            tm.NotificationTemplate.objects.filter(tenant_id=tenant_id, language="es")
            .values_list("code", flat=True)
        )
        live = set(
            tm.NotificationTemplateVersion.objects.filter(
                tenant_id=tenant_id, status=tm.VERSION_PUBLISHED,
                template__category=tm.VARIANT_DEFAULT, template__language=tm.VARIANT_DEFAULT,
            ).values_list("template__code", flat=True)
        )
    codes = [c for c in catalogs.listable_codes() if c in live and c not in spanish]
    assert len(codes) >= 2, codes
    return codes


# ── the chips ──────────────────────────────────────────────────────────────
def test_channel_chips_count_the_catalogue_under_the_other_filters(brazos, dana):
    whole = _list(brazos, dana)
    assert [chip["key"] for chip in whole["channels"]] == ["email", "sms", "in_app", "pdf_print"]
    assert whole["channels_total"] == whole["count"]
    for chip in whole["channels"]:
        assert chip["count"] == sum(1 for row in whole["all"] if row["channel"] == chip["key"])

    collections = _list(brazos, dana, {"f.category": catalogs.CAT_COLLECTIONS})
    assert collections["channels_total"] == collections["count"] < whole["count"]
    assert sum(chip["count"] for chip in collections["channels"]) <= collections["count"]

    texts = _list(brazos, dana, {"f.category": catalogs.CAT_COLLECTIONS, "f.channel": "sms"})
    sms = next(chip["count"] for chip in collections["channels"] if chip["key"] == "sms")
    assert texts["count"] == sms > 0
    assert {row["channel"] for row in texts["all"]} == {"sms"}
    # Choosing a chip does not change what the chips count.
    assert texts["channels"] == collections["channels"]
    assert texts["channels_total"] == collections["channels_total"]


# ── languages ──────────────────────────────────────────────────────────────
def test_each_row_lists_the_utilitys_languages_written_or_not(brazos, dana, monkeypatch):
    _spanish_on(monkeypatch)
    code, other = _no_spanish(brazos)[:2]
    before = _list(brazos, dana)
    with tenant_ctx(brazos):
        own = template_variants.utility_language() or tm.VARIANT_DEFAULT
        offered = [entry["code"] or entry["value"] for entry in template_variants.offered_languages()]
    assert offered[0] == own and "es" in offered

    assert {lang["code"]: lang["written"] for lang in _row(before, code)["languages"]}["es"] is False
    _write_spanish(brazos, dana, code)
    after = _list(brazos, dana)

    target = _row(after, code)
    assert [language["code"] for language in target["languages"]] == offered
    assert {lang["code"]: lang["written"] for lang in target["languages"]}["es"] is True
    assert {lang["code"]: lang["written"] for lang in target["languages"]}[own] is True
    assert target["variants"] == _row(before, code)["variants"] + 1
    untouched = {lang["code"]: lang["written"] for lang in _row(after, other)["languages"]}
    assert untouched["es"] is False


def test_the_language_filter_returns_the_templates_written_in_it(brazos, dana, monkeypatch):
    _spanish_on(monkeypatch)
    code = _no_spanish(brazos)[0]
    _write_spanish(brazos, dana, code)
    whole = _list(brazos, dana)
    spanish = _list(brazos, dana, {"f.language": "es"})
    facet = {entry["key"]: entry["count"] for entry in whole["languages"]}
    assert spanish["count"] == facet["es"] > 0
    assert code in {row["code"] for row in spanish["all"]}
    assert all(
        {lang["code"]: lang["written"] for lang in row["languages"]}["es"]
        for row in spanish["all"]
    )
    # The language facet is not narrowed by itself.
    assert spanish["languages"] == whole["languages"]
    # A language this utility has not switched on falls back, never empties.
    assert _list(brazos, dana, {"f.language": "ja-JP"})["count"] == whole["count"]


# ── status ─────────────────────────────────────────────────────────────────
def test_status_is_one_of_three_and_the_counts_add_up(brazos, dana, monkeypatch):
    _spanish_on(monkeypatch)
    code = _no_spanish(brazos)[0]
    _write_spanish(brazos, dana, code)  # a draft is now waiting on it
    whole = _list(brazos, dana)
    target = _row(whole, code)
    assert target["has_draft"] is True and target["status"] == template_list.STATUS_DRAFT

    statuses = {entry["key"]: entry["count"] for entry in whole["statuses"]}
    assert list(statuses) == ["published", "draft", "not_published", "needs_approval"]
    assert statuses["published"] + statuses["draft"] + statuses["not_published"] == whole["count"]

    for key in ("published", "draft", "not_published"):
        filtered = _list(brazos, dana, {"f.status": key})
        assert filtered["count"] == statuses[key]
        assert {row["status"] for row in filtered["all"]} <= {key}
        assert filtered["statuses"] == whole["statuses"]
    drafts = _list(brazos, dana, {"f.status": "draft"})
    assert code in {row["code"] for row in drafts["all"]}
    assert all(row["has_draft"] for row in drafts["all"])


def test_needs_approval_marks_the_legal_notices(brazos, dana):
    whole = _list(brazos, dana)
    legal = {code for code in catalogs.listable_codes() if template_variants.is_legal_notice(code)}
    assert {row["code"] for row in whole["all"] if row["needs_approval"]} == legal
    filtered = _list(brazos, dana, {"f.status": "needs_approval"})
    statuses = {entry["key"]: entry["count"] for entry in whole["statuses"]}
    assert filtered["count"] == statuses["needs_approval"] == len(legal)


# ── pagination, isolation, cost ────────────────────────────────────────────
def test_the_facets_describe_the_catalogue_not_the_page(brazos, dana):
    query = {"per": "50"}  # the smallest page size; 87 classes make two pages
    one = api_call(templates_api.template_catalog, "get", user=dana.user, role="system_admin",
                   tenant=brazos, query={**query, "page": "1"}).data
    two = api_call(templates_api.template_catalog, "get", user=dana.user, role="system_admin",
                   tenant=brazos, query={**query, "page": "2"}).data
    assert (len(one["results"]), len(two["results"])) == (50, len(catalogs.listable_codes()) - 50)
    assert {r["code"] for r in one["results"]}.isdisjoint({r["code"] for r in two["results"]})
    assert one["count"] == two["count"] == len(catalogs.listable_codes())
    for facet in ("channels", "channels_total", "languages", "statuses"):
        assert one[facet] == two[facet]
    assert one["channels_total"] == one["count"]


def test_another_utilitys_wording_never_counts_here(brazos, lonestar, dana, erin, monkeypatch):
    _spanish_on(monkeypatch)
    code = next(c for c in _no_spanish(lonestar) if c in _no_spanish(brazos))
    before = _list(brazos, dana)
    _write_spanish(lonestar, erin, code)
    after = _list(brazos, dana)
    assert _row(after, code)["has_draft"] is False
    assert _row(after, code)["variants"] == _row(before, code)["variants"]
    assert after["statuses"] == before["statuses"]
    assert after["languages"] == before["languages"]
    assert _list(lonestar, erin, {"f.status": "draft"})["count"] >= 1


def test_the_list_reads_the_tenant_in_grouped_statements_not_per_row(brazos, dana):
    with CaptureQueriesContext(connection) as queries:
        _ = api_call(templates_api.template_catalog, "get", user=dana.user, role="system_admin",
                     tenant=brazos, query={"per": "50"})
    # 87 classes. The old read asked three questions per class (~260).
    assert len(queries.captured_queries) < 40, len(queries.captured_queries)

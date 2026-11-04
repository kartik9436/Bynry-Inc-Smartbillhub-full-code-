# ── Trace ──────────────────────────────────────────────
# Defects: DEF-INT-5589 — a connector's *Service address* is declared
#          `kind="host"`, whose check refuses a scheme and a path, so the City
#          of Ann Arbor's real ArcGIS address cannot be typed into the product.
#          DEF-INT-5590 — nineteen `kind="host"` fields ship a `default=` their
#          OWN validator rejects (hard-won law 7's *incapable of passing*).
#          DEF-INT-5591 — `live_calls.provision()` writes a config that
#          `services.connect()` refuses, so neither live call can be
#          provisioned at all.
# Rules:   BR-INT-043 (the CLOSED field-kind vocabulary, no fallback branch) ·
#          BR-INT-037 (data, not code) · BR-INT-048 (the page policy is
#          GENERATED from the registered browser operations) · BR-INT-003 (no
#          credential in a non-secret field) · hard-won law 7
# PO:      2026-09-17 — "a) build it now with the Edit fix"
# ───────────────────────────────────────────────────────
"""**THE SERVICE ADDRESS IS A URL, AND `host` CANNOT HOLD ONE.**

The City of Ann Arbor's address service is

    https://a2mapseg.a2gov.org/a2arcgis/rest/services/SEU/SEUQualifiedAddress/FeatureServer/0/query

and **the path is not decoration** — `/SEU/SEUQualifiedAddress/FeatureServer/0/`
is what names the layer. `_check_host` matches a bare hostname and nothing
else, so the host passes and the real address does not.

⚠ **THE TEST THAT MATTERS IS `test_ann_arbor…`, AND IT IS FIRST ON PURPOSE.**
Everything below it guards the fix; that one IS the customer's blocker.

⚠ **WHAT WOULD MAKE THIS FILE PASS WRONGLY** — asked of every case here,
because a URL check is the classic regex that accepts everything. A validator
written as `^https?://.+` passes `https://` followed by a space, a URL with a
credential in it, and `http://a b/c`. So the refusal cases below are not
decoration either: they are the half that proves the acceptance means
something. `test_url_refuses_*` fails on `r"^https?://.+"`.
"""

from __future__ import annotations

import pytest

from apps.integrations import live_calls, page_policy, selectors
from apps.integrations.adapters.base import validate_fields
from apps.integrations.registry import REGISTRY, SEEDED_DEFAULT_EXEMPTIONS

#: The real address, from the Product Owner, 2026-09-17. Not an example.
ANN_ARBOR = (
    "https://a2mapseg.a2gov.org/a2arcgis/rest/services/SEU/"
    "SEUQualifiedAddress/FeatureServer/0/query"
)


def _errors(provider_key: str, field: str, value) -> list:
    """The problems this manifest reports ABOUT ONE FIELD.

    ⚠ Filtered to the field under test on purpose. `email_smtp` declares five
    required fields, so an unfiltered call reports four *required* errors that
    have nothing to do with the value being judged — and a test that asserts
    `== []` on that would be red for a reason it does not name, which is
    hard-won law 7's *looking at the wrong thing* wearing a green tick.
    """
    manifest = REGISTRY.get(provider_key)
    assert manifest is not None, f"{provider_key} is not registered"
    problems = validate_fields(manifest, {field: value}, require_secrets=False)
    return [one for one in problems if one.field == field]


# ── 1 · the customer's blocker ──────────────────────────────────────────────


def test_ann_arbor_real_service_address_is_accepted():
    """The one case this whole change exists for."""
    assert _errors("gis_esri", "base_url", ANN_ARBOR) == []


def test_ann_arbor_address_survives_the_page_policy_as_an_origin():
    """A URL with a path must still yield an ORIGIN to the browser policy.

    `DEF-INT-4259` is the record of what a wrong host in this policy costs.
    A CSP source is an origin; handing a browser a whole URL with a path is a
    source expression it reads differently from the origin it looks like.
    """
    assert page_policy._origin(ANN_ARBOR) == "https://a2mapseg.a2gov.org"


@pytest.mark.parametrize(
    "value,origin",
    [
        (ANN_ARBOR, "https://a2mapseg.a2gov.org"),
        # A TILE TEMPLATE. `map_tiles` declares `tile_url` as its own host
        # (`DEF-INT-4259`), and a basemap address carries `{z}/{y}/{x}`
        # placeholders as part of its PATH — braces, not a query.
        (
            "https://a2mapseg.a2gov.org/a2arcgis/rest/services/Basemap/MapServer/tile/{z}/{y}/{x}",
            "https://a2mapseg.a2gov.org",
        ),
        # Still works for the bare host a `host` field holds, so the two kinds
        # feed the policy through ONE path and cannot disagree.
        ("gis.vendor.example", "https://gis.vendor.example"),
        ("https://gis.vendor.example:6443/arcgis/rest", "https://gis.vendor.example:6443"),
    ],
)
def test_the_policy_derives_an_ORIGIN_and_never_asks_a_clerk_to_type_it_twice(value, origin):
    """The host the browser is permitted is DERIVED from the address typed.

    A CSP source is an origin, so the path has to come off — and it has to come
    off HERE rather than in a second box on the form, or the two could disagree
    and `DEF-INT-4259` is the record of what a wrong host in this policy costs.
    """
    assert page_policy._origin(value) == origin


def test_a_tile_template_is_accepted_by_the_url_check():
    """Proved in the browser too: the policy then grants
    `https://a2mapseg.a2gov.org` from `source: connection`, beating the
    shipped default, which is `R-7`'s whole case."""
    assert (
        _errors(
            "gis_esri",
            "tile_url",
            "https://a2mapseg.a2gov.org/a2arcgis/rest/services/Basemap/MapServer/tile/{z}/{y}/{x}",
        )
        == []
    )


# ── 2 · `host` is NOT widened ───────────────────────────────────────────────


def test_host_still_accepts_a_bare_hostname():
    assert _errors("email_smtp", "host", "smtp.mailhost.example") == []


@pytest.mark.parametrize(
    "value",
    [
        "https://smtp.mailhost.example",  # a scheme
        "smtp.mailhost.example/submit",  # a path
        "smtp.mailhost.example:587",  # a port belongs in `port`
        "smtp.mailhost.example/",  # a bare trailing slash is still a path
    ],
)
def test_host_still_refuses_anything_but_a_hostname(value):
    """SMTP dials a host and a port. A path here is concatenated into a
    connection string somewhere, which is why `host` must NOT be widened."""
    problems = _errors("email_smtp", "host", value)
    assert problems, f"{value!r} was accepted into a host field"
    assert problems[0].message_key == "integrations.field.host"


# ── 3 · what the new kind refuses ───────────────────────────────────────────


@pytest.mark.parametrize(
    "value",
    [
        "a2mapseg.a2gov.org",  # no scheme — not an absolute address
        "//a2mapseg.a2gov.org/x",  # protocol-relative is not absolute
        "/a2arcgis/rest/services",  # a path alone
        "https://",  # a scheme and nothing else
        "https:// a2gov.org/x",  # a space where the host goes
        "https://a2 gov.org/x",  # a space INSIDE the host
        "http://user:pass@a2gov.org/x",  # a credential in a non-secret field
        "ftp://a2gov.org/x",  # a scheme we do not dial
        "javascript:alert(1)",  # not an address at all
        "https://a2gov.org/x?f=json",  # a query — the adapter appends its own
        "https://a2gov.org/x#layer",  # a fragment never reaches a server
        "https://a2gov.org:0/x",  # not a port
        "https://a2gov.org:99999/x",  # not a port
        "https://-a2gov.org/x",  # not a hostname
        "rubbish",
        "",
    ],
)
def test_url_refuses_what_is_not_an_absolute_service_address(value):
    problems = _errors("gis_esri", "base_url", value)
    assert problems, f"{value!r} was accepted"
    assert problems[0].message_key in (
        "integrations.field.url",
        "integrations.field.required",
    )


@pytest.mark.parametrize(
    "value",
    [
        ANN_ARBOR,
        "https://gis.vendor.example",  # bare origin, no path
        "https://gis.vendor.example/",  # a trailing slash
        "http://192.168.10.4/arcgis/rest",  # an address, not a name
        "https://gis.vendor.example:6443/arcgis/rest/services",  # a port
    ],
)
def test_url_accepts_a_real_service_address(value):
    assert _errors("gis_esri", "base_url", value) == []


# ── 4 · the systemic defect: a default the form rejects ─────────────────────


def test_no_manifest_ships_a_default_its_own_form_would_refuse():
    """Hard-won law 7's *incapable of passing*, measured over all 28 connectors.

    A field pre-filled with a value that can never be saved is a box that
    refuses the only thing in it. Nineteen shipped that way after
    `CR-110-BRC04` wave C seeded a placeholder address into every connector
    that dials out — every one carrying a scheme, into a field whose own check
    refuses a scheme.
    """
    rejected = set()
    for manifest in REGISTRY.all():
        for field in manifest.fields:
            if not field.default:
                continue
            spoiled = [
                one
                for one in validate_fields(
                    manifest, {field.name: field.default}, require_secrets=False
                )
                if one.field == field.name
            ]
            if spoiled:
                rejected.add((manifest.key, field.name))
    assert rejected == SEEDED_DEFAULT_EXEMPTIONS


def test_the_one_exemption_is_still_the_one_we_signed_up_for():
    """⚠ **THIS IS THE TEST THAT FIRES WHEN THE HOLD EXPIRES** (hard-won law 2).

    `pay_invoicecloud.base_url` is the twentieth *Service address* and was
    left at `kind="host"` on 2026-09-17 because another lane held that file
    open for `CR-111-BRC04`; `DEF-INT-5592` carries it. The fix is one word.
    The DAY somebody applies it, this assertion goes red and names the entry
    to delete from `registry.SEEDED_DEFAULT_EXEMPTIONS` — which is the whole
    point, because a hold that quietly stays correct after it stops being
    needed is how a refusal outlives its reason (`DEF-CWP-3925`).
    """
    assert SEEDED_DEFAULT_EXEMPTIONS == {("pay_invoicecloud", "base_url")}
    manifest = REGISTRY.get("pay_invoicecloud")
    assert manifest is not None
    field = {one.name: one for one in manifest.fields}["base_url"]
    assert field.kind == "host", (
        "pay_invoicecloud.base_url is no longer a `host` — DEF-INT-5592 is "
        "fixed, so delete its row from registry.SEEDED_DEFAULT_EXEMPTIONS "
        "and this test with it"
    )


def test_live_call_defaults_are_values_connect_would_accept():
    """`live_calls.provision()` writes these through `services.connect()`,
    which runs `validate_fields` and raises BEFORE any write. A default the
    validator refuses makes `provision()` incapable of succeeding."""
    rejected = {
        key: validate_fields(REGISTRY.get(key), dict(config), require_secrets=False)
        for key, config in live_calls.LIVE_CALL_DEFAULTS.items()
    }
    assert {key: errs for key, errs in rejected.items() if errs} == {}


# ── 5 · what the move must not break ────────────────────────────────────────


def test_every_connector_that_dials_out_still_resolves_an_endpoint():
    """`DEF-INT-5502` — the endpoint column reads the manifest's single field
    of kind `host`. Moving the service address to a NEW kind without teaching
    that fallback would empty the column again, which is the same defect the
    fallback was written to fix."""
    resolved = {
        manifest.key: selectors.host_fallback_field(manifest)
        for manifest in REGISTRY.all()
    }
    for key in ("geocoder_census", "meters_itron", "print_vendor", "sms_twilio"):
        assert resolved[key] == "base_url", f"{key} lost its endpoint column"
    assert resolved["email_smtp"] == "host"
    assert resolved["bank_lockbox_file"] == "sftp_host"
    # Two addresses on one connection stays AMBIGUOUS and answers None —
    # `DEF-INT-4259` is the record of what guessing between two costs.
    assert resolved["gis_esri"] is None

# ── Trace ──────────────────────────────────────────────
# Change:   CR-110-BRC04 wave C — the blueprint draws 28 connectors and we
#           shipped 18. Ten files added, four keys retired, thirteen of the
#           additions split out of four manifests we already had.
# Rules:    BR-INT-037 (adding an API is DATA, not code — a 29th connector adds
#           no table, no column and no migration) · BR-INT-001 (the disposition
#           decides what a card says) · BR-INT-012 (AMI ingestion waits for the
#           B6 capacity re-run) · DEF-INT-5488 (a host_field that names nothing)
#           · CLAUDE.md hard-won law 2 (built is not wired; a hold carries the
#           test that fires when it expires) · law 3 (the unsafe option is the
#           one you type) · law 7 (prove a guard RED before trusting it green,
#           and in the harness that will run it).
# PO:       2026-09-16, five rulings this file asserts — one key per connection ·
#           the call limit is a guard nobody may edit · scheduling belongs to
#           Runbooks · never-twice on an OUTBOUND money call belongs to Runbooks
#           · the card page is the processor's, never ours.
# ───────────────────────────────────────────────────────
"""The twenty-eight, asserted where a reader will see them.

⚠ **WHY A COUNT IS WORTH A TEST AT ALL.** This repository's second hard-won law
is that an eleventh utility service did not appear on screen and *failed
silently* — the row existed, the API served it, `tsc` and every test passed, and
the sign-up screen simply never offered it. `SignupWizard.test.tsx` asserts
eleven for that reason. A connector is the same shape of fact: the grid draws
`REGISTRY.all()`, so a manifest that is written and never added to `MANIFESTS`
is a file nobody can see and nothing complains about. **This test fails when a
connector arrives and when one leaves**, and it names which.
"""

from __future__ import annotations

import pytest

from apps.integrations import manifests as manifests_module
from apps.integrations.manifests import CONNECTOR_COUNT, MANIFESTS, register_all
from apps.integrations.registry import (
    ADDRESS_FIELD_KINDS,
    DISPOSITION_COMING_SOON,
    Auth,
    Field,
    Idempotency,
    Manifest,
    ManifestError,
    Operation,
    Registry,
    validate,
)

#: The blueprint's catalogue, p161–p162, 01 to 28, in the order it draws them.
#: Typed out rather than derived, because a list derived from the thing it
#: checks cannot disagree with it — which is the whole failure shape of a check
#: that cannot fail (hard-won law 7).
DRAWN = (
    "email_microsoft",
    "email_google",
    "email_smtp",
    "sendgrid",
    # ⚠ **THE THIRTIETH, AND THE SECOND THE BLUEPRINT DOES NOT DRAW**
    # (`CR-115-BRC05`, 2026-09-17). The drawing's row 04 is ONE unnamed *Bulk
    # email service*; the PO named two ESPs and both accounts exist, so 04
    # became `sendgrid` and this sits beside it. It is here rather than at the
    # end for the reason `pay_invoicecloud_partner` is: this tuple is the ORDER
    # A CLERK SEES, and two ESP cards a page apart read as two unrelated
    # connectors rather than as one choice.
    "postmark",
    "sms_twilio",
    "meters_neptune360",
    "meters_badger",
    "meters_itron",
    "meters_sensus",
    "pay_invoicecloud",
    # ⚠ **THE TWENTY-NINTH, AND THE FIRST THE BLUEPRINT DOES NOT DRAW.**
    # `CR-111-BRC04` / `DEF-INT-5574`, PO 2026-09-17: InvoiceCloud runs in both
    # directions and a manifest declares ONE `auth.mode`, so the reading half is
    # a second row BESIDE the card one. It is here rather than at the end
    # because this tuple is the ORDER A CLERK SEES, and two rows with one
    # company name have to be adjacent to read as one relationship.
    "pay_invoicecloud_partner",
    "pay_paymentus",
    "pay_uspayments",
    "pay_worldpay",
    "pay_globalpayments",
    "payments_kiosk",
    "payments_sandbox",
    "erp_aclarian",
    "erp_workday",
    "erp_sap",
    "erp_infor",
    "erp_msgp",
    # ⚠ **30 → 31 ON 2026-09-22 — `erp_newworld`** (`CR-132-BRC07`). A SIXTH
    # named ERP, appended after the five `gl_partner` was split into, and
    # nothing renumbered. Like `pay_invoicecloud_partner` and `postmark` it is
    # NOT in the blueprint's catalogue of twenty-eight, so this tuple is *what
    # we ship in the order a clerk sees it* and has been since 2026-09-17.
    "erp_newworld",
    "accounting_file",
    "bank_lockbox_file",
    "print_vendor",
    "gis_esri",
    "geocoder_census",
    "map_tiles_public",
    "sso",
)

#: The four keys `CR-110-BRC04` retired. A manifest reappearing under one of
#: these is a split being undone by accident.
RETIRED = ("payments_card", "gl_partner", "meters_mdm", "gis_city")

#: The five that replace `payments_card`.
#:
#: ⚠ **THIS SET USED TO BE `key.startswith("pay_")` AND THAT STOPPED BEING TRUE
#: ON 2026-09-17** (`CR-111-BRC04`). `pay_invoicecloud_partner` is a `pay_` key
#: that is not a card processor at all — it is InvoiceCloud's READING half, a
#: partner that holds a key we issued — so the prefix caught it and two cases
#: below demanded a card page and a `coming_soon` disposition of a live partner
#: connector. **A name prefix is a copy of a fact that has no reason to stay
#: right** (`DEF-INT-5575`'s own lesson, one file along). A card processor is
#: now identified by the thing that makes it one — it charges a card — and the
#: literal set below locks that derivation so a sixth arriving has to move a
#: line here rather than joining silently.
CARD_PROCESSORS = frozenset({
    # ⚠ **`pay_uspayments` LEFT THIS SET ON 2026-10-07 (`CR-174-BRC10`).** PO D4,
    # verbatim: *"US payment card - use it"* — the card became US Payments
    # (Prime)'s three INBOUND calls and is live; it charges no card.
    "pay_invoicecloud",
    "pay_paymentus",
    "pay_worldpay",
    "pay_globalpayments",
})


def _card_processors(registry: Registry):
    """Every manifest that charges a card, derived — and checked against the
    literal set, so neither a silent arrival nor a silent removal passes."""
    found = [
        one for one in registry.all()
        if any(op.name == "deliver_charge" for op in one.operations)
    ]
    assert {one.key for one in found} == CARD_PROCESSORS, sorted(one.key for one in found)
    return found


@pytest.fixture
def registry() -> Registry:
    """Every manifest, registered together, exactly as `AppConfig.ready()` does.

    ⚠ Validation is a WHOLE-SET act: `register_all` refuses the FIRST bad
    manifest by name, so a file validated on its own proves nothing about the
    set the product loads.
    """
    return register_all(Registry())


# ═══════════════════════════════════════════════════════════════════════════
# The count, and the names behind it
# ═══════════════════════════════════════════════════════════════════════════


def test_cr110__thirty_connectors_load(registry: Registry) -> None:
    """⚠ **28 → 29 ON 2026-09-17** (`CR-111-BRC04`, `DEF-INT-5574`). The one
    connector is `pay_invoicecloud_partner`, and it is the first row that is NOT
    in the blueprint's catalogue of twenty-eight — so the number this asserts has
    stopped being *what the blueprint draws* and is now *what we ship*.

    ⚠ **30 → 31 ON 2026-09-22** (`CR-132-BRC07`). The one connector is
    `erp_newworld` — Tyler's New World / Logos, a SIXTH named ERP, arriving for
    a real municipal utility going live on it. One manifest file, no migration
    and no screen code, which is `BR-INT-037` being true rather than claimed.

    ⚠ **29 → 30 ON 2026-09-17** (`CR-115-BRC05`). The one connector is
    `postmark`. The blueprint draws ONE unnamed *Bulk email service* at row 04;
    the PO named two ESPs and both accounts exist, so 04 became `sendgrid` and
    `postmark` sits beside it at 04b. **THE RENAME DID NOT MOVE THIS NUMBER** —
    `email_bulk` → `sendgrid` is the same row under a real name, and counting it
    as an arrival is how a count quietly stops meaning anything."""
    assert len(registry) == 31
    assert CONNECTOR_COUNT == 31
    assert len(MANIFESTS) == 31


def test_cr110__the_keys_are_the_blueprints_catalogue_in_its_own_order(
    registry: Registry,
) -> None:
    """Order matters: the card grid draws `REGISTRY.all()` as registered, so
    this sequence IS what a clerk sees on Settings."""
    assert tuple(one.key for one in registry.all()) == DRAWN


@pytest.mark.parametrize("key", RETIRED)
def test_cr110__a_retired_key_is_gone(registry: Registry, key: str) -> None:
    assert registry.get(key) is None
    assert not hasattr(manifests_module, key)


def test_cr110__every_display_name_is_distinct(registry: Registry) -> None:
    """Two cards reading the same words is a grid a clerk cannot use — and it
    is how *Itron / Sensus* came to be one card giving each vendor half a
    name."""
    names = [one.display_name for one in registry.all()]
    assert len(set(names)) == len(names), sorted(n for n in names if names.count(n) > 1)


def test_cr110__the_two_renames_landed(registry: Registry) -> None:
    assert registry.require("sms_twilio").display_name == "Twilio"
    assert registry.require("meters_neptune360").display_name == "Neptune 360"
    assert registry.require("gis_esri").display_name == "Esri ArcGIS"


# ═══════════════════════════════════════════════════════════════════════════
# The PO's rulings of 2026-09-16, each asserted where it can be broken
# ═══════════════════════════════════════════════════════════════════════════


def test_cr110__every_operation_names_its_ceiling(registry: Registry) -> None:
    """*"keep the limit in database so if we want to change it later it is easy
    to do"* — and the default provisioning copies in lives here."""
    for manifest in registry.all():
        for op in manifest.operations:
            assert op.rate_limit_per_minute is not None, f"{manifest.key} · {op.name}"
            assert op.rate_limit_per_minute >= 1, f"{manifest.key} · {op.name}"


def test_cr110__no_connector_asks_a_clerk_for_a_time_of_day(registry: Registry) -> None:
    """PO: *"conenctor i a conenctor not a logic to to ETL"*.

    The blueprint draws a clock in a *When it runs* panel on nine screens. None
    of it is declared: when to call is Runbooks'. ⚠ This does NOT touch the
    connection's `cadence`, which is shipped and read, nor a `Poll` schedule,
    which is how often to re-ask about a job already submitted.
    """
    for manifest in registry.all():
        for field_declared in manifest.fields:
            words = f"{field_declared.name} {field_declared.label}".lower()
            for banned in ("time", "hour", "clock", "schedule", "run at"):
                assert banned not in words, f"{manifest.key} · {field_declared.name}"


def test_cr110__no_connector_asks_a_clerk_for_a_token(registry: Registry) -> None:
    """PO: *"i only want to issue a key per conenction … i dont understand the
    differnt between key and token"*. One key per connection, and the word
    *token* is off every screen.

    ⚠ `token_exchange` STAYS as an auth mode and this does not touch it:
    `meters_neptune360` really does swap the vendor's key for a short-lived
    token because their API demands it. That is plumbing inside an adapter and
    reaches no clerk.

    ⚠ **ONE EXEMPTION, AND IT IS A QUESTION RATHER THAN A DECISION.** Twilio
    call their own secret an **Auth token** — it is the label printed on their
    console, CFG-05 draws it, and a clerk sent looking for an *Auth key* would
    find nothing. The PO's reason was OUR two words for one idea (*"i dont
    understand the differnt between key and token"*), not a vendor's product
    label, so this lane did not rename it — but the ruling's own words are *"the
    word token, from every screen"* and this is on a screen. It is a clerk-facing
    word, which makes it the PO's, so it is asked rather than settled:
    `OQ-INT-12392`. What this test enforces meanwhile is the part that is not in
    doubt — **no connector asks for a token ADDRESS, a token SCOPE or a
    GENERATE** — which is the whole Token panel the ruling removed.
    """
    banned = ("token address", "token url", "token_url", "generate token", "token scope")
    for manifest in registry.all():
        for field_declared in manifest.fields:
            words = f"{field_declared.name} {field_declared.label}".lower()
            for phrase in banned:
                assert phrase not in words, f"{manifest.key} · {field_declared.name}"
    # The one place `token` survives, named so that a second one cannot appear
    # without this list moving (OQ-INT-12392).
    with_token_in_a_label = {
        (one.key, f.name)
        for one in registry.all()
        for f in one.fields
        if "token" in f"{f.name} {f.label}".lower()
    }
    # ⚠ **TWO SINCE 2026-09-17, AND THE SECOND STRENGTHENS THE QUESTION RATHER
    # THAN WEAKENING THE RULE** (`CR-115-BRC05`). Postmark scopes its credential
    # to a SERVER and prints *Server API Token* on the screen a clerk copies it
    # from, so a field labelled *Server key* would send them hunting for a thing
    # that does not exist. That is the SAME reason Twilio's `auth_token` was left
    # alone, and it is the reason the PO's words do not settle it: the ruling was
    # about OUR two words for one idea (*"i dont understand the differnt between
    # key and token"*), not about a vendor's product label.
    #
    # **`OQ-INT-12392` IS NOW A TWO-CONNECTOR QUESTION.** One vendor reads as a
    # quirk; two reads as a rule needing an exception, which is what makes it
    # worth the PO's time. This guard is working exactly as designed — it is the
    # reason this lane went and read the ruling instead of typing a label.
    assert with_token_in_a_label == {
        ("sms_twilio", "auth_token"),
        ("postmark", "server_token"),
    }, with_token_in_a_label
    assert registry.require("meters_neptune360").auth.mode == "token_exchange"


def test_cr110__no_card_connector_offers_an_embedded_card_page(registry: Registry) -> None:
    """PO: *"A · their page only — toggle comes off 4 forms, costs nothing"*.

    Embedded would put this whole product inside the card industry's annual
    audit, and that cost is not reversible. There is no select with two options
    and no hidden default: **the field does not exist**, so a tenant cannot
    reach the embedded journey at all.
    """
    cards = _card_processors(registry)
    assert len(cards) == 4  # five until CR-174-BRC10 made USPayments inbound
    for manifest in cards:
        assert not any("card" in one.name for one in manifest.fields), manifest.key
        page = next(one for one in manifest.operations if one.name == "deliver_card_page")
        assert page.executor == "browser_credentialed", manifest.key


def test_cr110__outbound_money_declares_no_duplicate_guard(registry: Registry) -> None:
    """PO: *"again we will build a runbok with logic to ensure there no twice"*.

    ⚠ **THIS ASSERTS AN ABSENCE, WHICH IS THE THING NOTHING ELSE IN THIS REPO
    CAN SEE** — and it asserts it so that the absence is a decision with a test
    on it rather than an omission nobody can tell from one. The answer (never
    refund twice) is unchanged; its home moved to Runbooks. **Until that
    Runbook exists a real refund cannot ship**, which is why all five
    processors are `coming_soon`.
    """
    for manifest in _card_processors(registry):
        assert manifest.disposition.kind == DISPOSITION_COMING_SOON, manifest.key
        for name in ("deliver_charge", "deliver_refund"):
            op = next(one for one in manifest.operations if one.name == name)
            assert op.idempotency is not None
            assert op.idempotency.source == "none", f"{manifest.key} · {name}"
            assert not op.mutates_partner_state, f"{manifest.key} · {name}"


def test_cr110__inbound_duplicate_guards_are_untouched(registry: Registry) -> None:
    """The half that would open a hole while appearing to obey the ruling.

    *They send the same event twice* is a fact about the door — *have I already
    been handed this exact event?* — which is access control in the PO's own
    sense. Every one of these was declared before this change and none moved.
    """
    expected = {
        ("sendgrid", "receive_feedback"): "provider_event_id",
        ("postmark", "receive_feedback"): "provider_event_id",
        ("sms_twilio", "receive_status"): "provider_event_id",
        ("payments_kiosk", "payments"): "provider_event_id",
        ("payments_kiosk", "returns"): "provider_event_id",
        ("payments_sandbox", "settlement"): "provider_event_id",
    }
    for (key, name), source in expected.items():
        op = next(one for one in registry.require(key).operations if one.name == name)
        assert op.idempotency is not None and op.idempotency.source == source, (key, name)


def test_cr110__a_blank_scope_grants_nothing(registry: Registry) -> None:
    """Hard-won law 3 — the unsafe option must be the one you type. A key with
    nothing named cannot be issued (`machine_auth._validated_scope`).

    ⚠ **THE CONTROL MOVED ON 2026-09-16 AND THE RULE DID NOT.** This asserted
    the shape of a `scopes` FIELD: required, no default, and its options equal
    to the operations. PO, verbatim: *"we need to allow all apis to be read -
    all 4 currently i can select only 1 or you remove it and put selection on
    off directly on apis"* — the field was `kind="select"`, which is
    single-value, so a clerk could grant one of four. **The field is gone and
    the choice is on the API rows**, which is the same assertion one layer
    down: the set a clerk may grant IS the set of operations, because it is
    now literally the same list rather than a second list kept beside it.

    So what is asserted here is what the removal has to leave true:

      * no `they_hold_ours` manifest declares a `scopes` field any more — a
        second control for one fact is how two controls come to disagree;
      * every one of them still declares an `issued_secret` field, so the
        screen knows to draw the switches and the keys panel at all;
      * and `DEF-INT-5504`'s two vocabularies are CLOSED by construction: there
        is no clerk word left to map onto an operation name.
    """
    issuing = [one for one in registry.all() if one.auth.mode == "they_hold_ours"]
    # ⚠ **6 → 7 ON 2026-09-17, AND THE ONE CONNECTOR IS
    # `pay_invoicecloud_partner`** (`CR-111-BRC04`, `DEF-INT-5574`, PO ruling of
    # that date). It is the seventh manifest that issues a key of ours, and the
    # number is stated rather than derived for the reason the reference suite
    # gives: a case reading `len(...)` on both sides passes over a connector
    # quietly REMOVED.
    # ⚠ **7 → 8 ON 2026-09-22, AND THE ONE CONNECTOR IS `erp_newworld`**
    # (`CR-132-BRC07`). It is the eighth manifest that issues a key of ours —
    # New World dials us, we never dial them — and the number stays STATED
    # rather than derived for the reason given above: a case reading `len(...)`
    # on both sides passes over a connector quietly REMOVED.
    # ⚠ **8 → 9 ON 2026-10-07, AND THE ONE CONNECTOR IS `pay_uspayments`**
    # (`CR-174-BRC10`, PO D4: *"US payment card - use it"*). The card became
    # US Payments (Prime), who call us with a key we issue.
    assert len(issuing) == 9, [one.key for one in issuing]
    for manifest in issuing:
        names = {one.name for one in manifest.fields}
        assert "scopes" not in names, (
            f"{manifest.key}: a separate scope picker is back beside the API "
            "switches — two controls for one fact"
        )
        assert "client_id" not in names, (
            f"{manifest.key}: `client_id` is back, and nothing reads it — a "
            "required field nothing reads refuses the save and strands the key"
        )
        assert any(one.kind == "issued_secret" for one in manifest.fields), (
            f"{manifest.key}: declares no issued key, so the set-up screen "
            "draws neither the switches nor the key panel"
        )
        assert manifest.operations, manifest.key



def test_cr110__no_new_connector_declares_a_mapping(registry: Registry) -> None:
    """PO: *"we dont need mapping at connector level it will be in runbook with
    business logic"*. Forward-looking only — the three that shipped with a
    vocabulary keep it, because ripping out live machinery on the day its owner
    changes is how a working product breaks."""
    # ⚠ **`pay_uspayments` JOINS ON 2026-10-07 (`CR-174-BRC10`), AND IT IS A
    # LATER RULING READ THROUGH, NOT THIS ONE IGNORED.** PO D1, verbatim: *"(a).
    # A person standing at a machine needs the live balance. Runbooks still
    # handle the exceptions in D2."* A payment posted INSIDE the call needs its
    # tender resolved inside the call, and the tender vocabulary is the one
    # built mechanism that does it (*"unknown → OTHER, never refuse"*). Decision
    # log 2026-10-07, the build's judgments (J7).
    shipped_with_mappings = {
        "accounting_file",
        "bank_lockbox_file",
        "payments_kiosk",
        "pay_uspayments",
    }
    for manifest in registry.all():
        if manifest.key in shipped_with_mappings:
            continue
        assert manifest.vocabularies == (), manifest.key
        assert not any(one.kind == "mapping_editor" for one in manifest.fields), manifest.key


# ═══════════════════════════════════════════════════════════════════════════
# DEF-INT-5488 — the dummy APIs, and the refusal that keeps them honest
# ═══════════════════════════════════════════════════════════════════════════


def test_cr110__every_operation_we_dial_has_a_host_that_resolves(
    registry: Registry,
) -> None:
    """`DEF-INT-5488`: fifteen of eighteen manifests named `base_url` and
    declared no such field, so no connection ever held a host."""
    for manifest in registry.all():
        declared = {one.name: one for one in manifest.fields}
        for op in manifest.operations:
            if op.they_call_us:
                continue
            assert op.host_field in declared, f"{manifest.key} · {op.name}"
            # ⚠ **BOTH ADDRESS KINDS, SINCE `DEF-INT-5589`.** Nineteen
            # *Service address* fields moved from `host` to `url` on
            # 2026-09-17 so a path could be typed into them (Ann Arbor's
            # ArcGIS layer is named by its path). What this test cares about
            # is that the named field is VALIDATED AS AN ADDRESS — which both
            # kinds are and `text` is not — so it asks the registry's own
            # `ADDRESS_FIELD_KINDS` rather than naming one of them.
            assert (
                declared[op.host_field].kind in ADDRESS_FIELD_KINDS
            ), f"{manifest.key} · {op.name} · {declared[op.host_field].kind}"


def test_cr110__the_host_check_states_what_it_skipped(registry: Registry) -> None:
    """A declared blind spot with no NUMBER attached is indistinguishable from
    an empty one (hard-won law 7, `G32`'s shape). 22 operations are
    partner-called, so their address is ours and no clerk configures it."""
    coverage = registry.host_coverage()
    assert coverage["connectors"] == 31  # +erp_newworld, CR-132-BRC07
    assert coverage["checked"] + coverage["skipped"] == sum(
        len(one.operations) for one in registry.all()
    )
    assert coverage["skipped"] > 0


def test_cr110__every_connector_we_dial_seeds_a_placeholder_address(
    registry: Registry,
) -> None:
    """The PO's phase-1 dummy API: *"i want you to put dummary apis in all these
    28 conenctor"*. A seeded default is what provisioning copies in, so a
    connection holds an address the day the file is written.

    ⚠ The folder connectors are the exception and it is stated rather than
    skipped: their host is a customer's own SFTP or drop folder, and inventing
    a placeholder for it would put a plausible wrong address in front of a
    clerk. They are `required=False` and seed nothing.
    """
    # CR-173-BRC10 (2026-10-07): New World's *Send to City folder* is a City's
    # OWN SFTP server — the folder exception, for the same reason: a seeded
    # placeholder would be a plausible wrong address for a City password.
    folders = {"accounting_file", "bank_lockbox_file", "email_smtp", "erp_newworld"}
    for manifest in registry.all():
        dialled = [one for one in manifest.operations if not one.they_call_us]
        if not dialled or manifest.key in folders:
            continue
        hosts = {one.host_field for one in dialled}
        seeded = {
            one.name
            for one in manifest.fields
            if one.kind in ADDRESS_FIELD_KINDS and one.default
        }
        assert hosts & seeded, f"{manifest.key}: {sorted(hosts)} vs seeded {sorted(seeded)}"


def test_cr110__no_seeded_default_is_ever_a_secret(registry: Registry) -> None:
    for manifest in registry.all():
        for one in manifest.fields:
            if one.is_secret:
                assert not one.default, f"{manifest.key} · {one.name}"


# ═══════════════════════════════════════════════════════════════════════════
# The guards, shown RED — law 7, and through the path that will run them
# ═══════════════════════════════════════════════════════════════════════════


def _probe(**overrides) -> Manifest:
    base = dict(
        key="probe",
        category="meters",
        display_name="Probe",
        summary="A probe.",
        auth=Auth(mode="none", placement="none"),
        fields=(Field(name="base_url", label="Service address", kind="host"),),
        operations=(
            Operation(
                name="fetch_thing",
                label="Collect things",
                direction="in",
                initiative="us",
                transport="https",
                trigger="scheduled",
                idempotency=Idempotency(mode="reconcile", source="none"),
                completion="immediate",
                rate_limit_per_minute=60,
            ),
        ),
    )
    base.update(overrides)
    return Manifest(**base)


def test_cr110__the_probe_itself_is_valid() -> None:
    """The control. A probe that could never pass would make every refusal
    below meaningless — a check incapable of passing is law 7's third shape."""
    validate(_probe())


def test_cr110__a_host_field_naming_nothing_is_refused_by_name() -> None:
    with pytest.raises(ManifestError) as caught:
        validate(_probe(fields=()))
    assert "host_field 'base_url'" in str(caught.value)
    assert "DEF-INT-5488" in str(caught.value)
    assert "fetch_thing" in str(caught.value)


def test_cr110__a_host_field_of_the_wrong_kind_is_refused_by_name() -> None:
    with pytest.raises(ManifestError) as caught:
        validate(_probe(fields=(Field(name="base_url", label="X", kind="text"),)))
    assert "declared as kind 'text'" in str(caught.value)


def test_cr110__an_operation_with_no_ceiling_is_refused_by_name() -> None:
    naked = Operation(
        name="fetch_thing",
        label="Collect things",
        direction="in",
        initiative="us",
        transport="https",
        trigger="scheduled",
        idempotency=Idempotency(mode="reconcile", source="none"),
        completion="immediate",
    )
    with pytest.raises(ManifestError) as caught:
        validate(_probe(operations=(naked,)))
    assert "rate_limit_per_minute" in str(caught.value)
    assert "probe · fetch_thing" in str(caught.value)


def test_cr110__a_ceiling_of_nothing_is_refused_by_name() -> None:
    with pytest.raises(ManifestError) as caught:
        validate(
            _probe(
                operations=(
                    Operation(
                        name="fetch_thing",
                        label="Collect things",
                        direction="in",
                        initiative="us",
                        transport="https",
                        trigger="scheduled",
                        idempotency=Idempotency(mode="reconcile", source="none"),
                        completion="immediate",
                        rate_limit_per_minute=0,
                    ),
                )
            )
        )
    assert "refuses a healthy partner on its first request" in str(caught.value)


def test_cr110__a_seeded_secret_is_refused_by_name() -> None:
    with pytest.raises(ManifestError) as caught:
        validate(
            _probe(
                fields=(
                    Field(name="base_url", label="Service address", kind="host"),
                    Field(name="api_key", label="API key", kind="secret", default="hunter2"),
                )
            )
        )
    assert "'api_key'" in str(caught.value)
    assert "credential in the repository" in str(caught.value)


# ═══════════════════════════════════════════════════════════════════════════
# The two holds, and the tests that fire when they expire
# ═══════════════════════════════════════════════════════════════════════════
#
# Hard-won law 2's mirror clause, verbatim: *"WHEN YOU WRITE A HOLD, WRITE THE
# TEST THAT FIRES WHEN THE HOLD EXPIRES, in the same commit."* A hold with no
# such test is a promise nobody is keeping, and on 2026-09-05 the customer
# portal's front page had two working doors out of eight for exactly that
# reason.
#
# These two connectors are placeholders by PO ruling — *"keep it as it is right
# now - we will replace them - theya re dummay right now we will replace them
# later"*. The hold expires the day somebody NAMES the vendor, and naming a
# vendor means changing the display name away from its category word. So:
#
#   · while the name is still generic, the card must say *coming soon*;
#   · the moment the name changes, THIS TEST GOES RED and names the file.
#
# It cannot be satisfied by quietly flipping the disposition either, because
# the assertion runs both ways.

#: ⚠ **TWO UNTIL 2026-09-17, AND `email_bulk` DID NOT SIMPLY LEAVE — ITS HOLD
#: WAS RE-AIMED** (`CR-115-BRC05`). The PO named both ESPs and both accounts
#: exist, so that connector became `sendgrid`, `postmark` was added beside it,
#: and **the name-shaped hold above could not survive the rename in either
#: direction**: left alone it demanded a card go LIVE with no adapter behind it
#: (which is `DEF-INT-4224`, the defect this suite exists to prevent), and
#: satisfied by adding `{"sendgrid": "SendGrid"}` here it would have recorded a
#: real, contracted vendor as a placeholder — a hold that reads as kept while
#: meaning nothing.
#:
#: **The display name was always a PROXY for the question that matters — can a
#: utility press this card and have it work — and the proxy has been outgrown.**
#: The two ESPs are now held on the thing itself, in
#: `test_cr115_email_connectors.py`: coming-soon for exactly as long as
#: `adapter_for()` answers `None`. `print_vendor` keeps the name-shaped hold
#: because its vendor genuinely is still unnamed, which is what that hold is
#: about.
PLACEHOLDERS = {"print_vendor": "Print vendor"}


@pytest.mark.parametrize("key", sorted(PLACEHOLDERS))
def test_cr110__an_unnamed_vendor_says_coming_soon(registry: Registry, key: str) -> None:
    manifest = registry.require(key)
    generic = manifest.display_name == PLACEHOLDERS[key]
    assert manifest.disposition.coming_soon == generic, (
        f"{key}: display name is {manifest.display_name!r} and the card is "
        f"{manifest.disposition.kind!r}. If a vendor has been named, this connector "
        "is ready to be made live — bind its adapter, give it a real test action, "
        "and set the disposition. If it has not, the card must keep saying so: a "
        "placeholder that presents itself as ready to connect is a card a utility "
        "can press that cannot work."
    )
    if manifest.disposition.coming_soon:
        assert manifest.disposition.wave, key


@pytest.mark.parametrize("key", sorted(PLACEHOLDERS))
def test_cr110__a_placeholder_has_no_adapter_bound(registry: Registry, key: str) -> None:
    """The server half of the same hold. `BR-INT-001` refuses a connect for a
    coming-soon card at the service boundary, and the registry refuses to bind
    an adapter to one — so this cannot be half-released."""
    assert registry.adapter_for(key) is None

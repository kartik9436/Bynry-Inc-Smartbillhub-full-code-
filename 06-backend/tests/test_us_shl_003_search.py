# ── Trace ──────────────────────────────────────────────
# Story:    US-SHL-003 — global search. TC-1, TC-4, TC-5, TC-8 and the four
#           cases added with the 2026-09-03 amendment: TC-9 (rank), TC-10 (the
#           five new groups), TC-11 (rule 31 — no uuid on screen), TC-12
#           (a role-invisible group is OMITTED, not empty).
#           Screens: shell chrome (the topbar box on every authenticated screen)
# Defect:   DEF-2423 — the box that accepted text and did nothing. These cases
#           are what make it do something.
# Rules:    BR-SHL-005 AS AMENDED 2026-09-03 · BR-SHL-006 · B14 rule 31
# Note:     TC-7 (cross-tenant isolation) is NOT here. It needs live PostgreSQL
#           and a non-superuser probe, and it lives in
#           tests/test_us_shl_003_search_isolation.py — a green SQLite run
#           proves nothing about RLS and that file says so in its own words.
# ───────────────────────────────────────────────────────
"""The endpoint over the WIRED stack: a signed-in client, the real route, the
real middleware, the real sources.

⚠ **EVERY CASE HERE GOES THROUGH `GET /api/{tenant}/search`, NOT THROUGH
`core.search.search()`.** That is deliberate and it is the whole point of the
lane: the kernel, the sources, the prop and the debouncer all existed and passed
their own tests for weeks while the feature did not exist, because no route
joined them. A test that calls the kernel directly would have been green
throughout that period. This one would not.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.assets import models as asset_models
from apps.billing.models import Invoice
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.payments import models as payment_models
from core import permissions, search

from tests.test_us_idn_helpers import (  # noqa: F401 (fixture import)
    api_get,
    idn,
    signed_in_client,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def restore_search_sources():
    """Snapshot and restore the process-wide source registry.

    The nine real sources are registered at `AppConfig.ready()`, i.e. once per
    process. A case that re-registers one (TC-12 narrows `payments` to a single
    role) would otherwise leave that narrowing in place for every later test in
    the run — a cross-test leak that reads as a product bug in a file that has
    nothing to do with search.
    """
    saved = dict(search._sources)
    yield
    search._sources.clear()
    search._sources.update(saved)


# ── world ───────────────────────────────────────────────────────────────────


def _status(tenant):
    return customer_models.AccountStatus.objects.create(
        tenant=tenant, code="active", name="Active", behavior_class="billable"
    )


def _account_type(tenant):
    """The tenant's own home account type (`DEF-SHL-10691`).

    ⚠ **THIS WAS `AccountType.objects.first()` AND IT HAS RETURNED `None` SINCE
    2026-09-17** (`d0b2afb50`): account types became the TENANT's own
    (`customers.0054` deletes the platform rows), so a fresh test database holds
    none and every case in this file failed in setup on `accounts.account_type_id`
    NOT NULL. Seeded through the product's own path, in the tenant's context, and
    read BY TENANT — never another utility's row (hard rule 1)."""
    from apps.customers import services as customer_services
    from core.tenancy import tenant_context

    with tenant_context(tenant.id):
        customer_services.ensure_account_types()
    return customer_models.AccountType.objects.get(tenant_id=tenant.id, code="residential")


def _premises(tenant, *, premise_no=None, name=None, address_line="1 Test St"):
    return metering_models.Premises.objects.create(
        tenant=tenant, premise_no=premise_no, name=name, address_line=address_line
    )


def _anchor(tenant, premises=None):
    """A premises and a unit for an account to hang off.

    TWO constraints, not one, and the second is the one that bites:
      · `ck_accounts_anchored` — every account has a unit OR a premises;
      · `ck_accounts_regular_has_unit` — a REGULAR account must have a UNIT.
        Only a master account may be anchored to the premises alone, which is
        BR-CUS-068's shape (the owner's account over the common areas).
    ⚠ The premises address deliberately contains NO hyphen and no part of any
    account number. Every identifier in this file is hyphenated, so an address
    that echoed one would put a phantom row in the Premises group and quietly
    change what the group-count and group-order cases measure.
    """
    if premises is None:
        premises = _premises(tenant, address_line="Anchor Way")
    unit = metering_models.Unit.objects.create(tenant=tenant, premises=premises, label="Anchor")
    return premises, unit


def _account(
    tenant, status, account_no, *, name=None, kind="regular", updated=None, premises=None, unit=None
):
    if unit is None:
        premises, unit = _anchor(tenant, premises)
    account = customer_models.Account.objects.create(
        tenant=tenant,
        account_no=account_no,
        kind=kind,
        status=status,
        account_type=_account_type(tenant),
        premises_id=premises.id if premises is not None else None,
        # A master account carries the premises alone; a regular one must carry
        # the unit (`ck_accounts_regular_has_unit`).
        unit=None if kind == "master" else unit,
    )
    if name:
        customer_models.Contact.objects.create(
            tenant=tenant, account=account, full_name=name, is_primary=True
        )
    if updated is not None:
        # `updated_at` is auto_now, so it cannot be set on create — the rank is
        # about the STORED value, so the row is stamped by an UPDATE that
        # bypasses the field (a plain .save() would overwrite it with now()).
        customer_models.Account.objects.filter(pk=account.pk).update(updated_at=updated)
        account.refresh_from_db()
    return account


def _seed(idn, token=""):
    """Silver Creek, populated across all nine searchable surfaces.

    `token` is appended to every identifier so ONE query can reach all nine
    groups at once — which is what the group-ORDER case needs and what no
    realistic identifier set provides: `P-2001`, `A-10432`, `BL-2608-018410`
    and `SR-26-0046` share no two-character substring, and a one-character
    query is refused by the IS-3 minimum (which is itself a case above).
    Left empty everywhere else, so every other case reads real identifiers.
    """
    tenant = idn.silvercreek
    status = _status(tenant)
    now = timezone.now()

    world = {"tenant": tenant, "status": status}

    world["premises"] = metering_models.Premises.objects.create(
        tenant=tenant,
        premise_no=f"P-2001{token}",
        name="Cedar Ridge Apartments",
        address_line="118 Cedar Ridge Dr",
    )
    world["unit"] = metering_models.Unit.objects.create(
        tenant=tenant, premises=world["premises"], unit_no=f"U-3001{token}", label="Unit 3B"
    )
    # Anchored to the real premises and unit rather than to throwaway ones, so
    # the Premises and Units groups hold exactly the rows this fixture means.
    world["account"] = _account(
        tenant,
        status,
        f"A-10432{token}",
        name="Maria Delgado",
        premises=world["premises"],
        unit=world["unit"],
    )
    world["master"] = _account(
        tenant,
        status,
        f"A-10999{token}",
        name="Cedar Ridge HOA",
        kind="master",
        premises=world["premises"],
        unit=world["unit"],
    )
    asset_type = asset_models.AssetType.objects.create(
        tenant=tenant, code="water_meter", name="Water meter", category="meters"
    )
    stage = asset_models.AssetLifecycleStage.objects.create(
        tenant=tenant, code="in_service", name="In service", behavior_class="in_service"
    )
    world["asset"] = asset_models.Asset.objects.create(
        tenant=tenant, asset_no=f"MTR-4400{token}", serial_no="SN-778812", type=asset_type, status=stage
    )

    world["customer"] = customer_models.Customer.objects.create(
        tenant=tenant, customer_no=f"C-5500{token}", kind="person", display_name="Maria Delgado"
    )

    today = timezone.localdate()
    world["invoice"] = Invoice.objects.create(
        tenant=tenant,
        account=world["account"],
        invoice_no=f"BL-2608-018410{token}",
        status="issued",
        service_date=today,
        period_start=today - timedelta(days=30),
        period_end=today,
        due_date=today + timedelta(days=21),
        subtotal=Decimal("140.00"),
        tax_total=Decimal("8.63"),
        total=Decimal("148.63"),
        currency="USD",
    )

    # `method` is nullable and the tender is irrelevant to a search — the
    # fixture stays minimal so a change to the lookup catalogue cannot break a
    # test about finding a payment by its number.
    world["payment"] = payment_models.Payment.objects.create(
        tenant=tenant,
        account=world["account"],
        payment_no=f"PMT-88213{token}",
        type=payment_models.PAYMENT_TYPE_PAYMENT,
        purpose=payment_models.PURPOSE_BILL,
        amount=Decimal("247.30"),
        currency="USD",
        status=payment_models.PAYMENT_POSTED,
        posted_at=now,
        confirmation="CHQ-44120",
    )

    world["request"] = customer_models.ServiceRequest.objects.create(
        tenant=tenant,
        request_no=f"SR-26-0046{token}",
        state=customer_models.ServiceRequest.SUBMITTED,
        channel=customer_models.ServiceRequest.CHANNEL_STAFF_COLLECTIONS,
        applicant_kind=customer_models.ServiceRequest.APPLICANT_PERSON,
        applicant_name="Dev Patel",
        address_as_given="9 Quarry Hill Ct",
    )
    world["now"] = now
    return world


def _alex(idn):
    """A System Admin in Silver Creek."""
    idn.seed_silvercreek()
    return signed_in_client("alex@silvercreek.example", "Canyon2026rapids")


def _groups(response):
    return {group["entity"]: group["rows"] for group in response.json()["groups"]}


def _order(response):
    return [group["entity"] for group in response.json()["groups"]]


# ── TC-1 · the query the PO typed ───────────────────────────────────────────


def test_us_shl_003_tc1__an_account_number_finds_its_account(idn):
    """The whole defect in three lines: type an account number, get the account.

    On the shipped tree this could not be written — the route answered 404
    because `config/urls.py` registered no search path (DEF-2423).
    """
    world = _seed(idn)
    client = _alex(idn)

    response = api_get(client, "/search?q=A-104")
    assert response.status_code == 200, response.content

    accounts = _groups(response)["accounts"]
    assert [row["label"] for row in accounts] == ["A-10432"]
    assert accounts[0]["context"] == "Maria Delgado"
    assert response.json()["q"] == "A-104"
    assert world["account"].account_no == "A-10432"


def test_us_shl_003_tc1b__a_name_finds_the_account_through_its_primary_contact(idn):
    """BR-SHL-005's signed field list: `accounts.account_no` AND the primary
    `contacts.full_name`. A clerk with somebody on the phone types the name."""
    _seed(idn)
    client = _alex(idn)

    response = api_get(client, "/search?q=Delgado")
    assert [row["label"] for row in _groups(response)["accounts"]] == ["A-10432"]


def test_us_shl_003__a_removed_contacts_name_no_longer_finds_the_account(idn):
    """A soft-deleted contact is not a way in.

    ⚠ **AND THE BUG THIS GUARDS IS WORSE THAN A STRAY ROW.** The context line
    comes from `_primary_contact_names`, which has always excluded deleted
    contacts — so before the fix, searching a REMOVED person's name returned
    their old account labelled with a DIFFERENT person's name. A clerk would
    have read that as "this is now Jordan's account", which it may not be.

    It also pins the shape of the fix: the deleted check must live INSIDE the
    same `Q` as the name match. Two separate `.filter()` calls ask "some
    matching contact AND some live contact", which is TRUE here and would leave
    this test green over the defect.
    """
    world = _seed(idn)
    tenant = world["tenant"]
    # The account gains a second, LIVE contact, and the original is removed.
    customer_models.Contact.objects.filter(account=world["account"]).update(
        deleted_at=timezone.now()
    )
    customer_models.Contact.objects.create(
        tenant=tenant, account=world["account"], full_name="Jordan Blake", is_primary=True
    )
    client = _alex(idn)

    # The removed name finds nothing…
    assert "accounts" not in _groups(api_get(client, "/search?q=Delgado"))
    # …the live one still does, and labels the row with the live person.
    live = _groups(api_get(client, "/search?q=Jordan"))["accounts"]
    assert [row["label"] for row in live] == ["A-10432"]
    assert live[0]["context"] == "Jordan Blake"


# ── TC-9 · THE RANK, AND IT MUST FAIL UNDER THE TWO WRONG ORDERINGS ─────────


def test_us_shl_003_tc9__prefix_beats_recency_and_recency_breaks_the_tie(idn):
    """BR-SHL-005: *"ranked prefix-match-first then most-recently-updated"*.

    ⚠ **THIS CASE IS BUILT SO THAT THE TWO PLAUSIBLE WRONG IMPLEMENTATIONS BOTH
    FAIL IT**, which is the only reason it is worth writing:

      · plain SUBSTRING + `-updated_at` → `B-9A-104` is the newest row and would
        come FIRST. It comes last here.
      · plain PREFIX only, no recency   → the two prefix matches would come back
        in arbitrary order. Here the newer of them must be first.

    Three rows, one query, and the expected order is fixed by the rule rather
    than by insertion order.
    """
    tenant = idn.silvercreek
    status = _status(tenant)
    now = timezone.now()

    _account(tenant, status, "A-10432", updated=now - timedelta(days=7))  # prefix, old
    _account(tenant, status, "A-10450", updated=now - timedelta(days=1))  # prefix, newer
    _account(tenant, status, "B-9A-104", updated=now)  # substring, newest of all

    client = _alex(idn)
    response = api_get(client, "/search?q=A-104")

    assert [row["label"] for row in _groups(response)["accounts"]] == [
        "A-10450",  # prefix band, newest in it
        "A-10432",  # prefix band, older
        "B-9A-104",  # substring band — newest row in the table, and still last
    ]


# ── TC-5 / TC-8 · the two quiet answers ─────────────────────────────────────


def test_us_shl_003_tc5__one_character_searches_nothing_and_is_not_an_error(idn):
    """IS-3's two-character minimum, enforced server-side as well as in the box.

    200 with no groups — SILENCE, never a refusal. A client that had to catch an
    error to learn "your query was too short" would eventually stop catching it.
    """
    _seed(idn)
    client = _alex(idn)

    response = api_get(client, "/search?q=A")
    assert response.status_code == 200
    assert response.json()["groups"] == []
    assert response.json()["total"] == 0


def test_us_shl_003_tc8__no_match_is_an_empty_result_not_a_404(idn):
    """A18 §2's "No results" pattern is rendered from a 200 with nothing in it."""
    _seed(idn)
    client = _alex(idn)

    response = api_get(client, "/search?q=zzzz")
    assert response.status_code == 200
    assert response.json() == {"q": "zzzz", "total": 0, "groups": []}


# ── the ≤5 cap ──────────────────────────────────────────────────────────────


def test_us_shl_003__a_group_never_returns_more_than_five_rows(idn):
    """BR-SHL-005's cap, proved with SEVEN matching rows in one group."""
    tenant = idn.silvercreek
    status = _status(tenant)
    for index in range(7):
        _account(tenant, status, f"A-2000{index}")

    client = _alex(idn)
    response = api_get(client, "/search?q=A-2000")

    assert len(_groups(response)["accounts"]) == 5
    assert response.json()["total"] == 5


# ── TC-10 · the five surfaces the amendment added ───────────────────────────


@pytest.mark.parametrize(
    ("query", "entity", "label"),
    [
        ("P-2001", "premises", "P-2001"),
        ("Cedar Ridge Apart", "premises", "P-2001"),  # the signed free-text half
        ("U-3001", "units", "U-3001"),
        ("MTR-4400", "assets", "MTR-4400"),
        ("SN-7788", "assets", "MTR-4400"),  # found by SERIAL, labelled by asset_no
        ("C-5500", "customers", "C-5500"),
        ("BL-2608", "bills", "BL-2608-018410"),
        ("PMT-88213", "payments", "PMT-88213"),
        ("CHQ-441", "payments", "PMT-88213"),  # found by CONFIRMATION
        ("SR-26-0046", "requests", "SR-26-0046"),
    ],
)
def test_us_shl_003_tc10__every_group_answers_its_own_identifier(idn, query, entity, label):
    """Nine groups, each found by the identifier a person would quote.

    ⚠ The ASSET rows are the pair worth reading: an asset is found by
    `asset_no` OR `serial_no` (BR-AST-026 names both as quotable) and is
    LABELLED by `asset_no` either way — the serial rides in the context line so
    a field tech can check it against the device.
    """
    _seed(idn)
    client = _alex(idn)

    groups = _groups(api_get(client, f"/search?q={query}"))
    assert entity in groups, f"{query!r} returned {list(groups)}"
    assert [row["label"] for row in groups[entity]] == [label]


def test_us_shl_003_tc10b__a_master_account_is_its_own_group_and_not_in_accounts(idn):
    """The master/regular split the PO made explicit on 2026-09-03.

    Both rows match "A-10"; each appears in exactly ONE group. A master account
    turning up under *Accounts* would be the inference the ruling removed.
    """
    _seed(idn)
    client = _alex(idn)

    groups = _groups(api_get(client, "/search?q=A-10"))
    assert [row["label"] for row in groups["master_accounts"]] == ["A-10999"]
    assert [row["label"] for row in groups["accounts"]] == ["A-10432"]


def test_us_shl_003__groups_arrive_in_the_ruled_order_on_the_wire(idn):
    """`groups` is a LIST so the order is carried by the response.

    ⚠ It is a list rather than an object precisely so the client cannot need a
    hand-typed order of its own — which is how an eleventh utility service
    failed to reach the sign-up screen while every test passed.
    """
    # Every identifier carries the same token, so ONE query reaches all nine
    # groups this fixture builds. Real identifiers share no two-character
    # substring and a one-character query is refused by the IS-3 minimum —
    # which is how this case first went red, on `?q=-`, and the refusal was
    # correct.
    _seed(idn, token="ZQ")
    client = _alex(idn)

    order = _order(api_get(client, "/search?q=ZQ"))

    # ⚠ **THIS FIXTURE SEEDS NINE OF FIFTEEN, SO THE ASSERTION IS A
    # SUBSEQUENCE — AND THAT IS A DELIBERATE SPLIT, NOT A WEAKENING
    # (`CR-073`, 2026-09-05).** Six groups arrived on 2026-09-05 and building
    # their rows here would put work orders, templates, parts, technicians,
    # crews, plans and charge codes into a fixture that NINE other cases in
    # this file read, several of which count the rows in a group. The whole
    # fifteen-group order is asserted end to end in
    # `tests/test_cr073_search_work_rating.py`, on a fixture built for it.
    # What THIS case owns is the claim its docstring makes: the order is
    # carried by the wire, in the server's sequence, for whatever is present.
    assert len(order) == 9, order
    assert order == [entity for entity in search.GROUP_ORDER if entity in order]


# ── TC-11 · B14 rule 31 — no database id is the visible value of a field ────


def test_us_shl_003_tc11__no_uuid_is_ever_a_visible_value(idn):
    """Every rendered field of every row, checked against the row's own id.

    The id IS carried — the popover needs somewhere to link to — and the test is
    that it appears in `id` and NOWHERE ELSE. An asset is the sharp case:
    BR-AST-026 says its uuid is never displayed, and it has two other numbers
    that could have been confused for it.
    """
    _seed(idn, token="ZQ")
    client = _alex(idn)

    response = api_get(client, "/search?q=ZQ")
    assert len(response.json()["groups"]) == 9  # every group is under this lens
    for group in response.json()["groups"]:
        for row in group["rows"]:
            visible = [row["label"], row["context"], row["amount"], row["currency"]]
            for value in visible:
                assert row["id"] not in (value or ""), (group["entity"], row)
            # A label is an identifier a person quotes, so it is never a bare
            # 36-character uuid either — a defensive shape check, because a
            # future source could pick the wrong column and still pass above.
            assert len(str(row["label"])) < 36, (group["entity"], row)


def test_us_shl_003__money_rides_as_its_stored_decimal_beside_its_currency(idn):
    """Hard rule 2: never a float on the wire, never re-rounded here.

    `148.63` is stored as `148.630000` and travels that way; the client displays
    it to two places. A test that asserted "148.63" would be asserting the
    DISPLAY rule in the wrong layer.
    """
    _seed(idn)
    client = _alex(idn)

    bill = _groups(api_get(client, "/search?q=BL-2608"))["bills"][0]
    assert bill["amount"] == "148.630000"
    assert bill["currency"] == "USD"
    assert bill["context"] == "A-10432"


# ── TC-12 · a role-invisible group is OMITTED, never rendered empty ─────────


def test_us_shl_003_tc12__a_group_a_role_cannot_see_is_absent_not_empty(idn):
    """BR-SHL-006: *"role-invisible entity groups omitted"*.

    In v1 all three roles read all nine surfaces, so this narrows `payments` to
    System Admin for the length of the case and searches as an EXECUTIVE. The
    assertion is that the key is not in the response at all — a heading over
    zero rows would tell a user there are no payments matching, which is a
    different and false statement.
    """
    _seed(idn)
    idn.seed_silvercreek()
    from apps.payments import search_sources as payment_sources

    search.register_search_source(
        "payments",
        payment_sources.search_payments,
        visible_to=frozenset({permissions.SYSTEM_ADMIN}),
    )

    admin = signed_in_client("alex@silvercreek.example", "Canyon2026rapids")
    executive = signed_in_client("diana@silvercreek.example", "Vista2026peak")

    assert "payments" in _groups(api_get(admin, "/search?q=PMT-88213"))
    executive_groups = _groups(api_get(executive, "/search?q=PMT-88213"))
    assert "payments" not in executive_groups
    assert executive_groups == {} or all(rows for rows in executive_groups.values())


# ── the door itself ─────────────────────────────────────────────────────────


def test_us_shl_003__the_route_is_mounted_and_refuses_an_anonymous_caller(idn):
    """The include in `config/urls.py`, asserted rather than assumed.

    If a future lane drops the include this fails with 404 instead of 401 — the
    failure mode DEF-2423 was, and the reason `search_api.py`'s docstring says
    the test resolves the route through the real URLconf.
    """
    from django.test import Client

    response = Client().get("/api/silvercreek/search?q=A-104")
    assert response.status_code in (401, 403), response.status_code

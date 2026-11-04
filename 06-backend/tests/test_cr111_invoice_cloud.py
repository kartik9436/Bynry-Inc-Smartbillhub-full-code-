# ── Trace ──────────────────────────────────────────────
# Story:  CR-111-BRC04 — the Invoice Cloud partner API. Five PO rulings of
#         2026-09-17, plus five answers the same day.
# Rules:  BR-TEN-003 (nothing a caller sends selects anything) · BR-INT-044
#         (one refusal, one body, one set of bytes) · BR-INT-037 (a dialect is
#         data) · NFR-3 (universal server pagination — the CSV too) ·
#         CLAUDE.md hard rule 1 · hard rule 2 · hard rule 8 · law 7
# ───────────────────────────────────────────────────────
"""THE SHAPE, THE CSV, THE TWO NEW ADDRESSES, AND `company_id` EMPTIED.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per law 7
--------------------------------------------------------------------
**1 · The shape suite's named false pass: a fixture record whose keys the
shape does not rename.** Then `apply_record` could be the identity function and
every case would still be green. So `test_the_invoice_cloud_shape_renames_the_
record` asserts the OLD key is GONE as well as the new one being present — an
`update()` that added `invoiceNo` and kept `id` would serve a partner one value
under two names and pass a present-key check.

**2 · The native shape's false pass: asserting it "works".** `NATIVE` is a
no-op, so almost any implementation satisfies a loose check. It is asserted as
an EXACT identity (`==` on the whole dict) over a record of every resource, so
a shape that touched one field of one resource goes red naming it.

**3 · The CSV's false pass, and it is the one that would actually have shipped:
comparing the CSV against a SECOND call.** Two calls to a paged endpoint over a
moving table can legitimately differ, so a flaky comparison would be "fixed" by
loosening it. Instead the JSON and the CSV are taken from ONE response each and
the CSV's header row is asserted against the JSON record's own keys — which is
the actual contract — and `test_the_csv_is_the_same_records_as_the_json` reads
the values back cell by cell.

**4 · `company_id`'s false pass: asserting a 200 with a good `company_id`.**
That was already true before this wave. The removal is proved by sending a
DIFFERENT utility's id and a nonsense string and asserting **200 with the same
body as sending none at all**, which is the only assertion that can tell
*ignored* from *still checked and happening to match*.

**5 · `bill-download`'s false pass: asserting a 404 for another utility's
bill.** A 404 is also what an unknown id gets, so a per-case 404 proves
nothing. The case compares the **whole response body byte for byte** against
the body a REFUSED KEY gets, which is the property `BR-INT-044` actually
states.

RED PROVED FIRST, in `pytest` — the harness that runs it (`DEF-GOV-3733`).
"""

from __future__ import annotations

import json

import pytest

from apps.integrations import partner_api, partner_csv, shapes
from apps.integrations.runners import serve
from apps.integrations.seams import billing as billing_seam
from apps.integrations.seams import customers as customers_seam

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import tenant_ctx

ALLOWLIST_FOR_PROBE = "198.51.100.0/24"

# ⚠ **THE FOUR-ACCOUNT FIXTURE IS BORROWED RATHER THAN REBUILT.**
# `address_stories` already builds four accounts that are four DIFFERENT address
# stories — including the landlord whose bill goes to a building the meter is
# not at — and a fixture of my own with one shared premises would print green
# over a broken walk, which is that file's own named false pass.
from tests.test_cr110_phase2_partner_customers import (  # noqa: F401
    address_stories,
)

from tests.test_cr110_phase2_partner_reference import (  # noqa: F401
    ALLOWED_ADDRESS,
    HINT,
    KEY,
    _body,
    _connect,
    _get,
    wired,
)


# ══════════════════════════════════════════════════════════════════════════
# THE SHAPE — data, never code
# ══════════════════════════════════════════════════════════════════════════


BILL = {
    "id": "INV-2026-00412",
    "billDate": "2026-09-17",
    "consumer_no": "A-10432",
    "billType": {"code": "regular", "label": "Regular"},
    "status": {"code": "issued", "label": "Issued"},
    "projectType": "Utility Billing",
    "bill_amount": "142.1800",
    "lines": [{"id": 1, "gl_code": "4100", "amount": "100.0000"}],
}

CUSTOMER = {
    "id": "A-10432",
    "consumer_no": "A-10432",
    "customer_name": "Marisol Ruiz",
    "first_name": "Marisol",
    "last_name": "Ruiz",
    "phone": "555-0142",
    "status": {"code": "active", "label": "Active"},
    "status_display": "Active",
    "opening_balance": "142.1800",
}

PAYMENT = {"id": "P-99", "tender": {"code": "CHQ", "label": "Cheque"}, "paidOn": "2026-09-17"}


def test_the_native_shape_is_an_exact_identity_on_every_resource() -> None:
    """`NATIVE` goes through `apply_records` exactly as a partner dialect does.

    ⚠ **THE EXACT IDENTITY, NOT "IT WORKS".** The tempting build is *if no shape
    is declared, skip the mechanism* — and then the native path and the shaped
    path are two code paths and only one is exercised by the partner suites.
    This is the assertion that keeps them one.
    """
    for resource, record in (("bills", BILL), ("customers", CUSTOMER), ("payments", PAYMENT)):
        assert shapes.apply_record(record, shapes.NATIVE, resource=resource) == record, resource


def test_the_invoice_cloud_shape_renames_the_record_and_drops_our_names() -> None:
    """Their spelling arrives AND ours leaves — the second half is the test."""
    out = shapes.apply_record(BILL, shapes.INVOICE_CLOUD, resource="bills")
    assert out["invoiceNo"] == "INV-2026-00412"
    assert "id" not in out, "one value under two names is DEF-014"
    assert out["billDate"] == "17-09-2026", "DD-MM-YYYY, their document's spelling"
    assert out["billType"] == "Regular" and out["status"] == "Issued", "flat means the word"
    assert "lines" not in out, "their bill is FLAT — the nested lines do not travel"
    assert out["projectType"] == "Utility Billing"
    assert out["bill_amount"] == "142.1800", "a shape may not touch a money value"

    customer = shapes.apply_record(CUSTOMER, shapes.INVOICE_CLOUD, resource="customers")
    assert customer["contact_number"] == "555-0142" and "phone" not in customer
    assert customer["status"] == "Active" and "status_display" not in customer

    payment = shapes.apply_record(PAYMENT, shapes.INVOICE_CLOUD, resource="payments")
    assert payment["tenderType"] == "Cheque" and "tender" not in payment


def test_a_shape_cannot_change_a_value() -> None:
    """Every value that survives is the value that went in.

    ⚠ **THIS IS THE BOUNDARY ITSELF AND IT IS ASSERTED OVER THE WHOLE RECORD**,
    not over the fields the shape happens to name. A shape that quantized a
    money string, upper-cased a code or re-computed a total would be caught here
    whichever field it touched.
    """
    out = shapes.apply_record(BILL, shapes.INVOICE_CLOUD, resource="bills")
    survivors = [value for value in out.values()]
    originals = {
        "INV-2026-00412",
        "A-10432",
        "Utility Billing",
        "142.1800",
        "Regular",
        "Issued",
        "17-09-2026",  # the ONE permitted change: a reversible date reformat
    }
    for value in survivors:
        assert value in originals, f"{value!r} is a value no input carried"


def test_every_reformatter_round_trips() -> None:
    """A reformat is reversible; a computation is not. **That is the whole
    distinction**, and this is where it is checked rather than asserted in a
    docstring."""
    for value in ("2026-09-17", "2026-01-01", "1999-12-31"):
        assert shapes._to_iso(shapes._to_dmy(value)) == value, value
    # A value the reformatter cannot read comes back UNTOUCHED rather than None.
    for junk in ("", "not a date", "2026-09", "26-09-17"):
        assert shapes._to_dmy(junk) == junk, junk


def test_a_shape_holds_no_code() -> None:
    """The structural guarantee, asserted rather than described.

    Every field of every shape is a string, a tuple of strings, or a mapping of
    strings to those. **There is nowhere to put a lambda**, so a later lane
    cannot add a "just this once" hook without changing the dataclass — which a
    reviewer sees.
    """
    def _plain(value: object) -> bool:
        if isinstance(value, str):
            return True
        if isinstance(value, (tuple, list)):
            return all(_plain(one) for one in value)
        if isinstance(value, dict):
            return all(_plain(k) and _plain(v) for k, v in value.items())
        return False

    for shape in (shapes.NATIVE, shapes.INVOICE_CLOUD):
        assert _plain(shape.envelope), shape.key
        for name, resource in shape.resources.items():
            assert _plain(resource.rename), (shape.key, name)
            assert _plain(resource.omit), (shape.key, name)
            assert _plain(resource.dates), (shape.key, name)
            assert _plain(resource.flatten), (shape.key, name)
            assert _plain(resource.nest), (shape.key, name)


def test_a_shape_is_chosen_by_the_connector_and_by_nothing_else() -> None:
    """`resolve` takes a connector key. **There is no overload taking a request,
    a header or a query parameter**, so a caller cannot ask for another
    partner's dialect."""
    assert shapes.resolve("erp_aclarian") is shapes.NATIVE
    assert shapes.resolve("pay_invoicecloud") is shapes.INVOICE_CLOUD
    assert shapes.resolve(None) is shapes.NATIVE
    assert shapes.resolve("a connector that does not exist") is shapes.NATIVE


def test_the_partner_connector_resolves_to_its_own_dialect() -> None:
    """⚠ **`DEF-INT-5642` — THE DIALECT WAS DEAD ON EVERY REAL CALL.**

    The case above is true and asks the wrong question. `resolve` is called
    from ONE place — `partner_api._page_response`, with
    `caller.connection.provider_key` — so the only keys that can ever arrive
    are the connectors a partner can hold a key for. Neither of the two this
    map carried was one: **`erp_invoicecloud` is a manifest that does not
    exist** (considered and refused, in `pay_invoicecloud_partner.py`'s own
    docstring) and `pay_invoicecloud` is the CARD half, `we_hold_theirs`,
    which is never a partner caller.

    So InvoiceCloud received `NATIVE` — our envelope, ISO dates, `id` instead
    of `invoiceNo`, `phone` instead of `contact_number` — while every shape
    test above passed, because they call `apply_record` with the shape in
    hand, and every ROUTE test passed, because they connect as `erp_aclarian`,
    which correctly IS native. Both halves right, nothing joining them.

    **This case is the join**: the key a real call carries, through the real
    resolver. It was proved red on the tip.
    """
    from apps.integrations.partner_api import partner_provider_keys

    assert "pay_invoicecloud_partner" in partner_provider_keys()
    assert shapes.resolve("pay_invoicecloud_partner") is shapes.INVOICE_CLOUD, (
        "the connector whose key InvoiceCloud actually presents gets our own "
        "dialect, so everything in shapes.INVOICE_CLOUD is dead"
    )


def test_the_envelope_omits_a_fact_the_door_did_not_compute() -> None:
    """A named fact that is absent is OMITTED, never served null — a partner
    reading a null `next` cannot tell *last page* from *this route does not
    page*."""
    facts = {"total_records": 3, "page": 1, "records": []}
    out = shapes.apply_envelope(facts, shapes.INVOICE_CLOUD)
    assert out == {"count": 3, "page_number": 1, "results": []}
    assert "next" not in out and "remote_utility_id" not in out


def test_the_native_envelope_still_withholds_the_two_page_urls() -> None:
    """What `/customers` has served since `CR-110-BRC04` does not move by one
    byte, and the mechanism is the declaration rather than a flag."""
    facts = {
        "total_records": 3, "page": 1, "page_size": 1000, "total_pages": 1,
        "next": "https://example/next", "previous": None, "records": [],
    }
    out = shapes.apply_envelope(facts, shapes.NATIVE)
    assert set(out) == {"total_records", "page", "page_size", "total_pages", "records"}


# ══════════════════════════════════════════════════════════════════════════
# THE CSV
# ══════════════════════════════════════════════════════════════════════════


def _rows(text: str) -> list[list[str]]:
    import csv, io
    return list(csv.reader(io.StringIO(text)))


def test_the_csv_header_is_the_json_field_names() -> None:
    """The two serialisations of one page name every field identically, so a
    partner moves between them with no mapping table."""
    shaped = shapes.apply_records([BILL], shapes.INVOICE_CLOUD, resource="bills")
    rows = _rows(partner_csv.render(shaped))
    assert rows[0] == list(shaped[0]), "the header row IS the record's keys, in order"
    assert "invoiceNo" in rows[0] and "id" not in rows[0]


def test_the_csv_is_the_same_records_as_the_json_cell_by_cell() -> None:
    shaped = shapes.apply_records([BILL], shapes.NATIVE, resource="bills")
    rows = _rows(partner_csv.render(shaped))
    header, body = rows[0], rows[1]
    for name, cell in zip(header, body):
        value = shaped[0][name]
        if value is None:
            assert cell == "", name
        elif isinstance(value, (dict, list)):
            assert json.loads(cell) == value, name
        else:
            assert cell == str(value), name


def test_rows_lines_gives_one_row_per_line_with_its_gl_code() -> None:
    two = dict(BILL, lines=[
        {"id": 1, "gl_code": "4100", "amount": "100.0000"},
        {"id": 2, "gl_code": "4200", "amount": "42.1800"},
    ])
    rows = _rows(partner_csv.render([two], rows="lines"))
    assert len(rows) == 3, "a header and two line rows"
    assert "line_gl_code" in rows[0]
    codes = [row[rows[0].index("line_gl_code")] for row in rows[1:]]
    assert codes == ["4100", "4200"]
    # ⚠ the bill's own identity is on EVERY row, and the line's `id` did not
    # overwrite it — which is what the `line_` prefix is for.
    numbers = [row[rows[0].index("id")] for row in rows[1:]]
    assert numbers == ["INV-2026-00412", "INV-2026-00412"]


def test_a_bill_with_no_lines_still_produces_one_row() -> None:
    """Dropping it would be DECIDING WHICH ROWS COME BACK, which is the door's
    job and not a renderer's."""
    rows = _rows(partner_csv.render([dict(BILL, lines=[])], rows="lines"))
    assert len(rows) == 2


def test_a_null_is_an_empty_cell_and_never_the_word_none() -> None:
    rows = _rows(partner_csv.render([{"a": None, "b": "x"}]))
    assert rows[1] == ["", "x"]


def test_the_header_row_is_the_union_over_the_page() -> None:
    """Taking the first record's keys would drop a field its neighbour carries
    and the whole page would lose it."""
    rows = _rows(partner_csv.render([{"a": 1}, {"a": 2, "b": 3}]))
    assert rows[0] == ["a", "b"]
    assert rows[1] == ["1", ""]


def test_the_paging_headers_carry_what_the_envelope_carries() -> None:
    headers = partner_csv.paging_headers(total_records=40000, page=3, total_pages=40)
    assert headers == {
        partner_csv.HEADER_TOTAL_RECORDS: "40000",
        partner_csv.HEADER_PAGE: "3",
        partner_csv.HEADER_TOTAL_PAGES: "40",
    }


def test_only_the_exact_spelling_asks_for_csv() -> None:
    """A partner sending `CSV` would silently receive JSON and parse it as a
    table, so the near-misses are refused rather than tolerated."""
    assert partner_csv.wants_csv("csv")
    for near in ("CSV", " CSV ", "text/csv", ".csv", "json", "", None):
        assert not partner_csv.wants_csv(near), near


# ══════════════════════════════════════════════════════════════════════════
# THE SEAM'S NEW FACTS
# ══════════════════════════════════════════════════════════════════════════


def test_the_name_split_is_lossless() -> None:
    """We hold ONE name column, so the split is a presentation of a fact we do
    not have. The honest form keeps the whole name recoverable.

    ⚠ **THE TWO AWKWARD CASES ARE IN THE FIXTURE ON PURPOSE**, because a split
    tested only on *"First Last"* is tested on the case that cannot fail.
    """
    for full in ("Marisol Ruiz", "Maria de la Cruz", "Mary Jane Watson", "Prince", ""):
        first, last = customers_seam.split_name(full)
        rebuilt = " ".join(part for part in (first, last) if part)
        assert rebuilt == full.strip(), full

    assert customers_seam.split_name("Prince") == ("Prince", None), (
        "a one-word name is a FIRST name — a mononym or a business, not a surname"
    )
    assert customers_seam.split_name(None) == (None, None)
    assert customers_seam.split_name("Maria de la Cruz") == ("Maria", "de la Cruz")


def test_project_type_is_a_literal_on_every_bill() -> None:
    """PO 2026-09-17, asked what `projectType` says when one bill covers several
    services: *"a) always \\"Utility Billing\\""*.

    ⚠ **A CONSTANT, WHICH MEANS A LATER LANE MUST NOT DERIVE IT.** Reading the
    bill's services and composing *"Electric, Water"* is the obvious next move
    and is the thing that was ruled against.
    """
    assert billing_seam.PROJECT_TYPE == "Utility Billing"


# ══════════════════════════════════════════════════════════════════════════
# `company_id` IS ACCEPTED, IGNORED AND RECORDED — PO ruling 2026-09-17
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_company_id_no_longer_decides_anything(brazos, dana, wired) -> None:
    """**THE ASSERTION THAT CAN TELL *IGNORED* FROM *STILL CHECKED*.**

    A good id was already a 200 before this wave, so asserting one proves
    nothing. These four calls send a good id, ANOTHER UTILITY'S id, a nonsense
    string and NOTHING AT ALL, and assert **the same status and the same body
    every time**. Under the old check, three of the four were a `403
    COMPANY_MISMATCH`.
    """
    import uuid as _uuid

    bodies = []
    for named in (str(brazos.id), str(_uuid.uuid4()), "302", None):
        serve.reset_partner_limits()
        response = _get(
            brazos,
            partner_api.partner_accounts,
            query={"company_id": named},
            path="/partner/v1/accounts",
        )
        assert response.status_code == 200, (named, _body(response))
        bodies.append(_body(response))

    assert len({bytes(one) for one in bodies}) == 1, (
        "the four answers differ, so something still reads company_id"
    )


@pytest.mark.django_db
def test_what_they_named_is_recorded_without_being_a_refusal(brazos, dana, wired) -> None:
    """A manager can still see *this partner thinks we are 302* on S142 — as
    information, not as a turned-away key."""
    from apps.integrations import models
    serve.reset_partner_limits()
    response = _get(
        brazos,
        partner_api.partner_accounts,
        query={"company_id": "302"},
        path="/partner/v1/accounts",
    )
    assert response.status_code == 200
    with tenant_ctx(brazos):
        run = models.IntegrationRun.objects.order_by("-started_at").first()
    assert "they named 302" in (run.summary or ""), run.summary
    assert "refused" not in (run.summary or "").lower()


@pytest.mark.django_db
def test_the_company_id_the_run_row_carries_is_bounded(brazos, dana, wired) -> None:
    """It is a value a stranger typed and it lands in a line a manager reads."""
    from rest_framework.test import APIRequestFactory

    request = APIRequestFactory().get("/x", {"company_id": "A" * 500 + "\nforged"})
    named = partner_api._company_named(request)
    assert len(named) <= 64 and "\n" not in named


# ══════════════════════════════════════════════════════════════════════════
# `consumer-info` — ITS OWN DOOR SINCE `DEF-INT-5622`
# ══════════════════════════════════════════════════════════════════════════
#
# ⚠ **THESE CASES RAN ON AN ACLARIAN KEY UNTIL 2026-09-17 AND NOW RUN ON THE
# INVOICE CLOUD ONE, WHICH IS NOT TIDYING — IT IS THE DEFECT FIX ARRIVING.**
# `consumer-info` used to be a second address onto `serve_customer`, so any
# partner with the account list could call it and no screen showed it existed.
# It is `serve_consumer_info` now, declared by `pay_invoicecloud_partner` and
# by nothing else, so an Aclarian key is correctly refused and these cases had
# to move to a key that holds the tick.
#
# ⚠ **AND THAT MAKES THEM THE FIRST END-TO-END PROOF OF THE INVOICE CLOUD
# DIALECT** (`DEF-INT-5642`). The envelope below is `results` / `count` and the
# account number is `account_no`, because `shapes.resolve` now answers
# `INVOICE_CLOUD` for this connector — it answered `NATIVE` for every real call
# until the same day, and no case joined the two halves.
#
# `wired_for_documents` is reused rather than copied: it takes its scope FROM
# the manifest, so it granted `serve_consumer_info` the moment the manifest
# declared it — which is that fixture's own docstring coming true.


#: The InvoiceCloud envelope's own words, DERIVED so a shape change moves these
#: cases instead of leaving them asserting a dialect nobody serves.
IC_RECORDS = shapes.INVOICE_CLOUD.envelope["records"]
IC_TOTAL = shapes.INVOICE_CLOUD.envelope["total_records"]


@pytest.mark.django_db
def test_both_selectors_or_neither_is_a_400(brazos, dana, wired_for_documents) -> None:
    for query, code in (
        ({}, "CONSUMER_SELECTOR_REQUIRED"),
        ({"consumer_numbers": "A-1", "consumer_id": "A-2"}, "CONSUMER_SELECTOR_AMBIGUOUS"),
        ({"consumer_numbers": " , , "}, "CONSUMER_SELECTOR_REQUIRED"),
    ):
        serve.reset_partner_limits()
        response = _get(
            brazos,
            partner_api.partner_consumer_info,
            key=DOC_KEY,
            query=query,
            path="/partner/v1/consumer-info",
        )
        assert response.status_code == 400, (query, _body(response))
        assert json.loads(_body(response))["code"] == code, query


@pytest.mark.django_db
def test_a_stranger_gets_the_refusal_and_never_the_400(
    brazos, dana, wired_for_documents
) -> None:
    """⚠ **A `400` HANDED OUT BEFORE THE DOOR IS AN ENUMERATION ORACLE.** It
    would tell an unauthenticated caller that the address is real and that its
    parameters are named such-and-such."""
    serve.reset_partner_limits()
    response = _get(
        brazos,
        partner_api.partner_consumer_info,
        key="sbh_live_not_a_real_key",
        path="/partner/v1/consumer-info",
    )
    assert response.status_code == 404, _body(response)
    assert json.loads(_body(response))["error"] == serve.REFUSAL_SENTENCE


@pytest.mark.django_db
def test_consumer_info_is_the_accounts_composer_plus_two_fields(
    brazos, dana, wired_for_documents, address_stories
) -> None:
    """**ONE IMPLEMENTATION, TWO ADDRESSES.** The day a field is added to one
    and not the other, a partner reading an account at two addresses gets two
    answers from one utility. Two operations now, still one composer.

    ⚠ **`account_no` AND NOT `consumer_no` (`DEF-INT-5623`).** PO 2026-09-17:
    *"it should be account and not customer - theya re lookung for details for
    accounts not customer id"*. The VALUE never moved — it has always been
    `account.account_no` — so this assertion is about the KEY a partner reads,
    which is the whole defect.
    """
    serve.reset_partner_limits()
    listed = json.loads(_body(_get(
        brazos, partner_api.partner_accounts, key=DOC_KEY, path="/partner/v1/accounts"
    )))
    assert listed[IC_RECORDS], "the fixture must seed accounts — a skip reads like a pass"
    assert "consumer_no" not in listed[IC_RECORDS][0], (
        "the partner still reads `consumer_no` and will map it to their CUSTOMER "
        "record — DEF-INT-5623"
    )
    assert "customer_name" not in listed[IC_RECORDS][0]
    number = listed[IC_RECORDS][0]["account_no"]

    serve.reset_partner_limits()
    one = json.loads(_body(_get(
        brazos,
        partner_api.partner_consumer_info,
        key=DOC_KEY,
        query={"consumer_id": number},
        path="/partner/v1/consumer-info",
    )))
    assert one[IC_TOTAL] == 1
    record = one[IC_RECORDS][0]
    assert record["account_no"] == number
    assert "account_name" in record
    # Every key the list serves, served here too — plus exactly one more.
    assert set(listed[IC_RECORDS][0]) <= set(record)
    assert set(record) - set(listed[IC_RECORDS][0]) == {
        # PO 2026-09-17, asked in which APIs it is required: this one, and no
        # other payload of their document carries it.
        "remote_plan_id",
        # ⚠ **AND `opening_balance`, WHICH IS HERE FOR A DIFFERENT REASON AND
        # THE DIFFERENCE MATTERS (`DEF-INT-5587`).** It is not a ruling — it is
        # that the balance read costs a statement PER ACCOUNT, so it may not ride
        # on a route that walks 40,000 of them. If billing ever publishes a
        # batched balance, this one may legitimately move to the list and
        # `remote_plan_id` may not.
        "opening_balance",
    }, "the two consumer-info-only fields"
    assert "payment_received" not in json.dumps(record), (
        "OQ-INT-12399 is OPEN — a money field whose meaning is unruled is not guessed"
    )


@pytest.mark.django_db
def test_consumer_numbers_takes_many(
    brazos, dana, wired_for_documents, address_stories
) -> None:
    """⚠ **THE REQUEST PARAMETERS KEEP INVOICE CLOUD'S OWN WORDS.**
    `consumer_numbers` and `consumer_id` are names in THEIR document, the way
    `bill-download/` keeps their trailing slash. `DEF-INT-5623` is about the
    word OUR surface uses for OUR thing, and a parameter they send us is
    theirs."""
    serve.reset_partner_limits()
    listed = json.loads(_body(_get(
        brazos, partner_api.partner_accounts, key=DOC_KEY, path="/partner/v1/accounts"
    )))
    numbers = [one["account_no"] for one in listed[IC_RECORDS][:2]]
    assert len(numbers) == 2, "the fixture must seed at least two accounts"

    serve.reset_partner_limits()
    many = json.loads(_body(_get(
        brazos,
        partner_api.partner_consumer_info,
        key=DOC_KEY,
        query={"consumer_numbers": ",".join(numbers)},
        path="/partner/v1/consumer-info",
    )))
    assert many[IC_TOTAL] == 2
    assert {one["account_no"] for one in many[IC_RECORDS]} == set(numbers)


# ══════════════════════════════════════════════════════════════════════════
# `bill-download`
# ══════════════════════════════════════════════════════════════════════════


#: **THE REAL CONNECTOR, NOT A PROBE.** Until 2026-09-17 this file registered a
#: whole connector of its own — `erp_cr111_document_probe` — because
#: `bill-download` needs a `serve_document` operation and **no manifest declared
#: one** (`DEF-INT-5586`). The manifest that would was blocked on
#: `DEF-INT-5574`, and the PO ruled that block on 2026-09-17: *"a) Two
#: connectors — one for the reading half, live now"*.
#:
#: `pay_invoicecloud_partner` declares `serve_document`, so these cases now run
#: against a key a utility can actually issue, and the probe is gone. **That is
#: the hold expiring, and `test_the_real_connector_declares_serve_document`
#: below is the case that made it a failure rather than a thing to remember**
#: (hard-won law 2).
#:
#: ⚠ **THE FACT THE PROBE EXISTED TO WORK AROUND IS KEPT, BECAUSE IT IS STILL
#: TRUE OF EVERY OTHER CONNECTOR:** a credential scoped to an operation its own
#: manifest does not declare makes `services.start_run` raise, so the route
#: answers **500** rather than a refusal. That state is unreachable in the
#: product — a real scope is drawn from the manifest's own operations — which is
#: why a scope could not simply be widened and a connector had to be found.
DOC_CONNECTOR = "pay_invoicecloud_partner"
DOC_KEY = "sbh_live_ic_partner_brazosbend_do_not_reuse"
DOC_HINT = "••••euse"


@pytest.fixture()
def wired_for_documents(brazos, dana):
    """A live connection and an issued key on the REAL InvoiceCloud read half.

    The scope is every operation the manifest declares, taken FROM the manifest
    — never typed — so the day a fifth operation arrives this fixture grants it
    and the day one leaves this fixture stops granting it.
    """
    from apps.integrations import models, services
    from apps.integrations.registry import REGISTRY
    from apps.integrations.runners import serve as serve_runner
    from core import crypto

    serve.reset_partner_limits()
    manifest = REGISTRY.require(DOC_CONNECTOR)
    with tenant_ctx(brazos):
        connection = models.IntegrationConnection.objects.create(
            tenant=brazos, provider_key=DOC_CONNECTOR, label="InvoiceCloud reads",
            environment=models.ENVIRONMENT_PRODUCTION, status=models.STATUS_WORKING,
            enabled=True, cadence=models.CADENCE_MANUAL,
            config={serve_runner.ALLOWLIST_CONFIG_KEY: ALLOWLIST_FOR_PROBE},
        )
        services.record_credential(
            actor=dana, connection=connection, payload=DOC_KEY, masked_hint=DOC_HINT,
            blind_index=crypto.blind_index(
                DOC_KEY, context=serve_runner.ISSUED_KEY_BLIND_INDEX_CONTEXT
            ),
            scope=[one.name for one in manifest.operations],
        )
    return connection


def test_the_real_connector_declares_serve_document() -> None:
    """**THE HOLD-EXPIRY CASE, TURNED ROUND ON THE DAY IT EXPIRED.**

    It used to read `test_no_manifest_declares_serve_document_yet` and assert
    that NO manifest declared the operation, naming the first one that did —
    which is what went red when `pay_invoicecloud_partner` landed and told this
    file to delete its probe. **It is not deleted, it is inverted**, because the
    thing worth asserting for ever is that `bill-download` has a door: an
    address whose operation no manifest declares is unreachable by every key
    that can exist, and that is how it shipped (`DEF-INT-5586`).

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** asserting that SOME manifest
    declares it. A test connector registered by a sibling fixture would satisfy
    that and the product would still have no door, which is the exact state this
    case exists to refuse. So it asserts the declaring set is non-empty **and
    that every operation `SERVED_ROUTES` names is declared by a manifest we
    SHIP** — the durable version `DEF-INT-5586`'s own prevention field asks for.
    """
    from apps.integrations import manifests

    declaring = [
        manifest.key
        for manifest in manifests.MANIFESTS
        for one in manifest.operations
        if one.name == "serve_document"
    ]
    assert declaring == ["pay_invoicecloud_partner"], declaring

    shipped = {
        one.name
        for manifest in manifests.MANIFESTS
        for one in manifest.operations
    }
    unreachable = sorted(
        {operation for operation, _ in partner_api.SERVED_ROUTES.values()} - shipped
    )
    assert unreachable == [], (
        f"{unreachable} is named by a partner address and declared by no manifest we "
        "ship, so no key that can exist may call it (DEF-INT-5586)"
    )


@pytest.mark.django_db
def test_bill_download_without_a_bill_id_is_a_400(brazos, dana, wired_for_documents) -> None:
    serve.reset_partner_limits()
    response = _get(
        brazos, partner_api.partner_bill_download, key=DOC_KEY,
        path="/partner/v1/bill-download/",
    )
    assert response.status_code == 400, _body(response)
    assert json.loads(_body(response))["code"] == "BILL_ID_REQUIRED"


@pytest.mark.django_db
def test_a_bill_that_is_not_ours_answers_the_same_bytes_as_a_refused_key(
    brazos, dana, wired_for_documents
) -> None:
    """⚠ **THE WHOLE SECURITY ARGUMENT OF THIS ROUTE, AND THE ASSERTION IS THE
    BODY AND NOT THE STATUS.** A 404 is also what an unknown id gets, so a
    per-case status check proves nothing. *No such bill* and *not yours* must be
    ONE answer, or a partner could walk our invoice numbers and learn which ones
    exist.
    """
    serve.reset_partner_limits()
    unknown = _get(
        brazos,
        partner_api.partner_bill_download,
        key=DOC_KEY,
        query={"bill_id": "INV-0000-99999"},
        path="/partner/v1/bill-download/",
    )
    serve.reset_partner_limits()
    stranger = _get(
        brazos,
        partner_api.partner_bill_download,
        key="sbh_live_not_a_real_key",
        query={"bill_id": "INV-0000-99999"},
        path="/partner/v1/bill-download/",
    )
    assert unknown.status_code == stranger.status_code == 404
    assert bytes(_body(unknown)) == bytes(_body(stranger)), (
        "an unknown bill and a refused key must be the same bytes (BR-INT-044)"
    )


# ══════════════════════════════════════════════════════════════════════════
# `limit`, and the trailing slash
# ══════════════════════════════════════════════════════════════════════════


def test_limit_is_a_synonym_and_page_size_wins_when_both_are_sent() -> None:
    from rest_framework.test import APIRequestFactory

    factory = APIRequestFactory()
    assert partner_api._page_params(factory.get("/x", {"limit": "25"}))[1] == 25
    assert partner_api._page_params(factory.get("/x", {"page_size": "10"}))[1] == 10
    assert partner_api._page_params(
        factory.get("/x", {"page_size": "10", "limit": "25"})
    )[1] == 10, "the name we PUBLISH wins"
    assert partner_api._page_params(factory.get("/x", {}))[1] == partner_api.DEFAULT_PAGE_SIZE
    # ⚠ NFR-5: the ceiling clamps, it does not refuse, and there is no cap on
    # what a tenant may hold — only on what one call returns.
    assert partner_api._page_params(
        factory.get("/x", {"limit": "999999"})
    )[1] == partner_api.MAX_PAGE_SIZE


def test_every_partner_address_is_registered_with_and_without_a_slash() -> None:
    """Their document writes `/bill-download/` and the others without a slash.
    `APPEND_SLASH` would answer a `301`, which a partner's client may not follow
    and may drop the bearer token on."""
    from apps.integrations import partner_urls

    spellings = {str(one.pattern) for one in partner_urls.urlpatterns}
    for name in partner_urls.PARTNER_ROUTES:
        assert f"partner/v1/{name}" in spellings, name
        assert f"partner/v1/{name}/" in spellings, name


def test_the_two_new_addresses_are_declared_and_go_through_the_same_door() -> None:
    """A route registered beside the loop would have NO tenant context and would
    read zero rows for a valid key — which looks exactly like a bad key."""
    from apps.integrations import partner_urls

    assert "consumer-info" in partner_urls.PARTNER_ROUTES
    assert "bill-download" in partner_urls.PARTNER_ROUTES
    # ⚠ **THIS ASSERTED `== "serve_customer"` UNTIL 2026-09-17, AND THE
    # SENTENCE BESIDE IT WAS THE DESIGN IT WAS PROTECTING** — *"a second
    # ADDRESS onto one door — not a fifth tick on the set-up screen"*. That
    # design bought a real safety property (one tick closed both addresses)
    # with a cost nobody had counted: **the address could not be seen**. The
    # connector screen draws one row per operation, so `consumer-info` drew
    # none, and the PO counted four APIs where five exist (`DEF-INT-5622`).
    # Its own operation gives the clerk the same control in a stronger form.
    assert partner_api.SERVED_ROUTES["consumer-info"][0] == "serve_consumer_info", (
        "its own door, its own tick, its own row — DEF-INT-5622"
    )
    assert partner_api.SERVED_ROUTES["accounts"][0] == "serve_customer"


# ══════════════════════════════════════════════════════════════════════════
# THE TWO ADDRESSES, AND THE CSV OVER THE WIRE
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_territory_data_carries_both_addresses_and_they_differ(
    brazos, dana, wired, address_stories
) -> None:
    """Hard rule 8, both legs, read back as VALUES.

    ⚠ **THE LANDLORD IS THE CASE THAT MATTERS AND IT IS IN THE FIXTURE ON
    PURPOSE.** Its bill goes to `PO Box 9912, Dallas` and its meter is in Austin,
    so an implementation that served the service address for both — or the
    mailing address for both — cannot look right. Asserting only that the keys
    are present would pass on either.
    """
    serve.reset_partner_limits()
    body = json.loads(_body(_get(
        brazos, partner_api.partner_accounts, path="/partner/v1/accounts"
    )))
    territories = [one["territory_data"] for one in body["records"]]
    assert territories, "no records"
    for one in territories:
        assert set(one) == {"service_address", "billing_address"}

    landlord = [one for one in territories if "9912" in str(one["billing_address"] or "")]
    assert landlord, f"the landlord's mailing address never reached the payload: {territories}"
    story = landlord[0]
    assert story["billing_address"] != story["service_address"], (
        "the bill goes where the meter is not — serving one for both is the defect"
    )
    assert "Dallas" in story["billing_address"]


@pytest.mark.django_db
def test_an_account_with_no_mailing_row_is_billed_where_it_takes_service(
    brazos, dana, wired_for_documents, address_stories
) -> None:
    """**THE FALLBACK IS PART OF THE RULE, NOT A CONSOLATION.**

    ⚠ **IT IS EXERCISED BY REMOVING A ROW ON PURPOSE, BECAUSE THE FIXTURE
    CANNOT REACH IT OTHERWISE.** `create_account` writes a mailing address for
    every account it opens, so **every account in this product has one** and the
    fallback branch is unreachable through the front door. Discovered by
    asserting the opposite and watching it fail with `assert set()` — which is
    the only reason this case exists in this shape rather than as a partition of
    the fixture that would have "passed" by never running.

    Returning `null` here instead would tell a finance system *we do not know
    where to send this* about an account we post to every month.
    """
    from apps.customers import models as customers_models

    with tenant_ctx(brazos):
        row = customers_models.Address.objects.filter(
            tenant_id=brazos.id, kind=customers_seam.ADDRESS_KIND_MAILING
        ).first()
        assert row is not None, "the fixture seeds no mailing address at all"
        orphaned = str(
            customers_models.Account.objects.get(pk=row.account_id).account_no
        )
        row.delete()

    serve.reset_partner_limits()
    body = json.loads(_body(_get(
        brazos,
        partner_api.partner_consumer_info,
        key=DOC_KEY,
        query={"consumer_id": orphaned},
        path="/partner/v1/consumer-info",
    )))
    story = body[IC_RECORDS][0]["territory_data"]
    assert story["billing_address"] == story["service_address"]
    assert story["service_address"], "the walk to the premises returned nothing"


@pytest.mark.django_db
def test_the_csv_over_the_wire_is_the_json_page(brazos, dana, wired, address_stories) -> None:
    """`&format=csv` on a live call — the same records, the same page, and the
    counts in headers because a CSV body has no envelope."""
    serve.reset_partner_limits()
    as_json = json.loads(_body(_get(
        brazos, partner_api.partner_accounts, path="/partner/v1/accounts"
    )))
    serve.reset_partner_limits()
    csv_response = _get(
        brazos, partner_api.partner_accounts,
        query={"format": "csv"}, path="/partner/v1/accounts",
    )
    assert csv_response.status_code == 200
    assert csv_response["Content-Type"].startswith("text/csv")
    assert csv_response[partner_csv.HEADER_TOTAL_RECORDS] == str(as_json["total_records"])
    assert csv_response[partner_csv.HEADER_PAGE] == str(as_json["page"])
    assert csv_response[partner_csv.HEADER_TOTAL_PAGES] == str(as_json["total_pages"])

    rows = _rows(csv_response.content.decode("utf-8"))
    assert rows[0] == list(as_json["records"][0]), "the header row IS the JSON field names"
    assert len(rows) - 1 == len(as_json["records"]), "the CSV is the same page, not more"


@pytest.mark.django_db
def test_the_csv_is_paged_and_there_is_no_download_everything(
    brazos, dana, wired, address_stories
) -> None:
    """`NFR-3`. A CSV export is exactly where an unpaginated list gets built a
    second time — `GET /outstandings` is the named breach (`DEF-PAY-4221`)."""
    serve.reset_partner_limits()
    response = _get(
        brazos, partner_api.partner_accounts,
        query={"format": "csv", "page_size": "1"}, path="/partner/v1/accounts",
    )
    rows = _rows(response.content.decode("utf-8"))
    assert len(rows) == 2, "a header and ONE record — the page was honoured"
    assert int(response[partner_csv.HEADER_TOTAL_RECORDS]) > 1
    assert int(response[partner_csv.HEADER_TOTAL_PAGES]) > 1

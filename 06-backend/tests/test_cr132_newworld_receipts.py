# ── Trace ──────────────────────────────────────────────
# Change:  CR-132-BRC07 — New World / Logos reads our receipts.
# Rules:   CLAUDE.md hard rule 2 (money DISPLAYED to 2 — their fields are
#          `9,2`) · hard rule 4 (a READ; and the origin column is write-once) ·
#          hard rule 5 (the distributions ARE our credit legs)
# Proves:  the four-level structure against a RECORDED fixture · that an
#          unbalanced receipt is SENT, flagged and counted · that the card
#          fields are absent from every surface · that the GL code comes from
#          the one seam and not a second lookup
# ───────────────────────────────────────────────────────
"""New World / Logos — the receipt projection, proved by trying to break it.

⚠ **THE BALANCE CASE IS INVERTED FROM THE OBVIOUS ONE, AND THAT IS THE POINT.**
The natural test to write is *a receipt that does not balance is refused*. The
PO ruled the opposite on 2026-09-22 — *"please send receipt even if it is not
balance"* — because **a refused receipt is money that silently never reaches
the City's books, and an unbalanced one is money that arrives wrong and can be
found and fixed.** So the case below asserts that a one-cent-short receipt is
EMITTED, that it is FLAGGED, that the difference is STATED as a figure, and
that **nothing was plugged**: the three distributions come out at their own
rounded amounts and their sum is still 99.99.

**What would make these pass wrongly** (hard-won law 7, habit 2):

  * `test_the_fixture_is_what_we_emit` would pass wrongly if the fixture were
    regenerated from the code in the same run. It is not: the file is read from
    disk and compared byte for byte, and it was recorded in a separate act and
    committed. A change to the projection breaks it, which is the whole job.
  * `test_a_short_receipt_is_sent_and_flagged` would pass wrongly if it only
    checked `balanced is False` — a builder that emitted nothing at all would
    satisfy that. It asserts the bytes contain all three distributions AND the
    transaction amount, so *sent* is checked separately from *flagged*.
  * `test_no_card_field_reaches_any_surface` would pass wrongly if it searched
    only this module. It sweeps the projection, the manifest and the recorded
    fixture, because the absence has to hold on every one of them.
"""

from __future__ import annotations

import pathlib
from datetime import date
from decimal import Decimal

from apps.integrations import mappings, newworld

FIXTURE = (
    pathlib.Path(newworld.__file__).resolve().parent
    / "fixtures"
    / "newworld"
    / "receipt_v1.xml"
)

#: The four card attribute names. Since 2026-10-21 (PO, option A) they are
#: written present and ALWAYS empty; this test file is G130's NAME_HOLDER and
#: is the only place outside `newworld.CARD_ATTRIBUTES` that may quote them,
#: because it plants a value on purpose to prove the validator refuses it.
CARD_FIELDS = (
    "ReceiptPaymentCreditCardNumber",
    "ReceiptPaymentCreditCardType",
    "ReceiptPaymentCreditCardExpirationDate",
    "ReceiptPaymentCreditCardValidationNumber",
)

DAY = date(2026, 9, 15)


def _receipt(
    *,
    number: str,
    amount: str,
    distributions: list[tuple[str | None, str]],
    payment_type: str = mappings.NEWWORLD_PAYMENT_OTHER,
    other_type: str = "ACH",
    check_number: str = "",
    bill: str = "",
    name: str = "Rosa Delgado",
    description: str | None = None,
) -> newworld.Receipt:
    """One receipt built from the real dataclasses — no database.

    ⚠ **THE PROJECTION IS EXERCISED, NOT IMITATED.** These are
    `newworld.Receipt`, `.Transaction`, `.Distribution` and `.PaymentNode`
    themselves, so the rounding, the field widths and the element order under
    test are the shipped ones. What is stubbed is only where the values came
    from.
    """
    return newworld.Receipt(
        number=newworld.RECEIPT_NUMBER_BLANK,
        voided=False,
        entered_date=DAY,
        recorded_date=DAY,
        gl_date=DAY,
        received_from=name,
        description=number if description is None else description,
        cashier=newworld.RECEIPT_CASHIER,
        transactions=(
            newworld.Transaction(
                type="UTILITY",
                amount=Decimal(amount),
                description=number if description is None else description,
                ar_customer_number="AC-2026-00036",
                ar_bill_type="UTILITY",
                ar_bill_number=bill,
                distributions=tuple(
                    newworld.Distribution(
                        account=account,
                        amount=Decimal(value),
                        type=newworld.DISTRIBUTION_CREDIT,
                    )
                    for account, value in distributions
                ),
            ),
        ),
        payments=(
            newworld.PaymentNode(
                type=payment_type,
                amount=Decimal(amount),
                check_number=check_number,
                other_type=other_type,
            ),
        ),
        our_number=number,
    )


def _code_only(path: pathlib.Path) -> str:
    """A module's CODE, with every comment and docstring removed.

    ⚠ **IT EXISTS BECAUSE THE FIRST DRAFT OF THE TWO CHECKS BELOW WENT RED ON
    THEIR OWN SUBJECT'S PROSE**, which is `DEF-INT-4258`'s shape exactly: a
    check judging a RAW LINE, where the thing it forbids is spelled out in a
    docstring precisely to warn the next reader off it. `seams/payments.py`
    says *"`webhook_key__startswith` would look right and silently omit real
    ones"* — the correct thing to write, and a substring search called it a
    violation.

    **A file that explains what it must not do is doing the right thing.** So
    the question is asked of the code: parse, drop every docstring, and
    `ast.unparse`, which discards comments on the way.
    """
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = getattr(node, "body", [])
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(tree)


def _bytes(*receipts: newworld.Receipt) -> bytes:
    """**The shipped serialiser, not a copy of it.**

    ⚠ **THIS WAS A SIX-LINE REIMPLEMENTATION OF `newworld.emit`'s TAIL AND IT
    MADE EVERY BALANCE CASE BELOW INCAPABLE OF FAILING (CLAUDE.md law 7).**
    The red proof is what found it: a refusal was inserted into `emit` —
    reinstating the exact rule the PO reversed on 2026-09-22 — and all
    seventeen cases stayed GREEN, because none of them went anywhere near
    `emit`. They were proving a property of the test file.

    `newworld.render` was split out of `emit` in the same commit so the path
    the endpoint actually calls is the path under test, and the copy is gone.
    """
    return newworld.render(receipts)


# ── the structure, against the recorded fixture ─────────────────────────────


def test_the_fixture_is_what_we_emit():
    """Byte for byte. A schema written from their prose is a claim; this is
    evidence, and it is the discipline every other codec in this module is held
    to (`fixtures/*/PROVENANCE`).

    ⚠ **IT CANNOT PASS WRONGLY BY REGENERATING ITSELF.** The fixture is read
    from disk and was recorded in a separate act and committed; this test only
    ever compares. Change the projection and it goes red, which is the job.
    """
    one = _receipt(
        number="PMT-2609-0187",
        amount="142.1800",
        distributions=[("1200", "142.1800")],
        bill="INV-2609-00412",
    )
    two = _receipt(
        number="PMT-2609-0188",
        amount="200.0000",
        distributions=[("1200", "142.1800"), ("2400", "57.8200")],
        payment_type=mappings.NEWWORLD_PAYMENT_CHARGE,
        other_type="",
        name="Marcus Hale",
        description="PMT-2609-0188 \u00b7 Paid online",
    )
    three = _receipt(
        number="PMT-2609-0189",
        amount="100.0000",
        distributions=[("4100", "33.3333"), ("4105", "33.3333"), ("4110", "33.3334")],
        bill="INV-2609-00418",
        name="Aisha Bennett",
    )
    assert FIXTURE.exists(), "the recorded fixture is the evidence; it must be committed"
    assert _bytes(one, two, three) == FIXTURE.read_bytes()
    # ⚠ AND THE FIXTURE ITSELF PASSES NEW WORLD'S CONFIRMED TEMPLATE (2026-10-21,
    # DEF-INT-10304). Byte-equality alone proved only that the output was
    # STABLE: the fixture was recorded from this code, in the wrong shape, and
    # this case was green for a month over it.
    assert newworld.validate(FIXTURE.read_bytes()) == []


def test_the_four_levels_are_nested_the_way_their_spec_draws_them():
    """Header ▸ transaction ▸ distribution, and the payment node a SIBLING of
    the transaction rather than inside it. Their importer reads the nesting,
    so a flat file with the right field names would parse to nothing."""
    from xml.etree import ElementTree as ET

    root = ET.fromstring(
        _bytes(_receipt(number="PMT-1", amount="10.0000", distributions=[("1200", "10.0000")]))
    )
    header = root.find("ReceiptHeaderLevel")
    assert header is not None
    transaction = header.find("ReceiptTransactionLevel")
    assert transaction is not None
    assert transaction.find("ReceiptTransactionGLDistributionLevel") is not None
    # the payment node hangs off the HEADER, not off the transaction
    assert header.find("ReceiptPaymentLevel") is not None
    assert transaction.find("ReceiptPaymentLevel") is None


# ── the money rule, as the PO reversed it ───────────────────────────────────


def test_a_balanced_receipt_states_a_zero_difference():
    one = _receipt(
        number="PMT-2609-0187",
        amount="142.1800",
        distributions=[("1200", "142.1800")],
    )
    assert one.balanced is True
    assert one.difference == Decimal("0.00")
    assert one.transactions[0].distributed == Decimal("142.18")


def test_a_split_receipt_balances_because_the_legs_are_our_own_entry():
    """$200.00 = $142.18 against bills + $57.82 carried as credit — our
    journal entry's two credit legs, unchanged. **Nothing is allocated here**,
    which is why it foots: hard rule 5 already made the credits sum to the
    debit, and the debit IS the payment."""
    two = _receipt(
        number="PMT-2609-0188",
        amount="200.0000",
        distributions=[("1200", "142.1800"), ("2400", "57.8200")],
    )
    assert two.balanced is True
    assert two.transactions[0].distributed == Decimal("200.00")


def test_a_short_receipt_is_sent_and_flagged_and_never_plugged():
    """⚠ **THE RULE THE PO REVERSED.** $100.00 across three services stored as
    33.3333 · 33.3333 · 33.3334 rounds to 33.33 three times — 99.99, one cent
    short. It goes.

    Three separate assertions, because *sent*, *flagged* and *not plugged* are
    three different failures:
      * SENT — the bytes carry the receipt and all three distributions;
      * FLAGGED — `balanced` is False and `difference` states `0.01`;
      * NOT PLUGGED — no fourth distribution appeared, no amount was nudged,
        and the sum is still 99.99 rather than 100.00.
    """
    short = _receipt(
        number="PMT-2609-0189",
        amount="100.0000",
        distributions=[("4100", "33.3333"), ("4105", "33.3333"), ("4110", "33.3334")],
    )

    # FLAGGED
    assert short.balanced is False
    assert short.difference == Decimal("0.01")
    assert short.transactions[0].distributed == Decimal("99.99")

    # SENT — and this is the assertion that would be missing if the test only
    # checked the flag: a builder that emitted nothing would satisfy that.
    # Attributes since 2026-10-21 (DEF-INT-10304); child elements until then.
    body = _bytes(short)
    assert b'ReceiptTransactionAmount="100.00"' in body
    assert body.count(b"<ReceiptTransactionGLDistributionLevel ") == 3
    assert body.count(b'DistributionAmount="33.33"') == 3

    # NOT PLUGGED — no balancing line, and no amount adjusted to fit.
    assert b'DistributionAmount="33.34"' not in body
    assert b'DistributionAmount="0.01"' not in body


def test_the_page_reports_how_many_were_short_and_by_how_much():
    """*Never silently* is the half that makes *send it* safe. A count nobody
    computes is the same silence one step further along."""
    good = _receipt(number="PMT-A", amount="10.0000", distributions=[("1200", "10.0000")])
    short = _receipt(
        number="PMT-B",
        amount="100.0000",
        distributions=[("4100", "33.3333"), ("4105", "33.3333"), ("4110", "33.3334")],
    )
    emission = newworld.Emission(body=_bytes(good, short), receipts=(good, short))
    assert emission.short_count == 1
    assert emission.short_total == Decimal("0.01")
    assert emission.unbalanced() == [{"receipt": "PMT-B", "difference": "0.01"}]


def test_a_distribution_with_no_gl_account_goes_out_empty_and_is_counted():
    """PO 2026-09-22: a GL account ALWAYS travels, so an unresolvable one is an
    exception. **Sent and flagged, never zero-filled** — a zero GL account and
    a plug distribution line are the same act."""
    unresolved = _receipt(
        number="PMT-C", amount="10.0000", distributions=[(None, "10.0000")]
    )
    body = _bytes(unresolved)
    assert b'GLAccountNumber=""' in body
    assert b'GLAccountNumber="0"' not in body
    assert unresolved.unresolved_accounts == 1
    emission = newworld.Emission(body=body, receipts=(unresolved,))
    assert emission.unresolved_gl_count == 1


def test_the_ruled_empty_fields_are_present_and_empty_never_zero():
    """`DueToDueFromFund` and the distribution-level `ProjectCode1/2/3`.

    ⚠ AMENDED 2026-10-21 (DEF-INT-10304): until then the project codes were
    asserted at BOTH levels. The confirmed template carries them only on the
    distribution level, so they are counted once — and their absence at
    transaction level is its own case below."""
    body = _bytes(
        _receipt(number="PMT-D", amount="10.0000", distributions=[("1200", "10.0000")])
    )
    assert b'DueToDueFromFund=""' in body
    assert b'DueToDueFromFund="0"' not in body
    assert body.count(b'ProjectCode1=""') == 1
    assert body.count(b'ProjectCode3=""') == 1


# ── the tender mapping the PO ruled ─────────────────────────────────────────


def test_the_seven_tenders_map_as_the_po_ruled():
    """PO 2026-09-22: *"we send ACH, Moenry Order and Lockbox - as mapping from
    our side and wil ask them to map it at their end"*."""
    assert mappings.newworld_payment_type("cash", None) == ("0", "")
    assert mappings.newworld_payment_type("check", None) == ("1", "")
    assert mappings.newworld_payment_type("card", None) == ("2", "")
    assert mappings.newworld_payment_type("wire", None) == ("4", "")
    assert mappings.newworld_payment_type("ach", None) == ("3", "ACH")
    assert mappings.newworld_payment_type("money_order", None) == ("3", "Money order")
    assert mappings.newworld_payment_type("lockbox", None) == ("3", "Lockbox")


def test_our_own_bank_transfer_is_ach_and_not_a_wire():
    """This product's *Bank transfer* is the ACH tender — `seams/payments.py`
    records it mapping to a partner's `ACHCHECK`. A wire is a different
    instrument with different fees and a different clearing window, so filing
    it as one would misreport every such receipt."""
    assert mappings.newworld_payment_type("bank_transfer", None) == ("3", "ACH")


def test_a_clerk_mapping_row_wins_and_can_change_the_word_without_a_rebuild():
    """⚠ **THE DEPENDENCY ON NEW WORLD, MADE SURVIVABLE.** Their validation set
    is held on their side; until they add `ACH`, `Money order` and `Lockbox`,
    receipts carrying those words bounce. A different spelling coming back from
    their team must be a configuration change, not a release."""
    # one of their five type numbers IS the type
    assert mappings.newworld_payment_type("ach", "4") == ("4", "")
    # anything else is their OTHER-TYPE word, and the type is Other
    assert mappings.newworld_payment_type("ach", "ACH Debit") == ("3", "ACH Debit")


def test_an_unknown_tender_goes_as_other_under_our_own_word_never_a_guess():
    """A tender is the tenant's own lookup row, so a utility may add one we
    have never seen. Sending OUR word is a fact; picking one of their four
    named types for a tender we cannot identify is a plausible value."""
    assert mappings.newworld_payment_type("crypto", None) == ("3", "crypto")


def test_a_payment_with_no_tender_is_other_with_no_word():
    """An adjustment or a transfer leg took no money. *Other* is true about it,
    and it is not the unmapped case."""
    assert mappings.newworld_payment_type("", None) == ("3", "")


# ── the absence that is the deliverable ─────────────────────────────────────


def test_no_card_value_reaches_any_surface():
    """⚠ **CARD DATA IS NOT BUILT; THE NAMES TRAVEL EMPTY.** A card payment is
    `ReceiptPaymentType = 2` with no card number.

    ⚠ AMENDED 2026-10-21 (DEF-INT-10304). Until then this asserted the four
    names were never quoted anywhere. PO, option A: *"Always write all four as
    `""`"* — so the names live in exactly ONE tuple, `newworld.CARD_ATTRIBUTES`,
    and nowhere else in code; the manifest and the mappings never quote them;
    and in the recorded fixture every occurrence is an EMPTY attribute.
    """
    import re

    assert newworld.CARD_ATTRIBUTES == CARD_FIELDS
    root = pathlib.Path(newworld.__file__).resolve().parent
    for surface in (root / "mappings.py", root / "manifests" / "erp_newworld.py"):
        text = surface.read_text(encoding="utf-8")
        for name in CARD_FIELDS:
            assert f'"{name}"' not in text, f"{name} is quoted as a value in {surface.name}"
    code = _code_only(root / "newworld.py")
    for name in CARD_FIELDS:
        # once, in the tuple — never a second literal a value could ride on
        assert code.count(f"'{name}'") == 1, name
    recorded = FIXTURE.read_text(encoding="utf-8")
    for name in CARD_FIELDS:
        occurrences = re.findall(rf'{name}="([^"]*)"', recorded)
        assert occurrences == [""] * 3, f"{name} must be present and empty on all three"
        assert f"<{name}" not in recorded


def test_the_card_receipt_in_the_fixture_carries_charge_and_four_empty_card_attributes():
    """The second recorded receipt is a card payment. It carries type `2` and
    the four card attributes present and EMPTY (PO 2026-10-21, option A) —
    which is what makes the sweep above meaningful rather than vacuous.

    ⚠ AMENDED 2026-10-21: it asserted the names were absent until then."""
    from xml.etree import ElementTree as ET

    card = ET.fromstring(FIXTURE.read_bytes()).findall("ReceiptHeaderLevel")[1]
    node = card.find("ReceiptPaymentLevel")
    assert node is not None and node.get("ReceiptPaymentType") == "2"
    for name in CARD_FIELDS:
        assert node.get(name) == ""


# ── the confirmed template (PO 2026-10-21, DEF-INT-10304) ───────────────────
#
# The decision log of 2026-10-21, "New World / Logos receipt XML: attributes on
# a `<ROOT>` document; five answers": every field an ATTRIBUTE, root `<ROOT>`,
# VoidedFlag 0/1, dates MM/DD/YYYY, every attribute always present, the card
# attributes always "", no project codes at transaction level — and a file is
# validated against the template before it is sent or served.

#: The template the PO pasted, written out HERE BY HAND rather than read from
#: `newworld`'s tuples, so a change to those tuples cannot move this test with
#: it. Element → its attributes, in the template's order.
TEMPLATE = {
    "ReceiptHeaderLevel": [
        "ReceiptNumber", "VoidedFlag", "PaymentEnteredDate", "PaymentRecordedDate",
        "PaymentGLDate", "ReceivedFromName", "ReceiptDescription", "ReceiptCashier",
    ],
    "ReceiptTransactionLevel": [
        "ReceiptTransactionType", "ReceiptTransactionAmount", "ReceiptTransactionDescription",
        "ReceiptTransactionARCustomerNumber", "ReceiptTransactionARBillType",
        "ReceiptTransactionARBillNumber",
    ],
    "ReceiptTransactionGLDistributionLevel": [
        "GLAccountNumber", "DueToDueFromFund", "ProjectCode1", "ProjectCode2", "ProjectCode3",
        "DistributionAmount", "DistributionType",
    ],
    "ReceiptPaymentLevel": [
        "ReceiptPaymentType", "ReceiptPaymentAmount", "ReceiptPaymentCheckNumber",
        *CARD_FIELDS, "ReceiptPaymentOtherType",
    ],
}


def _one(**kwargs) -> bytes:
    defaults = dict(number="PMT-1", amount="10.0000", distributions=[("1200", "10.0000")])
    defaults.update(kwargs)
    return _bytes(_receipt(**defaults))


def test_the_root_is_ROOT_and_no_element_carries_text():
    from xml.etree import ElementTree as ET

    root = ET.fromstring(FIXTURE.read_bytes())
    assert root.tag == "ROOT"
    for element in root.iter():
        assert not (element.text or "").strip(), f"<{element.tag}> carries text"
        assert not (element.tail or "").strip(), f"text after <{element.tag}>"


def test_every_template_attribute_is_present_in_the_templates_order():
    """Including the empty ones — `ReceiptNumber`, `ReceiptTransactionARBillNumber`
    on receipt 2, `ReceiptPaymentOtherType` on the card receipt — and nothing
    else. ElementTree keeps insertion order, so the order is checked too."""
    from xml.etree import ElementTree as ET

    root = ET.fromstring(FIXTURE.read_bytes())
    seen = 0
    for element in root.iter():
        if element.tag == "ROOT":
            assert dict(element.attrib) == {}
            continue
        assert list(element.attrib) == TEMPLATE[element.tag], element.tag
        seen += 1
    # 3 headers + 3 transactions + 6 distributions + 3 payments
    assert seen == 15


def test_the_card_receipt_writes_other_type_as_an_empty_attribute():
    """`ReceiptPaymentOtherType` was OMITTED when empty until 2026-10-21."""
    body = _one(payment_type=mappings.NEWWORLD_PAYMENT_CHARGE, other_type="")
    assert b'ReceiptPaymentOtherType=""' in body


def test_voided_flag_is_zero_or_one_never_true_or_false():
    receipt = _receipt(number="PMT-V", amount="10.0000", distributions=[("1200", "10.0000")])
    import dataclasses

    voided = dataclasses.replace(receipt, voided=True)
    assert b'VoidedFlag="0"' in _bytes(receipt)
    assert b'VoidedFlag="1"' in _bytes(voided)
    for body in (_bytes(receipt), _bytes(voided)):
        assert b"true" not in body and b"false" not in body
        assert newworld.validate(body) == []


def test_the_three_dates_are_mm_dd_yyyy():
    body = _one()
    for name in ("PaymentEnteredDate", "PaymentRecordedDate", "PaymentGLDate"):
        assert f'{name}="09/15/2026"'.encode() in body
    assert b"2026-09-15" not in body


def test_no_project_code_at_transaction_level():
    """Removed 2026-10-21 by our judgment under law 13: the confirmed template
    carries project codes only on the distribution level, and their schema's
    transaction-level names are `ReceiptTransactionProjectCodeN` anyway."""
    from xml.etree import ElementTree as ET

    transaction = ET.fromstring(_one()).find("ReceiptHeaderLevel/ReceiptTransactionLevel")
    assert transaction is not None
    assert not [name for name in transaction.attrib if "ProjectCode" in name]
    assert not transaction.findall("ProjectCode1")


def test_the_four_card_attributes_are_present_and_empty_on_every_payment_node():
    from xml.etree import ElementTree as ET

    for payment_type in ("0", "1", "2", "3", "4"):
        node = ET.fromstring(
            _one(payment_type=payment_type, other_type="", check_number="4471")
        ).find("ReceiptHeaderLevel/ReceiptPaymentLevel")
        assert node is not None
        for name in CARD_FIELDS:
            assert node.get(name) == "", (payment_type, name)


# ── the validator, broken one fault at a time ──────────────────────────────


def _good() -> bytes:
    return FIXTURE.read_bytes()


def test_the_validator_passes_the_fixture_and_an_empty_day():
    assert newworld.validate(_good()) == []
    # PO 2026-10-07 Q3: an empty day is sent, as an empty document.
    assert newworld.validate(newworld.render([])) == []
    assert newworld.render([]).endswith(b"<ROOT />\n")


def test_the_validator_refuses_a_missing_attribute():
    bad = _good().replace(b' ReceiptNumber=""', b"", 1)
    assert any("ReceiptNumber is missing" in one for one in newworld.validate(bad))


def test_the_validator_refuses_an_attribute_not_in_the_template():
    bad = _good().replace(
        b' ReceiptTransactionARBillNumber="INV-2609-00412"',
        b' ReceiptTransactionARBillNumber="INV-2609-00412" ProjectCode1=""',
        1,
    )
    assert any("ProjectCode1 is not in the template" in one for one in newworld.validate(bad))


def test_the_validator_refuses_a_child_element_with_text():
    """The shape this file had until 2026-10-21."""
    bad = _good().replace(
        b'DistributionType="2" />',
        b'DistributionType="2"><GLAccountNumber>1200</GLAccountNumber></ReceiptTransactionGLDistributionLevel>',
        1,
    )
    problems = newworld.validate(bad)
    assert any("<GLAccountNumber> is not allowed here" in one for one in problems)
    assert any("carries text" in one for one in problems)


def test_the_validator_refuses_the_wrong_root():
    bad = _good().replace(b"<ROOT>", b"<Receipts>").replace(b"</ROOT>", b"</Receipts>")
    assert newworld.validate(bad) == ["the root is <Receipts>, not <ROOT>"]


def test_the_validator_refuses_true_or_false_as_the_voided_flag():
    for word in (b"false", b"true"):
        bad = _good().replace(b'VoidedFlag="0"', b'VoidedFlag="' + word + b'"', 1)
        assert any("VoidedFlag is" in one for one in newworld.validate(bad)), word


def test_the_validator_refuses_an_iso_date_and_a_date_that_does_not_exist():
    iso = _good().replace(b'PaymentGLDate="09/15/2026"', b'PaymentGLDate="2026-09-15"', 1)
    assert any("PaymentGLDate is '2026-09-15'" in one for one in newworld.validate(iso))
    impossible = _good().replace(b'PaymentGLDate="09/15/2026"', b'PaymentGLDate="02/30/2026"', 1)
    assert any("PaymentGLDate is '02/30/2026'" in one for one in newworld.validate(impossible))


def test_the_validator_refuses_an_empty_or_malformed_amount():
    """The template shows `""` as a placeholder; their schema types the three
    amounts `xs:double`, so a real file must carry a `9,2` number."""
    empty = _good().replace(b'ReceiptPaymentAmount="142.18"', b'ReceiptPaymentAmount=""', 1)
    assert any("ReceiptPaymentAmount is ''" in one for one in newworld.validate(empty))
    wide = _good().replace(b'DistributionAmount="142.18"', b'DistributionAmount="12345678.00"', 1)
    assert any("DistributionAmount is '12345678.00'" in one for one in newworld.validate(wide))
    three = _good().replace(b'ReceiptTransactionAmount="142.18"', b'ReceiptTransactionAmount="142.180"', 1)
    assert any("ReceiptTransactionAmount" in one for one in newworld.validate(three))


def test_the_validator_refuses_a_card_attribute_with_a_value_and_a_missing_one():
    """⚠ This file is G130's NAME_HOLDER: it plants a card value ON PURPOSE,
    in a test, to prove the last line of defence refuses it."""
    valued = _good().replace(
        b'ReceiptPaymentCreditCardNumber=""', b'ReceiptPaymentCreditCardNumber="4111111111111111"', 1
    )
    assert any(
        "ReceiptPaymentCreditCardNumber must be empty" in one for one in newworld.validate(valued)
    )
    missing = _good().replace(b' ReceiptPaymentCreditCardType=""', b"", 1)
    assert any("ReceiptPaymentCreditCardType is missing" in one for one in newworld.validate(missing))


def test_the_validator_refuses_a_payment_node_before_a_transaction_and_a_header_without_one():
    from xml.etree import ElementTree as ET

    root = ET.fromstring(_good())
    header = root.find("ReceiptHeaderLevel")
    assert header is not None
    transaction = header.find("ReceiptTransactionLevel")
    payment = header.find("ReceiptPaymentLevel")
    header.remove(transaction)
    header.remove(payment)
    header.append(payment)
    header.append(transaction)
    swapped = ET.tostring(root)
    assert any("a transaction after a payment node" in one for one in newworld.validate(swapped))
    header.remove(transaction)
    alone = ET.tostring(root)
    assert any("no ReceiptTransactionLevel" in one for one in newworld.validate(alone))


def test_the_validator_refuses_what_is_not_xml():
    assert newworld.validate(b"<ROOT>")[0].startswith("not well-formed XML")


def test_checked_raises_naming_the_problems():
    import pytest

    with pytest.raises(newworld.ReceiptFileInvalid) as raised:
        newworld.checked(_good().replace(b'VoidedFlag="0"', b'VoidedFlag="false"', 1))
    assert any("VoidedFlag" in one for one in raised.value.problems)
    assert newworld.checked(_good()) == _good()


# ── the GL resolution is the seam's, in one place ───────────────────────────


def test_the_gl_code_comes_from_the_one_seam_and_not_a_second_lookup():
    """⚠ **A GL RULE MUST CHANGE IN EXACTLY ONE PLACE.** The projection calls
    `seams/ledger.account_code` — the same resolution `/partner/v1/ledger`
    puts Aclarian's rows through. Two resolutions would be two things that can
    disagree, and the disagreement presents as a municipality's books being
    short.

    This asserts the wiring rather than a value: the module reads the seam's
    published name, and it declares no lookup of its own.
    """
    from apps.integrations.seams import ledger as ledger_seam

    assert callable(ledger_seam.account_code)
    code = _code_only(pathlib.Path(newworld.__file__))
    assert "ledger_seam.account_code(line)" in code
    # and nothing here reads the chart itself — asked of the CODE, because the
    # docstring names the thing it must not do, on purpose. See `_code_only`.
    assert "LedgerAccount" not in code
    assert "ledger_accounts" not in code


def test_the_feed_selects_the_origin_column_and_not_the_idempotency_key():
    """⚠ **`webhook_key` IS NULL ON EVERY PAYMENT RECORDED WITHOUT AN
    IDEMPOTENCY REFERENCE**, so a prefix filter would look right, pass every
    test written against seeded webhook rows, and silently omit real money.
    `payments/0029` made the origin a column for exactly this."""
    from apps.integrations.seams import payments as payments_seam

    assert payments_seam.ORIGIN_ONLINE == "webhook"
    code = _code_only(pathlib.Path(payments_seam.__file__))
    assert "query.filter(origin=origin)" in code
    # ⚠ The seam's own comment SPELLS OUT `webhook_key__startswith` to warn the
    # next reader off it. Asked of the code, not the prose — see `_code_only`.
    assert "webhook_key__startswith" not in code


def test_the_cashier_is_the_product_name_in_capitals_and_fits_their_field():
    """`CR-088` R.2 item 3 — PO 2026-10-02: *"yes"* to sending "SMART360 NEXT".

    Pinned by value, not by reference to the constant, so a rename that forgot
    the PO's ruling goes red here and not only in the fixture. Width: their
    `ReceiptCashier` is 32; this is 13.
    """
    assert newworld.RECEIPT_CASHIER == "SMART360 NEXT"
    assert len(newworld.RECEIPT_CASHIER) <= newworld.WIDTH_CASHIER
    recorded = FIXTURE.read_text(encoding="utf-8")
    assert recorded.count('ReceiptCashier="SMART360 NEXT"') == 3
    assert "SMARTBILLHUB" not in recorded


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-132-BRC07
# generated: 2026-09-22 by the CR-132-BRC07 New World lane
# gates: pytest tests/test_cr132_newworld_receipts.py
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

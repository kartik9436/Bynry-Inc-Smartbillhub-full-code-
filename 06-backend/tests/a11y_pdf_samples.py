"""Fake-data samples of every customer PDF type, for Group H (F-06).

Used by `tests/test_def_bil_f06_tagged_pdf.py` (structure markers + parity) and
by `10-scripts/a11y/verapdf_customer_pdfs.py` (veraPDF PDF/UA-1 over the same
samples). One source of samples, so the script and the suite look at the same
documents.

NO REAL CUSTOMER DATA (QA working rule, decision log 2026-10-23 Group A). Every
name, address and figure below is invented.

The bill samples are built WITHOUT a database: the mapping is assembled by the
same private builders `documents.render_invoice` calls, from an unsaved invoice
and unsaved lines, so both serialisations see exactly what a real render hands
them. `render_invoice` itself is exercised through the real issue path in the
test module.

Two utility set-ups:
  * `wdm` — West Des Moines-like: one standard layout, two services, no logo.
  * `a2`  — Ann Arbor-like: a different layout (amount-due-first), a stamped
    logo, three services (water, sewer, storm water) and a payment-plan line.
Every one of the five platform layouts is sampled with both.

Languages: `en` and `es`. ⚠ A BILL HAS NO LANGUAGE OF ITS OWN TODAY — every
label it prints is English (`documents.py`, and `agreement_pdf.py`'s *"Words
printed here are English, like every printed document in the product"*). The
`es` bill sample therefore carries Spanish CUSTOMER data (names, address, the
utility's own message) under English labels, which is what a Spanish-speaking
customer receives today. The `es` AGREEMENT is genuinely Spanish: its body is
the utility's published Spanish text and its `/Lang` is `es`.
"""

from __future__ import annotations

import datetime as dt
import io
import uuid
from decimal import Decimal
from typing import Any

LANGUAGES = ("en", "es")
UTILITIES = ("wdm", "a2")

SERVICE_IDS = {
    "water": "0199a000-0000-7000-8000-00000000a001",
    "sewer": "0199a000-0000-7000-8000-00000000a002",
    "storm": "0199a000-0000-7000-8000-00000000a003",
    "electric": "0199a000-0000-7000-8000-00000000a004",
}

PEOPLE = {
    "en": {"name": "Sarah Chen", "address": "1418 Maple Ridge Dr, Unit 2B",
           "message": "Thank you for paying on time. Your next reading is on July 15."},
    "es": {"name": "José Muñoz Peña", "address": "Calle Ñandú 12, Depto 3",
           "message": "Gracias por su pago puntual. Su próxima lectura será el 15 de julio."},
}

UTILITY = {
    "wdm": {"name": "Sample Water Works", "address": "100 Civic Center Way, Springfield, IA 50265",
            "contact": "(555) 010-0100 · billing@example.org"},
    "a2": {"name": "Sample City Utilities", "address": "301 Example Ave, Riverton, MI 48104",
           "contact": "(555) 010-0200 · utilities@example.org"},
}


def _logo() -> Any:
    """A small fake logo, decoded the way a stamped one is."""
    from PIL import Image, ImageDraw

    from apps.billing import documents

    image = Image.new("RGB", (120, 48), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle((4, 4, 44, 44), fill=(20, 90, 160))
    draw.ellipse((54, 8, 90, 44), fill=(236, 48, 19))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return documents._decode_logo("sample-logo", buffer.getvalue())


def _usage_history(services: list[tuple[str, str, str]]) -> dict[str, Any]:
    series = []
    for code, name, unit in services:
        if code == "storm":
            continue
        points = []
        for index in range(12):
            month = f"{2025 + (index + 6) // 12:04d}-{(index + 6) % 12 + 1:02d}"
            absent = index < 8
            quantity = None if absent else 3 + index
            points.append(
                {
                    "month": month,
                    "quantity": quantity,
                    "quantity_display": "" if absent else f"{quantity}",
                    "unit": None if absent else unit,
                    "absent": absent,
                    "estimated": index == 10,
                }
            )
        series.append({"service": {"code": code, "name": name}, "unit": unit, "points": points})
    return {"series": series}


def bill_inputs(utility: str, language: str) -> tuple[Any, list[Any], dict[str, Any]]:
    """`(invoice, lines, payload)` — unsaved, fake, realistic."""
    from apps.billing import models

    person = PEOPLE[language]
    who = UTILITY[utility]
    if utility == "a2":
        services = [("water", "Water", "kgal"), ("sewer", "Sewer", "kgal"),
                    ("storm", "Storm water", "ERU")]
    else:
        services = [("water", "Water", "kgal"), ("electric", "Electric", "kWh")]
    invoice_no = "BL-2609-000651" if utility == "a2" else "BL-2609-000420"
    line_specs: list[tuple[str, str, str, Decimal | None, str | None, Decimal | None, Decimal]] = []
    for code, name, unit in services:
        sid = SERVICE_IDS[code]
        line_specs.append((sid, "base", f"{name} base charge", None, None, None, Decimal("12.5000")))
        if code == "storm":
            line_specs.append((sid, "base", "Storm water, 1 ERU", Decimal("1"), "ERU",
                               Decimal("8.9375"), Decimal("8.9375")))
        else:
            line_specs.append((sid, "usage", f"{name} usage", Decimal("4.6000"), unit,
                               Decimal("6.0425"), Decimal("27.7955")))
    line_specs.append((None, "fee", "Paper bill fee", None, None, None, Decimal("1.0000")))
    line_specs.append((None, "tax", "State sales tax 6%", None, None, None, Decimal("2.1400")))
    total = sum((spec[-1] for spec in line_specs), Decimal("0"))
    previous = Decimal("45.0000")
    paid = Decimal("-45.0000")
    total_due = previous + paid + total
    payload: dict[str, Any] = {
        "account_no": "AC-2026-00057" if utility == "a2" else "AC-2026-00012",
        "customer_name": person["name"],
        "unit_label": "Unit 2B",
        "service_address": person["address"],
        "mailing_address": person["address"],
        "utility_name": who["name"],
        "utility_address": who["address"],
        "utility_contact": who["contact"],
        "bill_date": "2026-09-05",
        "cycle": "Cycle 3",
        "plan": {"id": None, "name": "Residential", "version": 3},
        "service_date": "2026-08-31",
        "currency": "USD",
        "period": {"cycle_days": 31, "service_days": 31},
        "tax_exempt": False,
        "services": [
            {"id": SERVICE_IDS[code], "code": code, "name": name, "measured": code != "storm",
             "estimated": False, "absent_reason": None if code != "storm" else "service_not_metered"}
            for code, name, unit in services
        ],
        "previous_balance": f"{previous:.6f}",
        "payments_credits": f"{paid:.6f}",
        "total_due": f"{total_due:.6f}",
        "message": person["message"],
        "ways_to_pay": "Online at the customer portal, by phone, or by mail with the stub below.",
        "usage_history": _usage_history(services),
    }
    if utility == "a2":
        payload["plan_not_yet_due"] = "20.000000"
    invoice = models.Invoice(
        id=uuid.UUID("0199a000-0000-7000-8000-0000000b0001" if utility == "a2"
                     else "0199a000-0000-7000-8000-0000000b0002"),
        invoice_no=invoice_no,
        currency="USD",
        total=total,
        due_date=dt.date(2026, 9, 25),
        period_start=dt.date(2026, 8, 1),
        period_end=dt.date(2026, 8, 31),
        payload_version=1,
        bill_payload=payload,
        status="draft",
    )
    lines = []
    for sid, kind, description, quantity, unit, unit_price, amount in line_specs:
        lines.append(
            models.InvoiceLine(
                kind=kind,
                description=description,
                quantity=quantity,
                unit=unit,
                unit_price=unit_price,
                amount=amount,
                service_id=uuid.UUID(sid) if sid else None,
                pricing_trace={},
            )
        )
    return invoice, lines, payload


def bill_document(utility: str, language: str, layout_key: str) -> tuple[dict[str, Any], Any]:
    """The mapping `render_invoice` would hand the layouts, and the spec."""
    from apps.billing import documents as d

    invoice, lines, payload = bill_inputs(utility, language)
    currency = invoice.currency
    masthead, _ = d._masthead(payload)
    meta, _ = d._meta(invoice, payload)
    services, _ = d._services(payload)
    groups, _ = d._groups(lines, currency, payload)
    summary, _ = d._summary(invoice, payload, currency)
    usage, _ = d._usage(payload)
    footer, _ = d._footer(payload)
    stub = d._stub(invoice, payload, summary)
    document = {
        "invoice_no": invoice.invoice_no,
        "template_version": 1,
        "payload_version": 1,
        "layout_source": f"platform-layout-{layout_key}",
        "masthead": masthead,
        "meta": meta,
        "services": services,
        "groups": groups,
        "summary": summary,
        "remarks": (),
        "usage": usage,
        "footer": footer,
        "stub": stub,
        "logo": _logo() if utility == "a2" else None,
    }
    return document, d.SPECS_BY_KEY[layout_key]


AGREEMENT_BODY = {
    "en": (
        "This agreement sets out the terms of your water and sewer service.\n\n"
        "1. You agree to pay each bill by its due date.\n"
        "2. A deposit of $150.00 is held and returned after twelve on-time payments.\n\n"
        "Questions? Call us at (555) 010-0200."
    ),
    "es": (
        "Este acuerdo establece las condiciones de su servicio de agua y alcantarillado.\n\n"
        "1. Usted acepta pagar cada factura antes de su fecha de vencimiento.\n"
        "2. Se retiene un depósito de $150.00 que se devuelve tras doce pagos puntuales.\n\n"
        "¿Preguntas? Llámenos al (555) 010-0200."
    ),
}


def agreement_inputs(language: str, *, stamped: bool) -> tuple[dict[str, Any], str, dict | None, str]:
    """`(facts, body, stamp, language)` for `agreement_pdf.render`."""
    person = PEOPLE[language]
    facts = {
        "utility_name": UTILITY["a2"]["name"],
        "agreement_name": "Service agreement" if language == "en" else "Acuerdo de servicio",
        "version": 3,
        "effective_from": "2026-01-01",
        "account_no": "AC-2026-00057",
        "customer_name": person["name"],
    }
    stamp = (
        {"accepted_date": "2026-09-14", "accepted_name": person["name"],
         "accepted_at": "2026-09-14 10:42 EDT"}
        if stamped
        else None
    )
    return facts, AGREEMENT_BODY[language], stamp, language


__all__ = ["LANGUAGES", "UTILITIES", "agreement_inputs", "bill_document", "bill_inputs"]

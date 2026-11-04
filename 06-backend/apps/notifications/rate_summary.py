# ── Trace ──────────────────────────────────────────────
# Change:   CR-190-BRC10 — PO 2026-10-22, decision log *"Plan-change email: 'Now'
#           and 'From' show each plan's main charges, one line each"*, verbatim:
#           *"B. Main charges, one line each — Now: Residential Standard: base
#           $12.00 a month, energy $0.0425 per kWh · From 10/31/2026:
#           Ayush_Plan: base $14.00 a month, energy $0.0390 per kWh"*.
# Defect:   DEF-NOT-10443 (the plan-change email printed `——` for both rates)
# Rules:    CLAUDE.md hard rule 2 (amounts 2dp; a UNIT PRICE up to 4dp, PO
#           2026-10-02) · hard rule 3 (a usage price names its unit) ·
#           BR-TEN-013 (rating resolved BY NAME — no rating model is imported) ·
#           B14 rule 35 (a language is written natively, not word for word)
# Tests:    06-backend/tests/test_cr190_movein_messages.py
# ───────────────────────────────────────────────────────
"""`{old_rate}` / `{new_rate}` — one plan's main charges, written as a sentence.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file decides **words a customer
reads**. Lane-authored wording, 2026-10-22; row in
12-governance/09-human-review-ledger.md.

WHAT IS DATA AND WHAT IS NOT (*"don't do any hardcoding"*)
────────────────────────────────────────────────────────────────────────────
* **Every figure, unit and name is data.** The prices and units are the plan's
  PUBLISHED rate schedule in force on the date (`rating.selectors
  .plan_charge_summary`); the plan's and service's names are the utility's own;
  the period a base charge covers is the account's CYCLE frequency
  (`metering`, through `customer_context.account_cycle`).
* **Money is written by `rendering`** — amounts at 2dp, unit prices up to 4dp,
  with the currency symbol of the utility's region (CLDR, ruled the same day).
* **The connecting words are a CATALOGUE, per language, below** — "base",
  "per", "a month", "tiered". They are the only words here, they are keyed by
  the language the message is sent in, and a language with no entry falls back
  to its primary tag and then to `en`. No price or unit is in this file.

JUDGMENTS, RECORDED IN THE DECISION LOG (2026-10-22, CR-190 MOVEIN-MSG)
────────────────────────────────────────────────────────────────────────────
* The PO's example says *"energy"* for an electric plan. No stored fact names a
  service's usage noun (energy, water, gas…), so the line uses the catalogue's
  one word for a usage charge — *usage* — rather than a per-service word typed
  here. A plan with several services prefixes each line with the service's own
  name, so the reader still knows which charge is which.
* A tiered, seasonal or time-of-day charge reads *"usage from $0.0390 per kWh,
  tiered"* — its LOWEST unit price plus the structure word (PO-ruled shape).
* A base the rate schedule cannot state for this account (no base code, a
  per-size code without a size, a conflict) is LEFT OUT — the line states the
  usage alone — rather than guessed. A service with neither is not listed.
* No cycle frequency → the base reads without its period (*"base $12.00"*).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.notifications import customers_seam, rendering, tenancy_seam

RATING_MODULE = "rating"
SUMMARY_READ = "plan_charge_summary"

#: language → phrase key → text. Placeholders are filled from data only.
WORDING: dict[str, dict[str, Any]] = {
    "en": {
        "base": "base {amount} {period}",
        "base_only": "base {amount}",
        "usage": "usage {price} per {unit}",
        "usage_no_unit": "usage {price}",
        "usage_from": "usage from {price} per {unit}, {structure}",
        "usage_from_no_unit": "usage from {price}, {structure}",
        "join": ", ",
        "line": "{plan}: {parts}",
        "line_service": "{plan} · {service}: {parts}",
        "structure": {"tiered": "tiered", "time_of_day": "time of day", "seasonal": "seasonal"},
        "period": {
            "Daily": "a day",
            "Weekly": "a week",
            "Fortnightly": "every two weeks",
            "Monthly": "a month",
            "Bimonthly": "every two months",
            "Quarterly": "a quarter",
            "Semiannual": "every six months",
            "Annual": "a year",
        },
    },
    "es": {
        "base": "cargo fijo {amount} {period}",
        "base_only": "cargo fijo {amount}",
        "usage": "consumo {price} por {unit}",
        "usage_no_unit": "consumo {price}",
        "usage_from": "consumo desde {price} por {unit}, {structure}",
        "usage_from_no_unit": "consumo desde {price}, {structure}",
        "join": ", ",
        "line": "{plan}: {parts}",
        "line_service": "{plan} · {service}: {parts}",
        "structure": {
            "tiered": "por tramos",
            "time_of_day": "según la hora",
            "seasonal": "según la temporada",
        },
        "period": {
            "Daily": "al día",
            "Weekly": "a la semana",
            "Fortnightly": "cada dos semanas",
            "Monthly": "al mes",
            "Bimonthly": "cada dos meses",
            "Quarterly": "al trimestre",
            "Semiannual": "cada seis meses",
            "Annual": "al año",
        },
    },
    "de": {
        "base": "Grundpreis {amount} {period}",
        "base_only": "Grundpreis {amount}",
        "usage": "Verbrauch {price} pro {unit}",
        "usage_no_unit": "Verbrauch {price}",
        "usage_from": "Verbrauch ab {price} pro {unit}, {structure}",
        "usage_from_no_unit": "Verbrauch ab {price}, {structure}",
        "join": ", ",
        "line": "{plan}: {parts}",
        "line_service": "{plan} · {service}: {parts}",
        "structure": {
            "tiered": "gestaffelt",
            "time_of_day": "nach Tageszeit",
            "seasonal": "nach Jahreszeit",
        },
        "period": {
            "Daily": "pro Tag",
            "Weekly": "pro Woche",
            "Fortnightly": "alle zwei Wochen",
            "Monthly": "pro Monat",
            "Bimonthly": "alle zwei Monate",
            "Quarterly": "pro Quartal",
            "Semiannual": "pro Halbjahr",
            "Annual": "pro Jahr",
        },
    },
    "fr": {
        "base": "abonnement {amount} {period}",
        "base_only": "abonnement {amount}",
        "usage": "consommation {price} par {unit}",
        "usage_no_unit": "consommation {price}",
        "usage_from": "consommation à partir de {price} par {unit}, {structure}",
        "usage_from_no_unit": "consommation à partir de {price}, {structure}",
        "join": ", ",
        "line": "{plan} : {parts}",
        "line_service": "{plan} · {service} : {parts}",
        "structure": {
            "tiered": "par tranches",
            "time_of_day": "selon l'heure",
            "seasonal": "selon la saison",
        },
        "period": {
            "Daily": "par jour",
            "Weekly": "par semaine",
            "Fortnightly": "toutes les deux semaines",
            "Monthly": "par mois",
            "Bimonthly": "tous les deux mois",
            "Quarterly": "par trimestre",
            "Semiannual": "par semestre",
            "Annual": "par an",
        },
    },
    "it": {
        "base": "quota fissa {amount} {period}",
        "base_only": "quota fissa {amount}",
        "usage": "consumi {price} per {unit}",
        "usage_no_unit": "consumi {price}",
        "usage_from": "consumi da {price} per {unit}, {structure}",
        "usage_from_no_unit": "consumi da {price}, {structure}",
        "join": ", ",
        "line": "{plan}: {parts}",
        "line_service": "{plan} · {service}: {parts}",
        "structure": {
            "tiered": "a scaglioni",
            "time_of_day": "a fasce orarie",
            "seasonal": "stagionale",
        },
        "period": {
            "Daily": "al giorno",
            "Weekly": "a settimana",
            "Fortnightly": "ogni due settimane",
            "Monthly": "al mese",
            "Bimonthly": "ogni due mesi",
            "Quarterly": "a trimestre",
            "Semiannual": "a semestre",
            "Annual": "all'anno",
        },
    },
    "pt": {
        "base": "tarifa fixa {amount} {period}",
        "base_only": "tarifa fixa {amount}",
        "usage": "consumo {price} por {unit}",
        "usage_no_unit": "consumo {price}",
        "usage_from": "consumo a partir de {price} por {unit}, {structure}",
        "usage_from_no_unit": "consumo a partir de {price}, {structure}",
        "join": ", ",
        "line": "{plan}: {parts}",
        "line_service": "{plan} · {service}: {parts}",
        "structure": {
            "tiered": "por faixas",
            "time_of_day": "por horário",
            "seasonal": "por estação",
        },
        "period": {
            "Daily": "por dia",
            "Weekly": "por semana",
            "Fortnightly": "a cada duas semanas",
            "Monthly": "por mês",
            "Bimonthly": "a cada dois meses",
            "Quarterly": "por trimestre",
            "Semiannual": "por semestre",
            "Annual": "por ano",
        },
    },
    "id": {
        "base": "biaya tetap {amount} {period}",
        "base_only": "biaya tetap {amount}",
        "usage": "pemakaian {price} per {unit}",
        "usage_no_unit": "pemakaian {price}",
        "usage_from": "pemakaian mulai {price} per {unit}, {structure}",
        "usage_from_no_unit": "pemakaian mulai {price}, {structure}",
        "join": ", ",
        "line": "{plan}: {parts}",
        "line_service": "{plan} · {service}: {parts}",
        "structure": {
            "tiered": "berjenjang",
            "time_of_day": "menurut waktu pemakaian",
            "seasonal": "menurut musim",
        },
        "period": {
            "Daily": "per hari",
            "Weekly": "per minggu",
            "Fortnightly": "setiap dua minggu",
            "Monthly": "per bulan",
            "Bimonthly": "setiap dua bulan",
            "Quarterly": "per tiga bulan",
            "Semiannual": "per enam bulan",
            "Annual": "per tahun",
        },
    },
    "hi": {
        "base": "स्थायी शुल्क {amount} {period}",
        "base_only": "स्थायी शुल्क {amount}",
        "usage": "खपत शुल्क {price} प्रति {unit}",
        "usage_no_unit": "खपत शुल्क {price}",
        "usage_from": "खपत शुल्क {price} प्रति {unit} से शुरू, {structure}",
        "usage_from_no_unit": "खपत शुल्क {price} से शुरू, {structure}",
        "join": ", ",
        "line": "{plan}: {parts}",
        "line_service": "{plan} · {service}: {parts}",
        "structure": {
            "tiered": "स्लैब के अनुसार",
            "time_of_day": "समय के अनुसार",
            "seasonal": "मौसम के अनुसार",
        },
        "period": {
            "Daily": "प्रति दिन",
            "Weekly": "प्रति सप्ताह",
            "Fortnightly": "हर दो सप्ताह",
            "Monthly": "प्रति माह",
            "Bimonthly": "हर दो महीने",
            "Quarterly": "प्रति तिमाही",
            "Semiannual": "हर छह महीने",
            "Annual": "प्रति वर्ष",
        },
    },
    "ja": {
        "base": "基本料金 {amount}（{period}）",
        "base_only": "基本料金 {amount}",
        "usage": "従量料金 {unit}あたり{price}",
        "usage_no_unit": "従量料金 {price}",
        "usage_from": "従量料金 {unit}あたり{price}から（{structure}）",
        "usage_from_no_unit": "従量料金 {price}から（{structure}）",
        "join": "、",
        "line": "{plan}：{parts}",
        "line_service": "{plan}・{service}：{parts}",
        "structure": {"tiered": "段階制", "time_of_day": "時間帯別", "seasonal": "季節別"},
        "period": {
            "Daily": "1日あたり",
            "Weekly": "1週間あたり",
            "Fortnightly": "2週間ごと",
            "Monthly": "月額",
            "Bimonthly": "2か月ごと",
            "Quarterly": "3か月ごと",
            "Semiannual": "6か月ごと",
            "Annual": "年額",
        },
    },
    "ko": {
        "base": "기본요금 {amount}({period})",
        "base_only": "기본요금 {amount}",
        "usage": "사용요금 {unit}당 {price}",
        "usage_no_unit": "사용요금 {price}",
        "usage_from": "사용요금 {unit}당 {price}부터({structure})",
        "usage_from_no_unit": "사용요금 {price}부터({structure})",
        "join": ", ",
        "line": "{plan}: {parts}",
        "line_service": "{plan} · {service}: {parts}",
        "structure": {"tiered": "누진제", "time_of_day": "시간대별", "seasonal": "계절별"},
        "period": {
            "Daily": "1일 기준",
            "Weekly": "1주 기준",
            "Fortnightly": "2주마다",
            "Monthly": "월",
            "Bimonthly": "2개월마다",
            "Quarterly": "분기마다",
            "Semiannual": "6개월마다",
            "Annual": "연",
        },
    },
}


def wording_for(language: str | None) -> dict[str, Any]:
    """Exact tag, then its primary language, then `en`."""
    tag = (language or "").strip()
    if tag in WORDING:
        return WORDING[tag]
    primary = tag.replace("_", "-").split("-")[0].lower()
    return WORDING.get(primary) or WORDING["en"]


def _summary(plan_id: Any, on_date: date, customer_class: str | None) -> dict[str, Any] | None:
    read = customers_seam._resolve(RATING_MODULE, SUMMARY_READ)
    if read is None or plan_id in (None, ""):  # pragma: no cover - rating publishes it
        return None
    return read(plan_id, on_date=on_date, customer_class=customer_class)


def compose(
    summary: dict[str, Any] | None,
    *,
    language: str | None,
    frequency: str | None,
) -> str | None:
    """One line per service, joined by newlines — or None when nothing is known."""
    if not summary or not summary.get("services"):
        return None
    words = wording_for(language)
    formats, _problems = tenancy_seam.regional_formats()
    locale = rendering.money_locale(
        language if language and language != "default" else formats.get("language"),
        formats.get("country"),
    )
    number_format = formats.get("number_format")
    period = (words["period"].get(frequency) if frequency else None) or None
    services = summary["services"]
    lines: list[str] = []
    for service in services:
        currency = service.get("currency") or formats.get("currency")
        parts: list[str] = []
        base = service.get("base_amount")
        if base is not None:
            amount = rendering.format_money(
                base, currency, locale=locale, number_format=number_format
            )
            parts.append(
                words["base"].format(amount=amount, period=period)
                if period
                else words["base_only"].format(amount=amount)
            )
        usage = service.get("usage")
        if usage and usage.get("unit_price") is not None:
            price = rendering.format_unit_price(
                usage["unit_price"], currency, locale=locale, number_format=number_format
            )
            unit = usage.get("unit") or None
            structure = words["structure"].get(usage.get("structure") or "")
            if structure:
                key = "usage_from" if unit else "usage_from_no_unit"
                parts.append(words[key].format(price=price, unit=unit, structure=structure))
            else:
                key = "usage" if unit else "usage_no_unit"
                parts.append(words[key].format(price=price, unit=unit))
        if not parts:
            continue
        template = words["line_service"] if len(services) > 1 else words["line"]
        lines.append(
            template.format(
                plan=summary.get("plan_name") or "",
                service=service.get("service_name") or "",
                parts=words["join"].join(parts),
            )
        )
    return "\n".join(lines) or None


def rate_line(
    plan_id: Any,
    *,
    on_date: date,
    language: str | None = None,
    customer_class: str | None = None,
    frequency: str | None = None,
) -> str | None:
    """`{old_rate}` / `{new_rate}` for one plan on one date. None when unknown."""
    return compose(
        _summary(plan_id, on_date, customer_class), language=language, frequency=frequency
    )

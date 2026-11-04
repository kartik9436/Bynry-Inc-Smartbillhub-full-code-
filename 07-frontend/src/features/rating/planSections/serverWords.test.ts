// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-RAT-9502 — the plan screens printed the words the SERVER
//          composes (usage headings and rows, base heading, When, What is
//          taxed, Everyone, the Audit Change column) in English, in every
//          language. CR-167-BRC10 task 9.
// ───────────────────────────────────────────────────────
//
// Each helper is read through a GERMAN translator, so a helper that hands
// the server's English straight through fails here: the server's words are
// English in every language, and only the catalogue can make them German.
import { describe, expect, it } from "vitest";

import type { PlanChargeSection, PlanServiceSection, PlanTaxSection, PlanUsageRow } from "@/api/planFormEndpoints";
import type { PlanAuditRow } from "@/api/planDetailEndpoints";
import i18n from "@/i18n";

import { auditChange } from "../planDetail/PlanAuditTab";
import type { Translator } from "../ratingShared";
import { classOrSizeWord, sizedByWord, taxedWord, usageKindWord, usageRowLabel, usageRowRate, whenWord } from "./PlanSections";

const de: Translator = (key, params) => i18n.getFixedT("de")(key, params);

function section(service: string, kind: string, kindLabel: string | null, sizedBy: string | null): PlanServiceSection {
  return {
    service,
    name: service,
    gl: null,
    schedule: null,
    base: { sized_by_label: sizedBy } as PlanServiceSection["base"],
    minimum: { by_size: [], flat_display: null },
    usage: { kind, kind_label: kindLabel, rows: [] },
    outside_city: { surcharged: false, percent_display: null },
  };
}

const row = (extra: Partial<PlanUsageRow>): PlanUsageRow => ({ label: "Over 500 kWh", rate_display: "$0.14 per kWh", ...extra });

describe("the server's plan words, in the catalogue's language (DEF-RAT-9502)", () => {
  it("words the usage heading and the base heading from their codes", () => {
    expect(usageKindWord(section("electric", "blocks", "Block (per month)", "meter size"), de)).toBe("Stufen (je Monat)");
    expect(usageKindWord(section("trash", "per_size", "Per cart, per month", "cart size"), de)).toBe("Je Tonne, je Monat");
    expect(sizedByWord(section("water", "blocks", "Block (per month)", "meter size"), de)).toBe("Zählergröße");
    expect(sizedByWord(section("fire", "per_size", "Per line, per month", "fire line size"), de)).toBe("Größe der Löschwasserleitung");
  });

  it("words a usage row and its rate, and keeps a row that is the utility's data", () => {
    expect(usageRowLabel(row({ label_key: "over", label_args: { qty: "500 kWh" } }), de)).toBe("Über 500 kWh");
    expect(usageRowLabel(row({ label: "Each month", label_key: "eachMonth" }), de)).toBe("Jeden Monat");
    expect(usageRowLabel(row({ label: "Share of water", label_key: "share", label_args: { service: "water" } }), de)).toBe(
      `Anteil an ${de("rating.service.water")}`,
    );
    expect(usageRowLabel(row({ label: "Water 5/8\"", label_key: null }), de)).toBe("Water 5/8\"");
    expect(usageRowRate(row({ rate_amount: "$0.14", rate_unit: "kWh" }), de)).toBe("$0.14 je kWh");
  });

  it("words When, What is taxed and an older server's row without codes", () => {
    const charge = { type_label: "penalty", when_label: "After the due date" } as PlanChargeSection;
    expect(whenWord(charge, de)).toBe("Nach Fälligkeit");
    const tax = { what_is_taxed: ["usage", "base"], what_is_taxed_label: "Usage and base charges" } as unknown as PlanTaxSection;
    expect(taxedWord(tax, de)).toBe("Verbrauchs- und Grundentgelte");
    const everyone = { class_or_size_label: "Everyone", everyone: true, amount_display: "75.00", percent_display: null, min_display: null };
    expect(classOrSizeWord(everyone, de)).toBe(de("rating.planSections.everyone"));
    expect(classOrSizeWord({ ...everyone, class_or_size_label: "Residential", everyone: false }, de)).toBe("Residential");
    // No codes from the server: its English is drawn as before, never a raw key.
    expect(usageRowLabel(row({}), de)).toBe("Over 500 kWh");
  });

  it("words the Audit change from its facts: field, yes/no and status", () => {
    const audit: PlanAuditRow = {
      id: "r1",
      at: null,
      actor_name: null,
      what_kind: "plan",
      what_name: null,
      change: "published",
      reason: null,
      before_display: "Status: draft",
      after_display: "Budget billing: Yes · Status: published",
      before_facts: [{ key: "status", label: "Status", kind: "status", raw: "draft", value: "draft" }],
      after_facts: [
        { key: "budget_billing", label: "Budget billing", kind: "bool", raw: true, value: "Yes" },
        { key: "discounts", label: "Discounts", kind: "none", raw: null, value: "None" },
        { key: "status", label: "Status", kind: "status", raw: "published", value: "published" },
      ],
      facts_more: 0,
      version: null,
    };
    expect(auditChange(audit, de)).toBe(
      `${de("rating.plans.col.status")}: Entwurf → Abschlagszahlung: Ja · Rabatte: Keine · ${de("rating.plans.col.status")}: Veröffentlicht`,
    );
  });
});

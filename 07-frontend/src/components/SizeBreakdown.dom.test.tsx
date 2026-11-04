// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Ruling:   PO 2026-10-01 — "CAPACITY SERVICES: THE BASE IS LOOKED UP BY SIZE
//           ON EVERY BILL" and "GO: THE NINE CHANGES", items 7 and 8.
// Rules:    B14 rules 21, 33, 35, 43
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import en from "@/i18n/locales/en.json";

import { SizeBreakdown } from "./SizeBreakdown";

const catalogue = en as Record<string, string>;
const t = (key: string, params?: Record<string, unknown>) =>
  (catalogue[key] ?? key).replace(/\{\{(\w+)\}\}/g, (_m, name: string) => String(params?.[name] ?? ""));
const usd = (amount: string) => `$${Number(amount).toFixed(2)}`;

describe("SizeBreakdown", () => {
  it("prints size × count · base · price each — the worked trash line", () => {
    const html = renderToStaticMarkup(
      <SizeBreakdown
        rows={[
          {
            size: "CART-96",
            size_label: "Trash 96-gallon cart",
            count: 2,
            base_each: "3.0000",
            price_each: "15.0000",
            base_priced: true,
          },
        ]}
        formatAmount={usd}
        t={t}
      />,
    );
    expect(html).toContain("Trash 96-gallon cart × 2 · base $3.00 · $15.00 each");
    expect(html).toContain('data-size="CART-96"');
  });

  it("names a size with no base price instead of printing a zero as if priced", () => {
    const html = renderToStaticMarkup(
      <SizeBreakdown
        rows={[
          { size: "CART-35", size_label: "Trash 35-gallon cart", count: 1, base_each: "0.0000", price_each: "15.0000", base_priced: false },
          { size: "CART-64", size_label: "Trash 64-gallon cart", count: 1, base_each: "0.0000", base_priced: false },
        ]}
        formatAmount={usd}
        t={t}
      />,
    );
    expect(html).toContain("Trash 35-gallon cart × 1 · no base price · $15.00 each");
    expect(html).toContain("Trash 64-gallon cart × 1 · no base price");
  });

  it("prints solar's per-size base with no per-size price (usage is on the total)", () => {
    const html = renderToStaticMarkup(
      <SizeBreakdown
        rows={[
          { size: "SOL-P2", size_label: "Solar panel 2 kW", count: 2, base_each: "2.0000", price_each: null },
          { size: "SOL-P4", size_label: "Solar panel 4 kW", count: 1, base_each: "3.0000", price_each: null },
        ]}
        formatAmount={usd}
        t={t}
      />,
    );
    expect(html).toContain("Solar panel 2 kW × 2 · base $2.00");
    expect(html).toContain("Solar panel 4 kW × 1 · base $3.00");
  });

  it("renders nothing for a metered line's one base, which has no count", () => {
    const html = renderToStaticMarkup(
      <SizeBreakdown rows={[{ size: "W-58", count: null, base_each: "8.0000" }]} formatAmount={usd} t={t} />,
    );
    expect(html).toBe("");
  });
});

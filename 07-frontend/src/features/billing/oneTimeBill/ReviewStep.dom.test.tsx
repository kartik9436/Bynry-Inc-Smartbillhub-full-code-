// @vitest-environment jsdom
/**
 * The review table's rows as the drawing and the stories print them —
 * DEF-BIL-8312 (a fee names its code, US-BIL-032 TC-3) and DEF-BIL-8315
 * (a counted service reads `Per cart` / `Base · per cart`, a base line
 * prints `1` at its rate, the header names the bill).
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, within } from "@testing-library/react";
import i18n from "i18next";
import { afterEach, describe, expect, it } from "vitest";

import type { OneTimeBillDocument } from "@/api/billingOpsEndpoints";

import { BillPreview } from "./ReviewStep";
import type { OtbFormat } from "./oneTimeBillShared";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;
const fmt: OtbFormat = { t, currency: "USD", timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" };

function bill(lines: OneTimeBillDocument["groups"][number]["lines"], label = "period"): OneTimeBillDocument {
  return {
    groups: [{ label, period_start: null, period_end: null, subtotal: "0.0000", lines }],
    subtotal: "0.0000",
    tax: [],
    total: "0.0000",
    currency: "USD",
  };
}

function rows(document: OneTimeBillDocument, kind: "fee" | "interim" = "interim") {
  render(
    <BillPreview
      kind={kind}
      bill={document}
      customer="Maria Alvarez"
      accountLine="AC-2026-00042"
      billDate="2026-09-30"
      dueDate="2026-10-21"
      period={null}
      warnings={[]}
      t={t}
      fmt={fmt}
    />,
  );
  return Array.from(document.groups[0].lines.keys()).map(
    (i) => (screen.getAllByRole("row").filter((r) => r.hasAttribute("data-bill-line"))[i] as HTMLElement).textContent,
  );
}

describe("the review table's rows", () => {
  it("DEF-BIL-8312 — a fee line reads Fee · RECON · 1 · $75.00 (US-BIL-032 TC-3)", () => {
    const [line] = rows(
      bill(
        [{ service: "Reconnection fee", asset_label: null, charge: "fee", code: "RECON", quantity: "1", unit: null, rate: "75.0000", amount: "75.0000", flags: [] }],
        "charges",
      ),
      "fee",
    );
    expect(line).toContain("Reconnection fee");
    expect(line).toContain("Fee · RECON");
    expect(line).toContain("$75.00$75.00");
  });

  it("DEF-BIL-8315 — trash reads Per cart and Base · per cart; a base prints 1 at its rate", () => {
    const [perCart, base] = rows(
      bill([
        { service: "trash", asset_label: null, charge: "per_asset", per_unit: "cart", quantity: "1", unit: "cart", rate: "15.00", amount: "15.0000", flags: [] },
        { service: "trash", asset_label: null, charge: "base", per_unit: "cart", quantity: "1", unit: null, rate: "3.0000", amount: "3.0000", flags: [] },
      ]),
    );
    expect(perCart).toContain("1 cart");
    expect(perCart).toContain("Per cart");
    expect(perCart).toContain("$15.00");
    expect(base).toContain("Base · per cart");
    expect(base).toContain("1$3.00$3.00");
  });

  it("DEF-BIL-8315 — the header names the bill: Interim bill · draft", () => {
    rows(bill([]));
    expect(within(document.body).getByText("Interim bill · draft")).toBeInTheDocument();
  });

  it("DEF-BIL-8744 — a prorated per-kW line reads 6 kW · $14.00 · 19/30 days · $53.20", () => {
    const [prorated, whole] = rows(
      bill([
        { service: "solar", asset_label: null, charge: "usage", quantity: "6", unit: "kW", rate: "14.000000", amount: "53.2000", flags: [], day_share: { days: 19, of: 30 } },
        { service: "battery", asset_label: null, charge: "usage", quantity: "5", unit: "kW", rate: "3.000000", amount: "15.0000", flags: [], day_share: null },
      ]),
    );
    expect(prorated).toContain("6 kW$14.0019/30 days$53.20");
    expect(whole).toContain("5 kW$3.00$15.00");
    expect(whole).not.toContain("days");
  });
});

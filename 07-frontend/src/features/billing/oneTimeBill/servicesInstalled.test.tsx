// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-BIL-10221 — found by the DEF-RAT-10220 walk (2026-10-17): the
//          bill line read 57.84 kW × $14.00 = $809.76 while the Services row
//          read "2 KW · PV-00001, PV-00002" and "Billed · 2 KW".
// ───────────────────────────────────────────────────────
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { OneTimeBillServiceRow } from "@/api/billingOpsEndpoints";
import i18n from "@/i18n";

import { ServicesTable } from "./ServicesStep";

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params);
const fmt = { t, currency: "USD", timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" } as const;

const solar: OneTimeBillServiceRow = {
  service: "solar",
  assets: [
    { asset_id: "a", label: "PV-00001" },
    { asset_id: "b", label: "PV-00002" },
  ],
  asset_kind: "count",
  count_unit: null,
  installed: { quantity: "57.84", unit: "kW" },
  status: "billed",
  basis_service: null,
  count: 2,
  on_bill: "per_asset_lines",
};
const trash: OneTimeBillServiceRow = {
  ...solar,
  service: "trash",
  assets: [{ asset_id: "c", label: "CART-1" }],
  count_unit: "cart",
  installed: null,
  count: 1,
  on_bill: "usage_and_base",
};

describe("DEF-BIL-10221 — a summed capacity reads its installed total", () => {
  it("solar says 57.84 kW and never 2 KW; trash still counts carts", () => {
    const html = renderToStaticMarkup(
      <ServicesTable services={[solar, trash]} warnings={[]} t={t} fmt={fmt as never} />,
    );
    expect(html).toContain("Billed · 57.84 kW");
    expect(html).toContain("2 assets · PV-00001, PV-00002");
    expect(html).not.toContain("2 KW");
    expect(html).toContain("1 cart · CART-1");
  });
});

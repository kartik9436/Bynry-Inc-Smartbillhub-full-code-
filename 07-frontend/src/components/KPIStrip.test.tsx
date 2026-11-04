// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-013 (EP-SHL-05 §Stories — display kit)  Screens: S7, S36 (KPI strips)
// Rules:    BR-REP-001 (basis label on every money KPI) · BR-SHL-012 (shared loading state)
// ───────────────────────────────────────────────────────
// TC tests for FE-09 KPIStrip: tiles, the BR-REP-001 basis-label law
// (type-enforced), and the shared KPI skeleton.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n"; // initializes the i18next singleton with the five catalogs

import { KPIStrip } from "./KPIStrip";
import type { KpiTile } from "./KPIStrip";

// S7-shaped tiles from the A14 basis table: AR outstanding reads the POSTING
// date, cash today reads the CLEARING date, unbilled reads is a plain count.
const s7Kpis: readonly KpiTile[] = [
  {
    id: "ar",
    label: "AR outstanding",
    money: { amount: "184320.00", currency: "USD", basis: "posting" },
    detail: "↑ 4.2% MoM",
  },
  {
    id: "cash",
    label: "Cash today",
    money: { amount: "4212.09", currency: "USD", basis: "clearing" },
  },
  { id: "unbilled", label: "Unbilled reads", value: "1,247", detail: "312 pending routes" },
];

describe("US-SHL-013 — KPIStrip (FE-09): KPI tiles with BR-REP-001 basis labels", () => {
  it("BR-REP-001: every money KPI header labels its date basis; money renders through the ONE MoneyCell", () => {
    const html = renderToStaticMarkup(<KPIStrip kpis={s7Kpis} />);
    expect(html).toContain("AR outstanding");
    expect(html).toContain("Posting date"); // billing-side KPI → posting
    expect(html).toContain("Cash today");
    expect(html).toContain("Clearing date"); // cash-side KPI → clearing
    expect(html).toContain("$184,320.00"); // MoneyCell 2dp display
    expect(html).toContain("$4,212.09");
    expect((html.match(/class="kpi"/g) ?? []).length).toBe(3);
    expect((html.match(/kpi-basis/g) ?? []).length).toBe(2); // only money tiles carry one
  });

  it("BR-REP-001 (by construction): a money KPI cannot be declared without a basis", () => {
    // @ts-expect-error — BR-REP-001: basis is REQUIRED on money KPIs; omitting it is a type error
    const tile: KpiTile = { id: "bad", label: "AR", money: { amount: "1.00", currency: "USD" } };
    expect(tile).toBeDefined(); // the assertion above is the compile-time gate
  });

  it("non-money KPIs render value + detail with no basis label", () => {
    const html = renderToStaticMarkup(<KPIStrip kpis={[s7Kpis[2]]} />);
    expect(html).toContain("Unbilled reads");
    expect(html).toContain("1,247");
    expect(html).toContain("312 pending routes");
    expect(html).not.toContain("kpi-basis");
  });

  it("BR-SHL-012 / A18 §3: loading composes the shared KPI skeleton — never a bare spinner, no stale tiles behind it", () => {
    const html = renderToStaticMarkup(<KPIStrip kpis={s7Kpis} loading />);
    expect(html).toContain("skeleton-kpi");
    expect(html).not.toContain("spinner");
    expect(html).not.toContain("AR outstanding");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-013@1e89ecb (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope)
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// DEF-MET-10164 — the shared Age cell renders what a reader sees.
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";
import { describe, expect, it } from "vitest";

import i18n from "@/i18n";
import { AgeCell } from "@/components/AgeCell";
import { TenantRegionalProvider } from "@/components/TenantRegional";

function html(node: JSX.Element): string {
  return renderToStaticMarkup(<I18nextProvider i18n={i18n}>{node}</I18nextProvider>);
}

describe("AgeCell", () => {
  it("renders the age between start and a fixed end", () => {
    const out = html(<AgeCell start="1996-03-14" end="2026-10-17" timeZone="America/Chicago" />);
    expect(out).toContain("30 yrs 7 mos");
  });

  it("reads the published tenant zone when no prop is passed", () => {
    // 03:00 UTC on 15 Oct is 14 Oct in Chicago → 3 days to 17 Oct, not 2.
    const out = html(
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <AgeCell start="2026-10-15T03:00:00+00:00" end="2026-10-17" />
      </TenantRegionalProvider>,
    );
    expect(out).toContain("3 days");
  });

  it("a missing start is a quiet dash, never 0 days", () => {
    const out = html(<AgeCell start={null} timeZone="UTC" />);
    expect(out).toContain("—");
    expect(out).not.toContain("days");
  });

  it("note renders as a second line; danger tone accents both", () => {
    const out = html(
      <AgeCell start="2001-06-01" end="2026-10-17" timeZone="UTC" note="Past life" tone="danger" />,
    );
    expect(out).toContain("25 yrs 4 mos");
    expect(out).toContain("Past life");
    expect(out.match(/text-danger-700/g)?.length).toBe(2);
  });
});

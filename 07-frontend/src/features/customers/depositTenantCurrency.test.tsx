// DEF-CUS-5114 — a screen with no account in scope reads the TENANT's currency.
//
// BR-TEN-042: one tenant, one currency. New account has no account until its
// commit, and a move-in into a VACANT unit has no outgoing account to read a
// currency off, so both deposit footers and both review blocks read
// "Currency not known here" where they should read "$600.00". The shell already
// reads the tenant's `CHAR(3)` on `GET /shell/display`; it now publishes it on
// `TenantRegionalProvider`, and `useTenantCurrency()` is the ONE reader.
//
// What must STILL hold: with nothing published, the sentence — never a
// defaulted `USD` (hard rule 2, `DEF-1121`).
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { withTenantCurrency } from "@/components/ShellWithSession";
import { TenantRegionalProvider, useTenantCurrency } from "@/components/TenantRegional";

import SHELL_SOURCE from "@/components/ShellWithSession.tsx?raw";

import {
  DepositReviewRows,
  DepositTodayTotals,
  emptyDepositForm,
  type DepositForm,
} from "./depositCapability";

const t = (key: string) => key;

/** The re-walk's figure: a 2" size picked, $600.00 taken today. */
function sixHundred(): DepositForm {
  return {
    ...emptyDepositForm(),
    decision: "required",
    amount: "600.0000",
    take_now: true,
    method_code: "card",
    amount_taken: "",
    posted_at: "2026-10-04",
  };
}

function underTenant(currency: string | null | undefined, node: React.ReactNode): string {
  return renderToStaticMarkup(
    <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY", currency }}>
      {node}
    </TenantRegionalProvider>,
  );
}

function review(form: DepositForm, currency: string | null) {
  return (
    <dl>
      <DepositReviewRows
        form={form}
        currency={currency}
        t={t}
        row={(label, value) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        )}
      />
    </dl>
  );
}

describe("DEF-CUS-5114: the tenant's currency reaches a screen with no account", () => {
  it("useTenantCurrency reads what the shell published, and null when nothing did", () => {
    function Probe() {
      return <span>{useTenantCurrency() ?? "none"}</span>;
    }
    expect(underTenant("USD", <Probe />)).toContain("USD");
    expect(underTenant(undefined, <Probe />)).toContain("none");
    expect(renderToStaticMarkup(<Probe />)).toContain("none");
  });

  it("New account / vacant move-in: the deposit footer reads $600.00, not the absence", () => {
    const html = underTenant("USD", <DepositTodayTotals form={sixHundred()} currency={null} t={t} />);
    expect(html).toContain("$600.00");
    expect(html).not.toContain("customers.deposit.totals.currencyAbsent");
    // Hard rule 2: stored to 4, DISPLAYED to 2.
    expect(html).not.toContain("600.0000");
  });

  it("the review block reads $600.00 off the tenant too", () => {
    const html = underTenant("USD", review(sixHundred(), null));
    expect(html).toContain("$600.00");
    expect(html).not.toContain("customers.deposit.totals.currencyAbsent");
  });

  it("an account in scope still wins — its own currency is the one shown", () => {
    const html = underTenant("USD", <DepositTodayTotals form={sixHundred()} currency="CAD" t={t} />);
    expect(html).toContain("CA$600.00");
  });

  it("nothing published is still a sentence, never a defaulted USD", () => {
    const html = underTenant(null, <DepositTodayTotals form={sixHundred()} currency={null} t={t} />);
    expect(html).toContain("customers.deposit.totals.currencyAbsent");
    expect(html).not.toContain("$");
    const bare = renderToStaticMarkup(review(sixHundred(), null));
    expect(bare).toContain("customers.deposit.totals.currencyAbsent");
  });
});

describe("DEF-CUS-5114: the shell publishes the currency it already reads", () => {
  const zone = { timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" as const };

  it("carries GET /shell/display's currency beside the zone and the format", () => {
    expect(withTenantCurrency(zone, { currency: "USD" })).toEqual({ ...zone, currency: "USD" });
  });

  it("an unset currency publishes null — the shell never defaults USD", () => {
    expect(withTenantCurrency(zone, { currency: null })?.currency).toBeNull();
    expect(withTenantCurrency(zone, { currency: "" })?.currency).toBeNull();
    expect(withTenantCurrency(zone, undefined)?.currency).toBeNull();
  });

  it("no regional settings yet is still `null` — the shell's own wait is untouched", () => {
    expect(withTenantCurrency(null, { currency: "USD" })).toBeNull();
  });

  it("the value the provider receives is the one built by withTenantCurrency", () => {
    // The provider's ONE call site, and the line that builds its value.
    expect(SHELL_SOURCE).toContain("<TenantRegionalProvider value={effectiveRegional}>");
    expect(SHELL_SOURCE).toMatch(
      /const effectiveRegional: TenantRegional \| null = withTenantCurrency\(/,
    );
  });
});

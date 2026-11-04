// ── Trace ──────────────────────────────────────────────
// Story:    US-CUS-019 (the BR-CUS-054 customer entity) — CR-060 **C16** / T17
// Rules:    BR-CUS-054 as AMENDED by CR-060 C16 · BR-CUS-089 · DEF-127 (an
//           absence is never spelled like a zero) · B14 rules 31 and 32
// ───────────────────────────────────────────────────────
/**
 * The customer statement, **asserted as RENDERED MARKUP**.
 *
 * ⚠ **THAT IS THE WHOLE POINT OF THIS FILE AND IT IS NOT A STYLE CHOICE.** No
 * gate in this repo reads rendered output, so a column that exists in the code
 * and never reaches the DOM — a cell renderer that returns nothing, a `<details>`
 * that ships open because a class overrode `display` — passes `tsc`, eslint and
 * every prop-shaped assertion. The markup is the only witness, and every case
 * below was re-proved RED by sabotaging exactly the thing it names.
 *
 * ⚠ **PROVED RED FIRST (hard-won law 7).** Before `CustomerStatementPage.tsx`
 * existed, vitest reported, verbatim:
 *
 *     Error: Failed to load url ./CustomerStatementPage (resolved id:
 *     ./CustomerStatementPage) ... Does the file exist?
 */
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import "@/i18n";
import i18n from "@/i18n";

import type { CustomerStatement } from "@/features/customers/customerEndpoints";

import { CustomerStatementTable, customerFromSearch } from "./CustomerStatementPage";

const t = i18n.getFixedT("en");
const translate = (key: string, params?: Record<string, unknown>) => t(key, params) as string;

/** One landlord, three accounts, one of them jointly held and one of them
 *  linked by an import that vouched for nothing. */
const STATEMENT: CustomerStatement = {
  basis: "posting",
  currency: "USD",
  customer: {
    id: "c1",
    customer_no: "C-1000",
    display_name: "Alvarez Property Co",
    kind: "business",
  },
  account_count: 3,
  rows: [
    {
      id: "a1",
      account_no: "ACC-1042",
      kind: "residential",
      status_code: "active",
      status_name: "Active",
      balance: "152.320000",
      match_tier: "strong",
      confident: true,
      held_with: ["Rosa Alvarez"],
    },
    {
      id: "a2",
      account_no: "ACC-1051",
      kind: "residential",
      status_code: "active",
      status_name: "Active",
      balance: "45.000000",
      match_tier: "probable",
      confident: true,
      held_with: [],
    },
    {
      id: "a3",
      account_no: "ACC-0009",
      kind: "master",
      status_code: "active",
      status_name: "Active",
      balance: "10.000000",
      match_tier: null,
      confident: false,
      held_with: [],
    },
  ],
  total: "197.320000",
  unconfident_total: "10.000000",
  unconfident_count: 1,
  available: true,
  unavailable: [],
};

describe("CR-060 C16 — the customer statement", () => {
  it("draws every account by NUMBER and prints no database id (B14 rule 31)", () => {
    const html = renderToStaticMarkup(
      <CustomerStatementTable statement={STATEMENT} t={translate} />,
    );
    expect(html).toContain("ACC-1042");
    expect(html).toContain("ACC-1051");
    expect(html).toContain("ACC-0009");
    // The row ids are React keys and a click's payload. They must not be text.
    expect(html).not.toContain(">a1<");
    expect(html).not.toContain(">a2<");
    expect(html).not.toContain(">a3<");
  });

  it("names the OTHER holder of a joint account, at its full value (rule 2)", () => {
    // Joint and several liability, correctly presented: the figure is not
    // halved, and the name is what explains it appearing twice.
    const html = renderToStaticMarkup(
      <CustomerStatementTable statement={STATEMENT} t={translate} />,
    );
    expect(html).toContain("Rosa Alvarez");
    expect(html).toContain("152.32");
    expect(html).not.toContain("76.16"); // half of it, which is the defect
  });

  it("MARKS an untiered link rather than merging or dropping it (rule 3)", () => {
    const html = renderToStaticMarkup(
      <CustomerStatementTable statement={STATEMENT} t={translate} />,
    );
    // Listed…
    expect(html).toContain("ACC-0009");
    expect(html).toContain("10.00");
    // …and marked. The pill is the mark, and it is the only thing that tells a
    // reader this row is not in the total.
    expect(html).toContain("Unverified link");
  });

  it("renders an unreadable balance as an ABSENCE, never as 0.00 (DEF-127)", () => {
    // The exact shape that told a customer owing 108.88 that they owed nothing.
    const unreadable: CustomerStatement = {
      ...STATEMENT,
      currency: null,
      total: null,
      unconfident_total: null,
      available: false,
      rows: [{ ...STATEMENT.rows[0], balance: null }],
      account_count: 1,
      unavailable: [
        {
          code: "ledger_publishes_no_per_account_ar_position",
          br_ref: "BR-CUS-015",
          detail: "server prose that never reaches a screen",
          wanted_reads: [],
        },
      ],
    };
    const html = renderToStaticMarkup(
      <CustomerStatementTable statement={unreadable} t={translate} />,
    );
    expect(html).toContain("Not available");
    expect(html).not.toContain("0.00");
    // B14 rule 32 — the reason is behind a `<details>` CLOSED by default, in
    // `AbsentFigure`'s ratified shape, and the summary is what stays visible.
    expect(html).toContain("<details><summary");
    // B14 rule 31 — the server's own `code` and `br_ref` never reach the reader.
    expect(html).not.toContain("ledger_publishes_no_per_account_ar_position");
    expect(html).not.toContain("BR-CUS-015");
    // BR-SHL-020 / the TD-16 rule: the server's English `detail` is never printed.
    expect(html).not.toContain("server prose that never reaches a screen");
  });

  it("reads its subject off the URL and never off component state", () => {
    // BR-SHL-011 — a statement someone ran is a link they can send.
    expect(customerFromSearch(new URLSearchParams("customer=c1"))).toBe("c1");
    expect(customerFromSearch(new URLSearchParams(""))).toBe("");
  });
});

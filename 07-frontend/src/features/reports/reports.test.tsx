// ── Trace ──────────────────────────────────────────────
// Story:    US-LED-009 (S59 account ledger — the per-account running ledger) ·
//           US-LED-010 (S60 by-premises summary) · US-LED-002 (the premises
//           dimension these reports are waiting on)
//           Screens: S59 · S60
// Rules:    BR-REP-001 (every money figure declares its date basis) ·
//           BR-REP-008 (a report states what it could not attribute) ·
//           BR-SHL-020 (plain-language failure) · BR-SHL-023 (one money path) ·
//           CLAUDE.md rule 2 (money is a decimal string, never a float)
// ───────────────────────────────────────────────────────
// THE ASSERTIONS THAT MATTER HERE ARE THE NEGATIVE ONES, and they are the whole
// reason this file exists rather than a smoke test.
//
// S60 has no rows and will have none until US-LED-002 stamps a premises onto
// the chain. The tempting screen is one that renders a single "Unassigned" row
// holding the entire book, or an empty table with a cheerful "no data" — both
// read as an answer. The real answer is that **553.69 was billed and 446.37
// collected, and neither can be attributed to a premises yet**, which is what
// the server says and what this screen must repeat.
//
// S59 refuses to run at all until it has an account and both dates: a ledger
// with no window would print a customer's whole history under whatever heading
// the screen happened to draw (US-LED-009 TC-6).
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import {
  REPORT_KEY_ACCOUNT_LEDGER,
  REPORT_KEY_BY_PREMISES,
  reportPath,
} from "@/api/endpoints";

import {
  accountLedgerParamsFrom,
  accountLedgerReady,
  accountLedgerSearchFrom,
} from "./AccountLedgerReportPage";
import { byPremisesKpis, UnattributedPanel } from "./ByPremisesReportPage";
import { ACCOUNT_LEDGER_ROUTE, BY_PREMISES_ROUTE } from "./reportsShared";

const t = i18n.getFixedT("en");

//: US-LED-010 §4 — the figures the read model returns on a tenant whose
//: premises dimension has never been written. Not invented here: they are the
//: same 553.69 / 446.37 the backend suite and the ledger review row assert.
const BY_PREMISES = {
  available: false,
  basis: "posting",
  currency: "USD",
  period: { start: "2026-07-01", end: "2026-07-31" },
  rows: [],
  kpis: { premises: 0, billed: "553.690000", collected: "446.370000", owed: "107.320000" },
  unattributed_billed: "553.690000",
  unattributed_collected: "446.370000",
  unavailable: [
    {
      code: "premises_and_unit_dimensions_never_stamped",
      br_ref: "BR-REP-008",
    },
  ],
} as never;

describe("US-LED-010 · S60 by-premises", () => {
  it("US-LED-010 TC-1: every money KPI carries its basis, and the count is not money", () => {
    const tiles = byPremisesKpis(BY_PREMISES, t, "en-US");
    // `KpiTile` is a UNION — a tile carries money or a value, never both — so
    // narrowing here is the type system stating BR-REP-001 rather than a
    // formality: an unlabeled money KPI is not expressible.
    const money = tiles.filter((tile) => "money" in tile);
    expect(money).toHaveLength(3);
    for (const tile of money) {
      if (!("money" in tile)) continue;
      // BR-REP-001. A money figure with no basis is not expressible in KpiTile,
      // so this asserts the screen actually passed one rather than that the
      // type allowed it.
      expect(tile.money.basis).toBe("posting");
      expect(tile.money.currency).toBe("USD");
      // CLAUDE.md rule 2 — it stays the served decimal STRING all the way here.
      expect(typeof tile.money.amount).toBe("string");
    }
    const premises = tiles.find((tile) => tile.id === "premises");
    expect(premises && "money" in premises).toBe(false);
    expect(premises && "value" in premises ? premises.value : null).toBe(0);
  });

  it("US-LED-010 TC-2: with no rows it states the money it could NOT attribute", () => {
    const html = renderToStaticMarkup(
      <UnattributedPanel report={BY_PREMISES} t={t} locale="en-US" />,
    );
    // The two figures a blank report would swallow.
    expect(html).toContain("553.69");
    expect(html).toContain("446.37");
    // And it must not have invented a bucket to hold them.
    expect(html.toLowerCase()).not.toContain("unassigned premises");
  });

  it("US-LED-010 TC-3: the reason is a sentence, never the server's code", () => {
    const html = renderToStaticMarkup(
      <UnattributedPanel report={BY_PREMISES} t={t} locale="en-US" />,
    );
    expect(html).not.toContain("premises_and_unit_dimensions_never_stamped");
  });
});

describe("US-LED-009 · S59 account ledger", () => {
  it("US-LED-009 TC-6: the report will not run without an account and both dates", () => {
    expect(accountLedgerReady({ accountId: "", from: "2026-07-01", to: "2026-07-31" })).toBe(false);
    expect(accountLedgerReady({ accountId: "A-10432", from: "", to: "2026-07-31" })).toBe(false);
    expect(accountLedgerReady({ accountId: "A-10432", from: "2026-07-01", to: "" })).toBe(false);
    expect(accountLedgerReady({ accountId: "A-10432", from: "2026-07-01", to: "2026-07-31" })).toBe(
      true,
    );
  });

  it("US-LED-009 TC-6: the parameters survive a round trip through the URL", () => {
    const params = { accountId: "A-10432", from: "2026-07-01", to: "2026-07-31" };
    expect(accountLedgerParamsFrom(accountLedgerSearchFrom(params))).toEqual(params);
  });

  it("US-LED-009 TC-6: an empty parameter is left OUT of the URL, not sent blank", () => {
    // A `f.from=` with nothing after it is a value the server has to interpret;
    // an absent key is a question that was never asked (BR-SHL-011).
    const search = accountLedgerSearchFrom({ accountId: "A-10432", from: "", to: "" });
    expect(search.has("f.from")).toBe(false);
    expect(search.has("f.to")).toBe(false);
    expect(search.get("f.account_id")).toBe("A-10432");
  });
});


// ══════════════════════════════════════════════════════════════════════════
// DEF-131 — THE TWO REPORT KEYS, PINNED TO THE SERVER'S OWN REGISTRY.
//
// S59 and S60 could not render FOR ANYONE for a day: this client sent
// `account-ledger` and `by-premises`, `apps/reports/api.py` has always
// registered `account_ledger` and `by_premises`, and every request answered
// 422 `reports.viewer.unknown_key`. Both files' comments admitted uncertainty
// about the vocabulary — one said the strings were "NOT CONTRACTED ANYWHERE"
// and the other "PROPOSED by this lane" — and neither asked the server.
//
// The literals below are the SERVER's, copied from `apps/reports/api.py`
// (KEY_ACCOUNT_LEDGER / KEY_BY_PREMISES) and confirmed against a running
// instance whose refusal enumerates its live vocabulary:
//     "keys": ["account_ledger", "by_premises"]
// Written as literals on purpose: a test that derived them from the same
// constant it is checking would pass on any value, including the wrong one.
// ══════════════════════════════════════════════════════════════════════════
describe("DEF-131 — the report keys are the server's, not a guess", () => {
  it("the API keys match apps/reports/api.py exactly", () => {
    expect(REPORT_KEY_ACCOUNT_LEDGER).toBe("account_ledger");
    expect(REPORT_KEY_BY_PREMISES).toBe("by_premises");
  });

  it("`reportPath` builds the path the server actually serves", () => {
    expect(reportPath(REPORT_KEY_BY_PREMISES)).toBe("/reports/by_premises");
    expect(reportPath(REPORT_KEY_ACCOUNT_LEDGER)).toBe("/reports/account_ledger");
  });

  it("the URL a human sees stays hyphenated and is a DIFFERENT string", () => {
    // The two vocabularies are separate now precisely so a display choice can
    // never again decide an API contract. `/reports/by_premises` in a browser
    // bar is not what anybody wants, and that is a UI opinion, not a contract.
    expect(BY_PREMISES_ROUTE).toBe("/reports/by-premises");
    expect(ACCOUNT_LEDGER_ROUTE).toBe("/reports/account-ledger");
    expect(BY_PREMISES_ROUTE).not.toContain(REPORT_KEY_BY_PREMISES);
  });

  it("DEF-144 · the unknown-key refusal INTERPOLATES rather than printing braces", () => {
    // The string used i18next SINGLE braces, which i18next does not
    // interpolate, so a user was shown the literal "{key}" and "{keys}".
    const rendered = i18n.t("reports.viewer.unknown_key", {
      key: "by-premises",
      keys: "account_ledger, by_premises",
    });
    expect(rendered).toContain("by-premises");
    expect(rendered).toContain("account_ledger, by_premises");
    expect(rendered).not.toContain("{key}");
    expect(rendered).not.toContain("{{key}}");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-LED-009@33253a0 (same five sources as apps/reports/api.py, which
//         serves these two reports; co-packet US-LED-010)
// generated: 2026-08-12 by the orchestrating session — the W5 finance-screens
//         lane authored the three screens and was cut off before its tests, so
//         G10 stood red naming exactly these stories.
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — a test file calls no endpoint) E=deferred(no-frontend-half — this IS the frontend half's test) F✔ G✔ H=deferred(PO 2026-08-09)
// gates: G10 was RED naming US-LED-009 and US-LED-010 before this file existed
//         — that is the red-proof, and it is the gate's own output rather than
//         a mutation invented for the occasion.
// exceptions: the full-page components are not mounted here. They pull a live
//         query client, a router and a permissions context, and this file's job
//         is the money-and-refusal contract rather than the wiring those three
//         provide — mounting them would test React, not the report.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

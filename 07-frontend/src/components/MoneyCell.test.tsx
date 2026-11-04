// ── Trace ──────────────────────────────────────────────
// Story:    US-SHL-013 (EP-SHL-05 §Stories)  Screens: every money display (S17, S30, S33, S36, …)
// Rules:    BR-SHL-023 (2dp at display, one path) · BR-REP-001 (basis label)
// ───────────────────────────────────────────────────────
// TC tests for FE-11 MoneyCell. Money is a decimal STRING end to end — these
// tests prove no float ever touches it and no rounding decision is ever made
// client-side (the server rounds for display, G9/B4).
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import "@/i18n"; // initializes the i18next singleton with the five catalogs

import {
  DEFAULT_MONEY_LOCALE,
  MoneyAmountAbsent,
  MoneyCell,
  formatMoney,
  formatMoneyInput,
  formatRate,
  formatRateNumber,
} from "./MoneyCell";

describe("US-SHL-013 — MoneyCell (FE-11): 2dp currency display over decimal strings", () => {
  it("US-SHL-013 TC-1 (money half): invoice total 148.63 USD renders \"$148.63\"; a tenant locale switch re-renders with no code change", () => {
    // §4 test data: invoice BL-2608-018410 total $148.63 (Silver Creek, USD).
    expect(formatMoney("148.63", "USD")).toBe("$148.63");
    expect(DEFAULT_MONEY_LOCALE).toBe("en-US");
    // The SAME value under a different Regional number format (IS-8): only the
    // locale prop changes — zero per-screen format code.
    expect(formatMoney("1234.5", "EUR", "de-DE")).toBe("1.234,50 €");

    const html = renderToStaticMarkup(<MoneyCell amount="148.63" currency="USD" />);
    expect(html).toContain('class="cell-money"');
    expect(html).toContain("$148.63");
  });

  it("US-SHL-013 (BR-SHL-023): 2dp display — short fractions pad, never round: '148.6' → $148.60, '1240' → $1,240.00", () => {
    expect(formatMoney("148.6", "USD")).toBe("$148.60");
    expect(formatMoney("1240", "USD")).toBe("$1,240.00");
    expect(formatMoney("-42.50", "USD")).toBe("-$42.50");
  });

  // ── DEF-088 / BR-TEN-080 ────────────────────────────────────────────────
  // THE ASSERTION THAT WAS MISSING. Every test above this line asserts a VALUE
  // or a refusal; none asserted how many decimal places reach the screen, which
  // is exactly how the UI shipped showing four of them (DEF-088, PO 2026-08-12:
  // "Currently UI is howing 4 decimals on screen"). These read the wire figure
  // in and require the RENDERED STRING to carry two decimals and no more.
  it("US-SHL-013 / BR-TEN-080 (DEF-088): a wire figure of 8.2985 RENDERS \"$8.30\" — the DOM string carries exactly 2 decimals", () => {
    // BR-TEN-080's own worked figure: a tax line computing to 8.2985 travels as
    // 8.2985 (the API serves 4 dp) and must READ $8.30 to a customer.
    expect(formatMoney("8.2985", "USD")).toBe("$8.30");

    const html = renderToStaticMarkup(<MoneyCell amount="8.2985" currency="USD" />);
    expect(html).toContain("$8.30");
    expect(html).not.toContain("8.2985");

    // The decimal places are counted in the RENDERED text, not assumed from the
    // input: 2, always, whatever precision the wire carried.
    const rendered = html.replace(/<[^>]*>/g, "");
    expect(rendered.match(/\.(\d+)/)?.[1]).toHaveLength(2);
  });

  it("US-SHL-013 / B4.4 (DEF-088): display rounding is HALF-UP at 2 dp, over decimal strings — never float arithmetic", () => {
    // B4.4 ❄️ (finance-signed): round half-up, 2 dp. The same rule the backend
    // applies at finalization — display does not invent a second convention.
    expect(formatMoney("8.295", "USD")).toBe("$8.30"); // tie → up
    expect(formatMoney("8.294999", "USD")).toBe("$8.29"); // below tie → down
    expect(formatMoney("-8.295", "USD")).toBe("-$8.30"); // half-up = away from zero
    // 8.005 is the float trap: as an IEEE-754 double it is 8.00499999999999989,
    // so ANY path through Number()/toFixed renders $8.00. The decimal-string
    // path renders $8.01. This assertion is the float detector.
    expect(formatMoney("8.005", "USD")).toBe("$8.01");
    // Precision beyond IEEE-754, still rounded half-up at 2 dp.
    expect(formatMoney("12345678901234567.895", "USD")).toBe("$12,345,678,901,234,567.90");
  });

  it("US-SHL-013 / BR-TEN-080 (DEF-088): 2 dp is locale-independent — a de-DE tenant gets 2 decimals too, in its own separators", () => {
    // A utility in one locale and a customer in another both get 2 decimals;
    // only the separators and symbol placement differ (IS-8).
    // The gap before the € is U+00A0, as the de-DE assertion above uses.
    // What is being asserted here is the COUNT of decimals, not the spacing.
    expect(formatMoney("8.2985", "EUR", "de-DE")).toBe("8,30 €");
    expect(formatMoney("1234.5678", "EUR", "de-DE")).toBe("1.234,57 €");
    expect(formatMoney("1234.5678", "USD", "en-US")).toBe("$1,234.57");
  });

  it("US-SHL-013 (CLAUDE.md #2): the amount never passes through Number()/float — precision beyond IEEE-754 survives intact", () => {
    // 17 significant integer digits + 2dp: a float path would mangle this.
    expect(formatMoney("12345678901234567.89", "USD")).toBe("$12,345,678,901,234,567.89");
  });

  it("US-SHL-013 (negative): malformed amounts and unknown currency codes render verbatim — never NaN, never a crash", () => {
    expect(formatMoney("N/A", "USD")).toBe("N/A USD");
    expect(formatMoney("12.3.4", "USD")).toBe("12.3.4 USD");
    expect(formatMoney("5.00", "???")).toBe("5.00 ???");
  });

  it("BR-REP-001: the basis prop renders the date-basis label beside the figure; no basis prop, no label", () => {
    const posting = renderToStaticMarkup(
      <MoneyCell amount="184320.00" currency="USD" basis="posting" />,
    );
    expect(posting).toContain("Posting date");
    const clearing = renderToStaticMarkup(
      <MoneyCell amount="4212.09" currency="USD" basis="clearing" />,
    );
    expect(clearing).toContain("Clearing date");
    const unlabeled = renderToStaticMarkup(<MoneyCell amount="148.63" currency="USD" />);
    expect(unlabeled).not.toContain("cell-money-basis");
  });

  // ── DEF-151 ─────────────────────────────────────────────────────────────
  // A MONEY RENDERER CANNOT RENDER AN ABSENCE, and until this assertion it
  // rendered one badly. `apps/ledger/wire.py` serves `written_off_ytd: null`,
  // `endpoints.ts` typed it `string`, and the null fell through to the verbatim
  // fallback below `DECIMAL_STRING_RE` — so the S36 tile read the literal text
  // **`null USD`** on a live finance screen, beside five tiles that said *Not
  // available* with a reason. The verbatim fallback is RIGHT for a malformed
  // amount and exactly wrong for an absent one, and nothing distinguished them.
  it("DEF-151: an ABSENT amount is refused at the boundary — never rendered as 'null USD'", () => {
    const absent = null as unknown as string;
    expect(() => formatMoney(absent, "USD")).toThrow(MoneyAmountAbsent);
    expect(() => formatMoney(undefined as unknown as string, "USD")).toThrow(MoneyAmountAbsent);
    expect(() => renderToStaticMarkup(<MoneyCell amount={absent} currency="USD" />)).toThrow(
      MoneyAmountAbsent,
    );
    // The old behaviour, pinned as the thing that must never come back.
    let rendered = "";
    try {
      rendered = formatMoney(absent, "USD");
    } catch {
      rendered = "";
    }
    expect(rendered).not.toBe("null USD");

    // A MALFORMED amount is a different fact and keeps its verbatim rendering:
    // "12.3.4 USD" beats "NaN", and beats a client-side guess at what the
    // server meant. Refusing this one too would have been an over-correction.
    expect(formatMoney("12.3.4", "USD")).toBe("12.3.4 USD");
    // …and a genuine zero is a figure, not an absence. It still renders.
    expect(formatMoney("0.000000", "USD")).toBe("$0.00");
  });
});

// ── OQ-620(a) · A TARIFF RATE IS A THIRD KIND OF NUMBER ─────────────────────
//
// PO 2026-08-27, closing OQ-620(a), verbatim: *"What does a tariff rate show?
// Four ($0.1420). A rate is not money and not a quantity - 4 decimal places"*.
//
// ⚠ **THESE CASES SIT BESIDE THE MONEY ONES ON PURPOSE.** The failure this
// suite exists to catch is not getting a rate wrong — it is reaching for
// `formatMoney` instead, which produces `$8.29` from the same input: a
// perfectly well-formed currency string, two decimal places short of the
// precision the line was priced at. Several cases below assert the NEGATIVE
// for exactly that reason.
describe("PO 2026-10-02 — formatRate: unit prices up to 4 decimals, totals at 2", () => {
  // PO, verbatim: *"Show unit prices with up to 4 decimals and keep every total
  // at 2."* Narrows OQ-620(a)'s four-places-zeros-KEPT form (`$8.2900`).
  it("the figures put to the PO: $0.0425 stays $0.0425 (it read $0.04)", () => {
    expect(formatRate("0.042500", "USD")).toBe("$0.0425");
    expect(formatRate("0.042500", "USD")).not.toBe(formatMoney("0.042500", "USD")); // "$0.04"
    expect(formatRate("12.5", "USD")).toBe("$12.50");
    expect(formatRate("0.100000", "USD")).toBe("$0.10");
  });

  it("a TOTAL stays at two: $425.00 is formatMoney's and does not move", () => {
    // 10,000 gal × $0.0425 — the amount the PO was shown beside the price.
    expect(formatMoney("425.000000", "USD")).toBe("$425.00");
    expect(formatMoney("425.0000", "USD")).not.toBe("$425.0000");
  });

  it("zeros after the SECOND place are dropped; never fewer than two", () => {
    expect(formatRate("8.290000", "USD")).toBe("$8.29"); // was $8.2900
    expect(formatRate("0.142000", "USD")).toBe("$0.142"); // was $0.1420
    expect(formatRate("12", "USD")).toBe("$12.00"); // padded to the floor
    expect(formatRate("0", "USD")).toBe("$0.00");
    expect(formatRate("8.290000", "USD")).not.toBe("$8.290000"); // never verbatim
  });

  it("half-up at the FOURTH place — B4's direction, at the price's own scale", () => {
    expect(formatRate("0.14205", "USD")).toBe("$0.1421"); // AT the tie → up
    expect(formatRate("0.142049", "USD")).toBe("$0.142"); // below → down, zero dropped
    expect(formatRate("-0.14205", "USD")).toBe("-$0.1421"); // away from zero
  });

  it("the currency rides WITH the rate and is never assumed", () => {
    expect(formatRate("0.142000", "EUR", "de-DE")).toBe("0,142 €");
    expect(formatRate("1234.5", "USD")).toBe("$1,234.50");
  });

  it("formatRateNumber — the same rule with no currency to print", () => {
    expect(formatRateNumber("0.002500")).toBe("0.0025");
    expect(formatRateNumber("5.000000")).toBe("5.00");
    expect(formatRateNumber("N/A")).toBe("N/A");
  });

  it("never through a float — a NUMERIC(18,6) rate can exceed a double", () => {
    expect(formatRate("12345678901234567.891234", "USD")).toBe(
      "$12,345,678,901,234,567.8912",
    );
    expect(formatRate("12345678901234567.800000", "USD")).toBe("$12,345,678,901,234,567.80");
  });

  it("malformed or unknown renders verbatim, never NaN and never a crash", () => {
    expect(formatRate("N/A", "USD")).toBe("N/A USD");
    expect(formatRate("5.00", "???")).toBe("5.00 ???");
  });

  it("an absent rate throws rather than rendering a zero (DEF-151's rule)", () => {
    expect(() => formatRate(null as unknown as string, "USD")).toThrow(MoneyAmountAbsent);
  });
});

// ══════════════════════════════════════════════════════════════════════════
describe("DEF-CUS-4999 / DEF-CUS-5008 — formatMoneyInput: 2dp for a box a person edits", () => {
  it("trims the served 4dp/6dp column to exactly two decimals", () => {
    // The two figures the step-1 lanes measured on the S22 Record payment
    // modal, at the precision the wire really carries them at.
    expect(formatMoneyInput("2410.000000")).toBe("2410.00");
    expect(formatMoneyInput("247.300000")).toBe("247.30");
    // Both directions, like `formatMoney`: it pads as well as it trims.
    expect(formatMoneyInput("148.6")).toBe("148.60");
    expect(formatMoneyInput("0")).toBe("0.00");
    expect(formatMoneyInput("-31.5")).toBe("-31.50");
  });

  it("rounds half-up on the decimal string's exact value — the float detector", () => {
    // 8.005 as an IEEE-754 double is 8.00499999999999989, so any path through
    // Number()/toFixed answers 8.00. B4.4 ❄️ is half-up and this must be 8.01.
    // Same assertion `formatMoney` carries, because it is the same engine and
    // the same `roundingMode`; a second implementation is what would drift.
    expect(formatMoneyInput("8.005")).toBe("8.01");
    expect(formatMoneyInput("8.2985")).toBe("8.30");
  });

  it("NO symbol, NO grouping and NO locale — the value goes back to the server", () => {
    // This is the difference from `formatMoney` and the whole reason the
    // function exists: `$2,410.00` in a box the serializer parses is a
    // refused payment, and a `de-DE` `2410,00` is the same bug wearing a
    // comma. The locale is pinned to the wire's and is deliberately not a
    // parameter, so no caller can reintroduce it.
    expect(formatMoneyInput("2410.000000")).not.toContain("$");
    expect(formatMoneyInput("2410.000000")).not.toContain(",");
    expect(formatMoneyInput("1234567.891")).toBe("1234567.89");
  });

  it("an absent amount is the EMPTY STRING — never a zero and never a throw", () => {
    // `formatMoney` throws `MoneyAmountAbsent` (DEF-151) and that is right for
    // a CELL: a figure the books will not state is not rendered as money. A
    // required FORM FIELD cannot render a sentence, and `0.00` would be a
    // number nobody read off a cheque that submits cleanly — so the box opens
    // empty and asks.
    expect(formatMoneyInput(null)).toBe("");
    expect(formatMoneyInput(undefined)).toBe("");
    expect(() => formatMoneyInput(null)).not.toThrow();
  });

  it("a malformed amount comes back VERBATIM, exactly as formatMoney does", () => {
    // The clerk sees what the server actually sent, never a client's guess at
    // what it meant. `formatMoney`'s own rule, kept identical on purpose.
    expect(formatMoneyInput("N/A")).toBe("N/A");
    expect(formatMoneyInput("")).toBe("");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-SHL-013@1e89ecb (story+rules snapshot hash)
// generated: 2026-08-09 by story-coder v1
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-08)
// gates: trace_lint✔ run_gates✔ (10 PASS · 0 FAIL · 2 SKIP) tsc✔ eslint✔ vitest 94/94✔ (12 todo this packet — browser/server/consumer scope) · [2026-08-15 DEF-088 display-precision lane] RED PROVED FIRST — the S30 tax line rendered `<span class="cell-money-amount">$8.2985</span>` and all 6 new assertions failed against the pre-fix formatter (verbatim in the lane report). MEASURED, THIS LANE'S OWN FILES ONLY: MoneyCell.test.tsx 8 tests (was 6) · BillDetailPage.test.tsx 22 tests / 3 skipped (was 20 / 3) · PaymentsPage.test.tsx 17 tests (was 15) — 44 passed / 3 todo across the three, all green. The FULL suite total is deliberately not quoted: a concurrent 07-frontend settings lane was adding files throughout, so no whole-suite number here would be reproducible. tsc --noEmit✔ · eslint --max-warnings 0✔ · vite build✔ · node --test server.test.mjs 10/10✔ · tsc -p tsconfig.e2e.json✔ · run_gates: 20 PASS · 0 FAIL at this lane's 17:55 baseline; the failures present at hand-off are named in the lane report and none is this lane's — no file it touched appears in any of them
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

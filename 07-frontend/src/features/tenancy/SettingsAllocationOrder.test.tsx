// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-009 (EP-TEN-07 SCOPE ADDENDUM — the S66 rule-page card) ·
//           US-PAY-006 (the within-invoice class order this setting IS)
//           Screens: S66 (Settings → Configure → Billing defaults)
// Rules:    BR-PAY-038 (the four within-invoice classes and the ruled default sequence) ·
//           BR-PAY-010 (allocation order — "tenant-configurable") · BR-TEN-024 (a partial
//           change set) · BR-SHL-025 (a view-only role gets disabled-with-reason) ·
//           BR-SHL-035 (the sequence control lives INSIDE the one rule-page shell)
// ───────────────────────────────────────────────────────
// THE LOAD-BEARING TEST IN THIS FILE IS THE PO'S OWN FIGURE.
//
// *"usage+base 100.58 + tax 8.30 + a tenant-defined service fee 15.00 + a late
// fee 5.00 = 128.88; a 120.00 payment meets 100.58, then 8.30, then 11.12 of
// the 15.00, and the late fee stays LAST at 0.00"* — ratified 2026-08-11
// (OQ-109 → BR-PAY-038), re-confirmed unmoved on 2026-08-12 when the sequence
// became a tenant setting and again on 2026-08-15 when the storage landed. If
// the panel a tenant reads it off ever disagrees with that, this file goes RED.
//
// The second half is the counter-case the 2026-08-15 lane recorded: move the
// fees class ahead of the tenant-defined one and the SAME payment pays the 5.00
// late fee and 6.12 of the service charge instead. A reorder control whose
// example did not MOVE would be a picture of a constant.
//
// The float detector is the MET column, and it was measured rather than
// assumed. The identical walk in IEEE-754 doubles pays the tenant-defined class
// 11.120000000000001 and leaves 3.879999999999999 owed on it, where the PO's
// ruling says 11.12 and 3.88 — and every figure loses its fixed two decimals
// besides ("8.3", "0", "120"). So `toEqual(["100.58","8.30","11.12","0.00"])`
// goes red the moment anything on this path goes through Number()
// (CLAUDE.md rule 2). NOTE what does NOT detect it: the bill TOTAL. The float
// sum of these four figures is 128.87999999999999545, which JavaScript prints
// as "128.88" — a total-only assertion would have passed over a float walk.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { RegionalSettings, RuleDocument } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  EXAMPLE_BILL_MINOR,
  EXAMPLE_PAYMENT_MINOR,
  minorToAmount,
  workedAllocation,
} from "./SettingsAllocationOrder";
import { RulePageView } from "./SettingsRulePageView";
import {
  ALLOCATION_CLASSES,
  ALLOCATION_CLASS_ORDER_KEY,
  BILLING_DEFAULTS_PAGE,
  draftFromDocument,
  moveInSequence,
  ruleChanges,
  ruleFieldValue,
  ruleIsDirty,
  sequenceFromDraft,
  sequenceToDraft,
} from "./settingsRulePages";

/** BR-PAY-038's ruled default, in the PO's own words. */
const RATIFIED_ORDER = ["usage_base", "taxes", "tenant_defined", "fees"];

/** The tenant who wants the late fee met BEFORE the service charge. Nothing
 *  signs this order — it is the tenant's, which is the point of the ruling. */
const FEES_BEFORE_TENANT_DEFINED = ["usage_base", "taxes", "fees", "tenant_defined"];

const S66: RuleDocument = {
  late_pct: "1.500000",
  late_min_amount: "5.000000",
  late_grace_days: 5,
  late_grace_mode: "calendar",
  minimum_bill_amount: null,
  overcharge_guardrail_pct: "200",
  allocation_order: "oldest_invoice_first",
  allocation_class_order: RATIFIED_ORDER,
  deposit_interest_rate_annual: "0",
};

const REGIONAL: RegionalSettings = {
  country: "US",
  state: "TX",
  timezone: "America/Chicago",
  language: "en",
  first_day_of_week: "sunday",
  currency: "USD",
  number_format: "1,234.56",
  date_format: "MM/DD/YYYY",
  time_format: "24h",
  fy_start_month: 10,
  fy_start_day: 1,
  accounting_method: "accrual",
  close_cadence: "monthly",
  close_day: "5",
  lock_closed_periods: true,
  current_period: null,
};

function renderS66(
  document: RuleDocument,
  options: { readOnly?: boolean; regional?: RegionalSettings | null } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.rulePage(BILLING_DEFAULTS_PAGE.slug), document);
  if (options.regional != null) {
    queryClient.setQueryData(queryKeys.regionalSettings, options.regional);
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <RulePageView page={BILLING_DEFAULTS_PAGE} readOnly={options.readOnly ?? false} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** `renderToStaticMarkup` escapes `&`, so a label containing one is compared
 *  in its rendered form rather than its catalogue form. */
function escaped(text: string): string {
  return text.replace(/&/g, "&amp;");
}

function metFor(order: readonly string[], klass: string): string {
  const row = workedAllocation(order).rows.find((candidate) => candidate.klass === klass);
  expect(row).toBeDefined();
  return row!.met;
}

describe("US-PAY-006 / BR-PAY-038 — the PO's worked figure, recomputed from the tenant's order", () => {
  it("US-TEN-009: under the RATIFIED default order the $120.00 payment meets 100.58, 8.30, 11.12 and 0.00", () => {
    const example = workedAllocation(RATIFIED_ORDER);
    expect(example.rows.map((row) => row.met)).toEqual(["100.58", "8.30", "11.12", "0.00"]);
    // …and what the bill states is unchanged by the order, of course.
    expect(example.rows.map((row) => row.billed)).toEqual(["100.58", "8.30", "15.00", "5.00"]);
    // The late fee is LAST and gets nothing; the service charge is short 3.88.
    expect(example.rows[3]).toEqual({ klass: "fees", billed: "5.00", met: "0.00", owed: "5.00" });
    expect(example.rows[2].owed).toBe("3.88");
    // The float detector: 100.58 + 8.30 + 15.00 + 5.00 is 128.88000000000002 in
    // IEEE-754 and 128.88 in exact arithmetic (CLAUDE.md rule 2).
    expect(example.total).toBe("128.88");
    expect(example.payment).toBe("120.00");
    expect(example.stillOwed).toBe("8.88");
  });

  it("US-PAY-006: moving fees ahead of the tenant class pays the 5.00 late fee and 6.12 of the 15.00", () => {
    const example = workedAllocation(FEES_BEFORE_TENANT_DEFINED);
    expect(example.rows.map((row) => row.met)).toEqual(["100.58", "8.30", "5.00", "6.12"]);
    expect(metFor(FEES_BEFORE_TENANT_DEFINED, "fees")).toBe("5.00");
    expect(metFor(FEES_BEFORE_TENANT_DEFINED, "tenant_defined")).toBe("6.12");
    // The same bill and the same payment — only the order moved. Neither the
    // total nor what is still owed can move with it.
    expect(example.total).toBe("128.88");
    expect(example.stillOwed).toBe("8.88");
  });

  it("tax first — the order an HOA or a submetering operator might set — is a different answer again", () => {
    const taxFirst = ["taxes", "usage_base", "tenant_defined", "fees"];
    const example = workedAllocation(taxFirst);
    expect(example.rows.map((row) => row.met)).toEqual(["8.30", "100.58", "11.12", "0.00"]);
    expect(example.total).toBe("128.88");
  });

  it("the illustration's own constants are the PO's, exactly", () => {
    expect(minorToAmount(EXAMPLE_PAYMENT_MINOR)).toBe("120.00");
    expect(minorToAmount(EXAMPLE_BILL_MINOR.usage_base)).toBe("100.58");
    expect(minorToAmount(EXAMPLE_BILL_MINOR.taxes)).toBe("8.30");
    expect(minorToAmount(EXAMPLE_BILL_MINOR.tenant_defined)).toBe("15.00");
    expect(minorToAmount(EXAMPLE_BILL_MINOR.fees)).toBe("5.00");
    // Trailing and leading zeros are formatted, never dropped: "8.30" not "8.3",
    // "0.00" not "0" — this is what an untrimmed toFixed-free path looks like.
    expect(minorToAmount(0n)).toBe("0.00");
    expect(minorToAmount(5n)).toBe("0.05");
    expect(minorToAmount(100n)).toBe("1.00");
  });
});

describe("BR-PAY-038 — the reorder control is explicit and reversible", () => {
  it("a move swaps with the neighbour, and the inverse move puts it back", () => {
    const down = moveInSequence(RATIFIED_ORDER, 2, 1);
    expect(down).toEqual(FEES_BEFORE_TENANT_DEFINED);
    // Its own inverse — which is the whole of "reversible". There is no undo
    // stack to build and no client-side copy of the shipped order to restore.
    expect(moveInSequence(down, 3, -1)).toEqual(RATIFIED_ORDER);
  });

  it("a move off either end is a NO-OP, never a wrap", () => {
    expect(moveInSequence(RATIFIED_ORDER, 0, -1)).toEqual(RATIFIED_ORDER);
    expect(moveInSequence(RATIFIED_ORDER, 3, 1)).toEqual(RATIFIED_ORDER);
    expect(moveInSequence(RATIFIED_ORDER, 9, 1)).toEqual(RATIFIED_ORDER);
    // …and it never mutates the array it was handed.
    const order = [...RATIFIED_ORDER];
    moveInSequence(order, 0, 1);
    expect(order).toEqual(RATIFIED_ORDER);
  });

  it("a move preserves membership, so the server's permutation rule cannot be broken from here", () => {
    let order = [...RATIFIED_ORDER];
    for (const [index, delta] of [
      [0, 1],
      [2, 1],
      [3, -1],
      [1, -1],
    ] as const) {
      order = moveInSequence(order, index, delta);
      expect([...order].sort()).toEqual([...ALLOCATION_CLASSES].sort());
    }
  });
});

describe("BR-TEN-024 — the order round-trips through the draft and posts as an ordered list", () => {
  it("the server's list becomes the draft and comes back as the same list", () => {
    const original = draftFromDocument(BILLING_DEFAULTS_PAGE, S66);
    expect(original[ALLOCATION_CLASS_ORDER_KEY]).toBe("usage_base,taxes,tenant_defined,fees");
    expect(sequenceFromDraft(original[ALLOCATION_CLASS_ORDER_KEY])).toEqual(RATIFIED_ORDER);
    // Untouched: nothing to post at all.
    expect(ruleIsDirty(BILLING_DEFAULTS_PAGE, original, original)).toBe(false);
    expect(ruleChanges(BILLING_DEFAULTS_PAGE, original, original)).toEqual({});
  });

  it("one reorder posts exactly one key, and its value is an ARRAY of the four classes", () => {
    const original = draftFromDocument(BILLING_DEFAULTS_PAGE, S66);
    const edited = {
      ...original,
      [ALLOCATION_CLASS_ORDER_KEY]: sequenceToDraft(FEES_BEFORE_TENANT_DEFINED),
    };
    expect(ruleIsDirty(BILLING_DEFAULTS_PAGE, edited, original)).toBe(true);
    expect(ruleChanges(BILLING_DEFAULTS_PAGE, edited, original)).toEqual({
      [ALLOCATION_CLASS_ORDER_KEY]: FEES_BEFORE_TENANT_DEFINED,
    });
  });

  it("the value is a string LIST on the wire — never a joined string the server would refuse", () => {
    const param = BILLING_DEFAULTS_PAGE.params.find((p) => p.key === ALLOCATION_CLASS_ORDER_KEY);
    expect(param?.kind).toBe("choice_sequence");
    const value = ruleFieldValue(param!, sequenceToDraft(RATIFIED_ORDER));
    expect(Array.isArray(value)).toBe(true);
    expect(value).toEqual(RATIFIED_ORDER);
  });
});

describe("hard-won law 2 — the control is WIRED into the S66 page, not merely built", () => {
  it("US-TEN-009: opening Billing defaults renders the four classes, in the tenant's order, with move controls", () => {
    const html = renderS66(S66, { regional: REGIONAL });
    expect(html).toContain("Payment allocation sequence within a bill");
    for (const klass of ALLOCATION_CLASSES) {
      expect(html).toContain(escaped(i18n.t(`settings.rules.choice.allocation_class_order.${klass}`)));
    }
    // …and in the ORDER the server stored, which is what makes it a setting
    // rather than a list: position 1 is usage+base, position 4 is fees.
    expect(html.indexOf(escaped(i18n.t("settings.rules.choice.allocation_class_order.usage_base")))).
      toBeLessThan(html.indexOf(i18n.t("settings.rules.choice.allocation_class_order.fees")));
    expect(html).toContain("Move up");
    expect(html).toContain("Move down");
    // ⚠ **INVERTED, `DEF-TEN-6935`.** This read `expect(html).toContain("Set by
    // BR-PAY-038")` — it asserted the defect. B14 rule 32 clause 4 bans a rule
    // id in clerk-facing copy, and the *why* it was answering is rationale,
    // which rule 33 puts at zero words on screen. Matched by SHAPE, not by the
    // one id: the id is interpolated from `param.br`, so an assertion naming
    // `BR-PAY-038` would pass the day the line comes back on another page.
    expect(html).not.toMatch(/BR-[A-Z]{3}-\d{3,5}/);
    // The help line KEEPS what a clerk acts on — what the order does.
    expect(html).toContain(i18n.t("settings.rules.sequence.help"));
  });

  it("the worked example is on the page, and it is the PO's figure", () => {
    const html = renderS66(S66, { regional: REGIONAL });
    expect(html).toContain("What this order does");
    // Rendered through the ONE money formatter at 2 dp (BR-SHL-023/BR-TEN-080).
    expect(html).toContain("$100.58");
    expect(html).toContain("$8.30");
    expect(html).toContain("$11.12");
    expect(html).toContain("$128.88");
    expect(html).toContain("$120.00");
    // …and it says, in words, that it is an illustration and not your money.
    expect(html).toContain("These figures are fixed and are an illustration only");
  });

  it("with no currency on file the figures still render — plainly, and saying why", () => {
    const html = renderS66(S66);
    expect(html).toContain("100.58");
    expect(html).not.toContain("$100.58");
    expect(html).toContain("Amounts are shown without a currency");
  });

  it("BR-SHL-025: a view-only role sees the control, disabled, with the reason", () => {
    const html = renderS66(S66, { readOnly: true, regional: REGIONAL });
    expect(html).toContain("Move up");
    expect(html).toContain("Your role can view this, but not change it.");
    // The classes are still readable — a forbidden control is disabled, never
    // vanished, and the worked example is a READ.
    expect(html).toContain("What this order does");
  });

  it("every string this control renders has copy in the catalog — no raw key reaches a user", () => {
    const keys = [
      "settings.rules.billing_defaults.allocation_class_order",
      "settings.rules.sequence.help",
      "settings.rules.sequence.listLabel",
      "settings.rules.sequence.moveUp",
      "settings.rules.sequence.moveDown",
      "settings.rules.sequence.positionLabel",
      "settings.rules.sequence.incomplete",
      "settings.rules.example.title",
      "settings.rules.example.lede",
      "settings.rules.example.colClass",
      "settings.rules.example.colBilled",
      "settings.rules.example.colMet",
      "settings.rules.example.colOwed",
      "settings.rules.example.billTotal",
      "settings.rules.example.note",
      "settings.rules.example.noCurrency",
      ...ALLOCATION_CLASSES.map((klass) => `settings.rules.choice.allocation_class_order.${klass}`),
    ];
    for (const key of keys) {
      expect(i18n.exists(key)).toBe(true);
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07, whose SCOPE ADDENDUM adds the S63–S71 cards; co-packet EP-PAY-02@0000000 for US-PAY-006's class order, a PLACEHOLDER hash — reported, not invented)
// generated: 2026-08-15 by story-coder (settings-screens lane)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — the endpoint is the existing PUT /settings/billing-defaults) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: PROVED RED FIRST, TWICE (hard-won law 7). (1) With the walk paying each class IN FULL regardless of what the payment had left, `expect(example.rows.map(row => row.met)).toEqual(["100.58","8.30","11.12","0.00"])` failed with received `["100.58","8.30","15.00","5.00"]` — 4 failed / 11 passed. (2) With the identical walk in IEEE-754 doubles the same assertion failed with received `["100.58","8.3","11.120000000000001","0"]` — 3 failed / 12 passed. Both restored and green afterwards. MEASURED AND WORTH RECORDING: the bill TOTAL is NOT a float detector — 100.58+8.30+15.00+5.00 in doubles is 128.87999999999999545, which JavaScript prints as "128.88", so a total-only assertion would have passed over a float walk. See the lane report for the suite totals
// exceptions: E3 there is no DOM in this suite (no jsdom, no @testing-library — the project's own posture), so a move is proved at the pure function `moveInSequence` and the mounting is proved through `renderToStaticMarkup` over a seeded query cache; the CLICK itself is not exercised — REPORTED
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

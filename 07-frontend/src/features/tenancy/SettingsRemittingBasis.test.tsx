// ── Trace ──────────────────────────────────────────────
// Story:    US-TEN-009 (EP-TEN-07 SCOPE ADDENDUM — the S71 rule-page card) ·
//           US-LED-014 (S41 dual-basis remittance — the report that consumes this setting
//           and supplies its authority list)
//           Screens: S71 (Settings → Configure → Finance controls) · S41
// Rules:    BR-LED-002 (BOTH bases always computed; a PER-AUTHORITY setting picks the one
//           each authority remits on) · BR-BIL-069 (each authority has its own 2200-nn
//           liability account — the CODE is this setting's key) · BR-TEN-022 (the
//           accounting period is COMPUTED, never stored) · BR-TEN-024 (a partial change
//           set) · BR-SHL-020 (plain-language failure)
// ───────────────────────────────────────────────────────
// THE LOAD-BEARING TESTS IN THIS FILE ARE ABOUT THE ABSENCE OF A DEFAULT.
//
// The server seeds `tax_remitting_basis_by_authority` EMPTY and never fills it,
// because LE-3 has State on COLLECTED and County on BILLED in the same month —
// so any shipped default is wrong for one of them in its first month. A screen
// can undo that in one character (`?? "billed"`), and the result would look
// completely normal: every authority pre-answered, nobody warned, and a utility
// filing on a basis it never chose.
//
// So: an authority with no entry must render as "Not set", clearing a choice
// must DELETE the key rather than store an empty one, and the panel must say
// what happens if it is left alone. Each of those is asserted below.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";
import type {
  CurrentPeriod,
  RegionalSettings,
  RemittanceResponse,
  RuleDocument,
} from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { periodKeyOf, unsetAuthorities } from "./SettingsRemittingBasis";
import { RulePageView } from "./SettingsRulePageView";
import {
  FINANCE_CONTROLS_PAGE,
  REMITTING_BASES,
  REMITTING_BASIS_KEY,
  basisMapFromDraft,
  basisMapToDraft,
  draftFromDocument,
  ruleChanges,
  ruleFieldValue,
  ruleIsDirty,
  withChoiceFor,
} from "./settingsRulePages";

const PERIOD: CurrentPeriod = {
  fy_label: "FY2026",
  period: 11,
  start: "2026-08-01",
  end: "2026-08-31",
  status: "open",
  close_by: null,
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
  current_period: PERIOD,
};

/** LE-3's four authorities, as `GET /finance/taxes` serves them. Each is its
 *  own 2200-nn liability account (BR-BIL-069) and the CODE is the key. */
function authority(code: string, name: string, billed: string, basis: string | null) {
  return {
    account_id: `acct-${code}`,
    code,
    name,
    billed,
    collected: null,
    remitted: "0.0000",
    outstanding_billed: billed,
    outstanding_collected: null,
    remitting_basis: basis,
    bases: ["posting", "clearing"],
    // OQ-1190 — the bill-sourced half of the row. This table reads only the
    // CODES and no amount at all, so the fixture states the absence rather than
    // inventing a figure it would never assert on.
    authority_name: null,
    billed_from_bills: null,
    bill_line_count: null,
    bill_count: 0,
    billed_delta: null,
    bills_agree: null,
    problems: [],
  };
}

const REMITTANCE: RemittanceResponse = {
  basis: { billed: "posting", collected: "clearing" },
  currency: "USD",
  period: { start: PERIOD.start, end: PERIOD.end },
  rows: [
    authority("2200-01", "State comptroller", "13.8700", "collected"),
    authority("2200-02", "County tax office", "2.2200", "billed"),
    authority("2200-03", "City of Brazos Bend", "4.4400", null),
    authority("2200-04", "Public Utility Commission", "0.4400", null),
  ],
  totals: {
    billed: "20.9700",
    collected: null,
    remitted: "0.0000",
    outstanding_billed: "20.9700",
    // OQ-1190 — null, because every row above states its bill-side figure as
    // absent and a partial sum under a column heading reads as the whole.
    billed_from_bills: null,
  },
  tie_out: { tax_payable_gl: "20.9700" },
  unavailable: [],
};

/** LE-3's own state, as the S41 report already reports it: State on COLLECTED,
 *  County on BILLED, in the same month for the same tenant. */
const S71: RuleDocument = {
  bank_match_date_tolerance_days: 3,
  write_off_threshold_amount: "5.000000",
  dso_target_days: 15,
  correction_approval_mode: "all",
  back_bill_cap_months: 12,
  back_bill_theft_exempt: true,
  tax_remitting_basis_by_authority: { "2200-01": "collected", "2200-02": "billed" },
};

function renderS71(
  document: RuleDocument,
  options: {
    readOnly?: boolean;
    regional?: RegionalSettings | null;
    remittance?: RemittanceResponse | null;
  } = {},
): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.rulePage(FINANCE_CONTROLS_PAGE.slug), document);
  const regional = options.regional === undefined ? REGIONAL : options.regional;
  if (regional != null) {
    queryClient.setQueryData(queryKeys.regionalSettings, regional);
  }
  const remittance = options.remittance === undefined ? REMITTANCE : options.remittance;
  if (remittance != null) {
    queryClient.setQueryData(
      queryKeys.remittanceByAuthority(periodKeyOf(regional?.current_period ?? null)),
      remittance,
    );
  }
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <RulePageView page={FINANCE_CONTROLS_PAGE} readOnly={options.readOnly ?? false} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * The same page with the authority read having actually FAILED.
 *
 * The cache is primed by running the query to rejection through the public
 * `fetchQuery`, rather than by poking a query's internal state: what the screen
 * then renders is the state a real 403 or 500 leaves behind, not a shape a test
 * invented. `renderToStaticMarkup` runs no effects, so nothing refetches.
 */
async function renderS71Failing(error: unknown): Promise<string> {
  // `retryOnMount: false` is a TEST-CLIENT setting, not a production one. A
  // freshly mounted observer over an errored query optimistically reports
  // *pending* while it re-fetches, which is the skeleton — true of the instant
  // after a remount and not of the state this test is about. Switching it off
  // pins the render to the state a user actually sits in once the request has
  // settled and failed.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, retryOnMount: false } },
  });
  queryClient.setQueryData(queryKeys.rulePage(FINANCE_CONTROLS_PAGE.slug), S71);
  queryClient.setQueryData(queryKeys.regionalSettings, REGIONAL);
  await queryClient
    .fetchQuery({
      queryKey: queryKeys.remittanceByAuthority(periodKeyOf(PERIOD)),
      queryFn: () => Promise.reject(error),
      retry: false,
    })
    .catch(() => undefined);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter>
          <RulePageView page={FINANCE_CONTROLS_PAGE} readOnly={false} />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("BR-LED-002 — the basis is PER AUTHORITY, and there is no default anywhere", () => {
  it("US-TEN-009: the two bases the rule names are the only two offered, and neither is preselected", () => {
    const param = FINANCE_CONTROLS_PAGE.params.find((p) => p.key === REMITTING_BASIS_KEY);
    expect(param?.kind).toBe("choice_map");
    expect(param?.choices).toEqual(["billed", "collected"]);
    expect([...REMITTING_BASES]).toEqual(["billed", "collected"]);
    // The seeded document is EMPTY on a fresh tenant, and the draft of an empty
    // map is an empty map — never one basis quietly applied to everybody.
    expect(draftFromDocument(FINANCE_CONTROLS_PAGE, { ...S71, [REMITTING_BASIS_KEY]: {} })[
      REMITTING_BASIS_KEY
    ]).toBe("{}");
    expect(basisMapFromDraft("{}")).toEqual({});
  });

  it("US-LED-014: LE-3's own case — State on collected and County on billed in the SAME month", () => {
    const chosen = basisMapFromDraft(
      draftFromDocument(FINANCE_CONTROLS_PAGE, S71)[REMITTING_BASIS_KEY],
    );
    expect(chosen).toEqual({ "2200-01": "collected", "2200-02": "billed" });
    // …and the two that nobody has ruled on are UNSET, not defaulted.
    expect(unsetAuthorities(REMITTANCE.rows, chosen)).toEqual(["2200-03", "2200-04"]);
    expect(chosen["2200-03"]).toBeUndefined();
  });

  it("clearing an authority DELETES its key — an unset basis survives the save", () => {
    const chosen = { "2200-01": "collected", "2200-02": "billed" };
    const cleared = withChoiceFor(chosen, "2200-01", "");
    expect(cleared).toEqual({ "2200-02": "billed" });
    expect("2200-01" in cleared).toBe(false);
    // Not `null`, not `""` — the server refuses a null inside the map precisely
    // so that "absent" and "null" cannot become two spellings of one state.
    expect(Object.values(cleared)).not.toContain(null);
    expect(Object.values(cleared)).not.toContain("");
    // …and it does not mutate what it was handed.
    expect(chosen["2200-01"]).toBe("collected");
  });

  it("setting a basis touches only that authority", () => {
    const chosen = { "2200-01": "collected" };
    expect(withChoiceFor(chosen, "2200-03", "billed")).toEqual({
      "2200-01": "collected",
      "2200-03": "billed",
    });
  });
});

describe("BR-TEN-024 — the map round-trips canonically and posts as one object", () => {
  it("two maps that differ only in key order encode identically, so nothing posts a change nobody made", () => {
    const a = basisMapToDraft({ "2200-02": "billed", "2200-01": "collected" });
    const b = basisMapToDraft({ "2200-01": "collected", "2200-02": "billed" });
    expect(a).toBe(b);
    const original = draftFromDocument(FINANCE_CONTROLS_PAGE, S71);
    const reshuffled = { ...original, [REMITTING_BASIS_KEY]: a };
    expect(ruleIsDirty(FINANCE_CONTROLS_PAGE, reshuffled, original)).toBe(false);
    expect(ruleChanges(FINANCE_CONTROLS_PAGE, reshuffled, original)).toEqual({});
  });

  it("one choice posts exactly one key, and its value is the whole MAP", () => {
    const original = draftFromDocument(FINANCE_CONTROLS_PAGE, S71);
    const chosen = basisMapFromDraft(original[REMITTING_BASIS_KEY]);
    const edited = {
      ...original,
      [REMITTING_BASIS_KEY]: basisMapToDraft(withChoiceFor(chosen, "2200-03", "billed")),
    };
    expect(ruleChanges(FINANCE_CONTROLS_PAGE, edited, original)).toEqual({
      [REMITTING_BASIS_KEY]: {
        "2200-01": "collected",
        "2200-02": "billed",
        "2200-03": "billed",
      },
    });
  });

  it("an EMPTY map posts as {} — never as null, which the server reads as required", () => {
    const param = FINANCE_CONTROLS_PAGE.params.find((p) => p.key === REMITTING_BASIS_KEY);
    expect(ruleFieldValue(param!, "{}")).toEqual({});
    expect(ruleFieldValue(param!, "{}")).not.toBeNull();
    // Unparseable text is an EMPTY map, never a partial one.
    expect(ruleFieldValue(param!, "not json")).toEqual({});
  });
});

describe("hard-won law 2 — the table is WIRED into the S71 page, not merely built", () => {
  it("US-LED-014: opening Finance controls lists every tax authority with its 2200-nn account", () => {
    const html = renderS71(S71);
    expect(html).toContain("Remitting basis, per tax authority");
    expect(html).toContain("2200-01");
    expect(html).toContain("State comptroller");
    expect(html).toContain("2200-04");
    expect(html).toContain("Public Utility Commission");
    // Both lawful bases are offered on every row, in the tenant's language.
    expect(html).toContain("What you billed");
    expect(html).toContain("What you collected");
    // ⚠ **INVERTED, `DEF-TEN-6935`** — see `SettingsAllocationOrder.test.tsx`
    // for why this is matched by shape rather than by the one id.
    expect(html).not.toMatch(/BR-[A-Z]{3}-\d{3,5}/);
    expect(html).toContain(i18n.t("settings.rules.basis.help"));
  });

  it("an authority with no basis is VISIBLY unset, and the screen says what unset does", () => {
    const html = renderS71(S71);
    // The marker is ON the row and only renders for a row with no choice — not
    // the select's placeholder option, which is present on every row.
    expect(html).toContain('<span class="settings-locked"> Not set</span>');
    expect(html).toContain("There is no default, on purpose");
    expect(html).toContain("still to be decided");
    // Named, not merely counted: a finance officer can see WHICH two.
    expect(html).toContain("2200-03, 2200-04");
  });

  it("a tenant who has chosen nothing gets four unset rows and no basis applied to any of them", () => {
    const html = renderS71({ ...S71, [REMITTING_BASIS_KEY]: {} });
    // The RENDER assertions come first on purpose: a `?? "billed"` anywhere on
    // this path has to be caught by what a utility SEES, not only by a helper.
    // Nothing is preselected — every select sits on its empty placeholder.
    expect(html).not.toContain('<option selected="" value="billed">');
    expect(html).not.toContain('<option selected="" value="collected">');
    expect(html.match(/<span class="settings-locked"> Not set<\/span>/g)).toHaveLength(4);
    expect(unsetAuthorities(REMITTANCE.rows, {})).toEqual([
      "2200-01",
      "2200-02",
      "2200-03",
      "2200-04",
    ]);
  });

  it("BR-TEN-022: with no fiscal calendar there is no period, and the table SAYS so", () => {
    const html = renderS71(S71, {
      regional: { ...REGIONAL, current_period: null },
      remittance: null,
    });
    expect(html).toContain("no fiscal calendar is set yet");
    // The warning about leaving an authority unset still stands, because the
    // setting exists whether or not this screen can list its authorities.
    expect(html).toContain("There is no default, on purpose");
    expect(html).not.toContain("2200-01");
  });

  it("while the authority list is still loading the page shows a skeleton, never an empty table", () => {
    const html = renderS71(S71, { remittance: null });
    expect(html).toContain("skeleton");
    expect(html).not.toContain("No tax authorities yet");
    // The unset warning stands even before the list arrives — it is a fact
    // about the setting, not about this read.
    expect(html).toContain("There is no default, on purpose");
  });

  it("BR-SHL-020: a read that fails says so in the server's own words, and that nothing saved has moved", async () => {
    const html = await renderS71Failing(
      new ApiError(403, { code: "AUTH-002", message_key: "errors.auth.forbidden" }),
    );
    expect(html).toContain("We couldn&#x27;t load your tax authorities");
    expect(html).toContain("Nothing you have already saved has changed.");
    // The server's own message rides beside ours — never swallowed, and never
    // replaced by a sentence this screen invented (TD-16/B8).
    expect(html).toContain(i18n.t("errors.auth.forbidden"));
  });

  it("a tenant with no authorities yet is told where they come from, not shown an empty table", () => {
    const html = renderS71(S71, { remittance: { ...REMITTANCE, rows: [] } });
    expect(html).toContain("No tax authorities yet");
    expect(html).not.toContain("2200-01");
  });

  it("periodKeyOf is the query identity — one period, one cached authority list", () => {
    expect(periodKeyOf(PERIOD)).toBe("2026-08-01|2026-08-31");
    expect(periodKeyOf(null)).toBe("");
  });

  it("every string this control renders has copy in the catalog — no raw key reaches a user", () => {
    const keys = [
      "settings.rules.finance_controls.tax_remitting_basis_by_authority",
      "settings.rules.basis.help",
      "settings.rules.basis.unsetWarning",
      "settings.rules.basis.tableLabel",
      "settings.rules.basis.colAuthority",
      "settings.rules.basis.colBasis",
      "settings.rules.basis.unset",
      "settings.rules.basis.unsetCount",
      "settings.rules.basis.empty",
      "settings.rules.basis.periodMissing",
      "settings.rules.basis.failed",
      ...REMITTING_BASES.map(
        (basis) => `settings.rules.choice.tax_remitting_basis_by_authority.${basis}`,
      ),
    ];
    for (const key of keys) {
      expect(i18n.exists(key)).toBe(true);
    }
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: US-TEN-009@178c282 (story+rules snapshot hash — EP-TEN-07, whose SCOPE ADDENDUM adds the S63–S71 cards; co-packet EP-LED-05@0000000 for US-LED-014, a PLACEHOLDER hash — reported, not invented)
// generated: 2026-08-15 by story-coder (settings-screens lane)
// checklist: A✔ B✔ C✔ D=deferred(no-API-half — the write is the existing PUT /settings/finance-controls and the read is the served GET /finance/taxes) E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: PROVED RED FIRST (hard-won law 7) — with `chosen[row.code] ?? "billed"` standing in for the unset state (the one-character mistake this whole file exists to catch), `expect(html).toContain("Not set")` failed and so did the four-unset-rows case, whose `unsetAuthorities` returned []. Green afterwards; see the lane report for the suite totals
// exceptions: E1 OQ-194 is OPEN — this suite asserts the control renders on S71 Finance controls, which is one of the question's two options and not a ruling. If the PO moves it to the Accounting tab these assertions move with it; the CHOICE-level assertions (unset stays unset, one key posts, the map is canonical) are placement-independent and would not · E3 there is no DOM in this suite (the project's posture), so a selection is proved at `withChoiceFor` and the mounting through `renderToStaticMarkup` over a seeded query cache; the CHANGE event itself is not exercised — REPORTED
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

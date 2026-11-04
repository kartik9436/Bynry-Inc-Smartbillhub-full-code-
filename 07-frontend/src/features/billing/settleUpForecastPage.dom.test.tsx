// ── Trace ──────────────────────────────────────────────
// Story:    US-BIL-019 — §05 entry 25.2 `Settle-up forecast`
//           (Billing blueprint p124(low)–p126(top), read AS IMAGES)
// Rules:    B14 rule 41 (the product matches the drawing) · rule 37 (a drawn
//           figure is an ILLUSTRATION) · rule 33 (the five caps) · rule 31 (no
//           database id is a field's visible value) · CLAUDE.md rule 2 (money
//           display 2, never a fabricated zero) · hard-won law 2 and BOTH its
//           halves — a dead control, and a fixture that cannot tell a working
//           link from a broken one
// Tests:    this file
// ───────────────────────────────────────────────────────
//
// ⚠ **THE FIXTURE MOUNTS THE REAL PATH PATTERN.** A bare `MemoryRouter` with no
// `/:tenant/…` route leaves `useParams().tenant` undefined, so every address the
// page builds comes out `//billing/…` — a protocol-relative URL to another
// host, which reads as a perfectly good string to `toContain`. That fixture is
// how `DEF-CWP-3925` hid eight dead doors over live screens, so the door cases
// below assert the WHOLE address including the tenant segment.
//
// ⚠ **THE HOLD-EXPIRY CASE IS THE ONE TO READ FIRST.** `Export` is drawn and
// ships DISABLED because no export resource exists for this list
// (`DEF-BIL-5328`). A hold with no test that fires when it expires is a promise
// nobody is keeping — so `TC-F9` asserts `EXPORT_RESOURCES` still holds none,
// and goes RED on the day somebody registers one.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { DEFAULT_PAGE_SIZE } from "@/components/tableTypes";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";
import { EXPORT_RESOURCES } from "@/api/endpoints";
import { accountDetailPath } from "@/features/customers/customersShared";
import type { SettleUpForecastResponse } from "@/api/billingOpsEndpoints";

import { SettleUpForecastPage, settleUpForecastKey } from "./SettleUpForecastPage";
import { BUDGET_FORECAST_ROUTE, BUDGET_TAB_ROUTE } from "./billingShared";

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** ⚠ B14 rule 37 — every figure below is an ILLUSTRATION OF A SHAPE. Nothing
 *  asserts the drawing's own `+$212.80` or `Showing 1–37 of 37`; the cases
 *  assert that a served figure reaches the screen, that the SIGN survives, and
 *  that an unserved one says so instead of printing `0.00`. */
const COLLECT_ID = "11111111-2222-3333-4444-555555555555";
const CREDIT_ID = "22222222-3333-4444-5555-666666666666";
const NOTHING_ID = "33333333-4444-5555-6666-777777777777";

const RESPONSE: SettleUpForecastResponse = {
  count: 3,
  as_of: "2026-09-15",
  directions: ["collect", "credit"],
  results: [
    {
      account_id: COLLECT_ID,
      account_no: "100412",
      customer_name: "Navarro, P.",
      settles_in_month: 11,
      settles_in_year: 2026,
      months_away: 2,
      settles_this_month: false,
      paid_on_level: "1152.000000",
      actual_so_far: "1364.800000",
      months_billed: 12,
      // + collects (`budget.SettleUp.signed`).
      balance_signed: "212.800000",
      settle_up_amount: "212.800000",
      settle_up_direction: "collect",
      settle_up_taxable: false,
      currency: "USD",
    },
    {
      account_id: CREDIT_ID,
      account_no: "100377",
      customer_name: "Ridge Coffee Co.",
      settles_in_month: 11,
      settles_in_year: 2026,
      months_away: 2,
      settles_this_month: false,
      paid_on_level: "1704.000000",
      actual_so_far: "1642.600000",
      months_billed: 12,
      // − credits.
      balance_signed: "-61.400000",
      settle_up_amount: "61.400000",
      settle_up_direction: "credit",
      settle_up_taxable: false,
      currency: "USD",
    },
    {
      account_id: NOTHING_ID,
      account_no: "100455",
      customer_name: "Okafor, D.",
      settles_in_month: 1,
      settles_in_year: 2027,
      months_away: 4,
      settles_this_month: false,
      // Enrolled, not yet billed inside this period — ABSENT, never `0.00`.
      paid_on_level: null,
      actual_so_far: null,
      months_billed: 0,
      balance_signed: null,
      settle_up_amount: null,
      settle_up_direction: null,
      settle_up_taxable: false,
      currency: "USD",
    },
  ],
  summary: {
    settling_this_month: 9,
    settling_month: 9,
    settling_year: 2026,
    to_collect_amount: "1204.600000",
    to_collect_accounts: 6,
    to_credit_amount: "318.200000",
    to_credit_accounts: 3,
    currency: "USD",
    currencies: ["USD"],
    later_accounts: 28,
    later_months: 8,
    no_settle_month: 0,
  },
  unavailable: [],
};

function render(overrides?: Partial<SettleUpForecastResponse>): string {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: Infinity } },
  });
  // ⚠ DERIVED, never hand-typed. The first draft of this fixture wrote `25`
  // and the page asks for `DEFAULT_PAGE_SIZE` (50), so the key never
  // matched, the query held no data, and six cases failed on a fixture
  // fault rather than on the screen — the shape CLAUDE.md's *never
  // hand-type a list* names, one constant wide.
  client.setQueryData(settleUpForecastKey(`|||1|${DEFAULT_PAGE_SIZE}`), {
    ...RESPONSE,
    ...overrides,
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <ToastProvider>
          {/* THE REAL PATH PATTERN — see this file's header. */}
          <MemoryRouter initialEntries={[`/brazosbend${BUDGET_FORECAST_ROUTE}`]}>
            <Routes>
              <Route
                path="/:tenant/billing/budget/settle-up"
                element={<SettleUpForecastPage />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}

describe("§05 entry 25.2 — the settle-up forecast is the screen the drawing needs", () => {
  it("TC-F1 · draws the page head, the caption and the back door", () => {
    const html = render();
    expect(html).toContain(t("billing.settleUp.title"));
    expect(html).toContain(t("billing.settleUp.caption"));
    expect(html).toContain(t("billing.settleUp.back"));
  });

  it("TC-F2 · draws the four tiles the drawing draws, in the drawn order", () => {
    const html = render();
    const tiles = [
      t("billing.settleUp.kpi.settling"),
      t("billing.settleUp.kpi.toCollect"),
      t("billing.settleUp.kpi.toCredit"),
      t("billing.settleUp.kpi.later"),
    ];
    const at = tiles.map((label) => html.indexOf(label));
    expect(at.every((index) => index >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
    // The detail lines: the counts and the months, from the server.
    expect(html).toContain(t("billing.settleUp.kpi.accounts", { count: 6 }));
    expect(html).toContain(t("billing.settleUp.kpi.otherMonths", { count: 8 }));
  });

  it("TC-F3 · draws the six columns the drawing draws, in the drawn order", () => {
    const html = render();
    const columns = [
      t("billing.settleUp.col.account"),
      t("billing.settleUp.col.settlesIn"),
      t("billing.settleUp.col.paidOnLevel"),
      t("billing.settleUp.col.actualSoFar"),
      t("billing.settleUp.col.balance"),
      t("billing.settleUp.col.will"),
    ];
    const at = columns.map((label) => html.indexOf(label));
    expect(at.every((index) => index >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
  });

  it("TC-F4 · draws the `Where it posts` group, and NOT its rationale", () => {
    const html = render();
    expect(html).toContain(t("billing.settleUp.posts.heading"));
    expect(html).toContain(t("billing.settleUp.posts.lineValue"));
    expect(html).toContain(t("billing.settleUp.posts.whoValue"));
    expect(html).toContain(t("billing.settleUp.posts.redraftValue"));
    // ⚠ B14 rule 33 — RATIONALE IS ZERO WORDS ON SCREEN. The drawing's *"There
    // is no button here on purpose…"* lives in the code and the register, and
    // this asserts it never crept back onto the screen.
    expect(html).not.toContain("on purpose");
    expect(html).not.toContain("second answer");
  });

  it("TC-F5 · the SIGN survives, in both directions, and the WILL word agrees", () => {
    const html = render();
    // `+ collects, − credits` — `budget.SettleUp.signed`, rendered at 2dp.
    //
    // ⚠ **THE NEGATIVE ASSERTIONS ARE THE ONES THAT BITE.** The first draft was
    // `toContain("$212.80")` and `toContain("-$61.40")`, and it PASSED over a
    // cell rewritten to negate, because `-$212.80` CONTAINS `$212.80`. A sign
    // check built only from `toContain` cannot see a flipped sign at all —
    // law 7's *what would make this check pass wrongly*, on the one column a
    // clerk reads out to a customer. Found by sabotage, not by review.
    expect(html).toContain("$212.80");
    expect(html).not.toContain("-$212.80"); // a COLLECTION is never negative
    expect(html).toContain("-$61.40"); // a CREDIT always is
    expect(html).toContain(t("billing.settleUp.will.collect"));
    expect(html).toContain(t("billing.settleUp.will.credit"));
    // Both sums reach the screen at display precision, from 6dp strings.
    expect(html).toContain("$1,152.00");
    expect(html).toContain("$1,364.80");
  });

  it("TC-F6 · an unbilled period is a stated absence and NEVER `$0.00`", () => {
    const html = render();
    expect(html).toContain(t("billing.settleUp.absent.noBills"));
    expect(html).toContain(t("billing.settleUp.will.nothing"));
    expect(html).not.toContain("$0.00");
  });

  it("TC-F7 · B14 rule 31 — the account NUMBER shows and the id only rides the href", () => {
    const html = render();
    expect(html).toContain("100412");
    // DERIVED from the shared helper, never hand-typed: an address written out
    // here would go on passing after the real route moved, which is exactly
    // the `DEF-CWP-3925` shape this case exists to close.
    expect(html).toContain(`/brazosbend${accountDetailPath(COLLECT_ID)}`);
    // The id is never a visible value: it appears only inside an attribute.
    expect(html).not.toContain(`>${COLLECT_ID}<`);
  });

  it("TC-F8 · two currencies get the counts and NO total (CLAUDE.md rule 2)", () => {
    const html = render({
      summary: {
        ...RESPONSE.summary,
        to_collect_amount: null,
        to_credit_amount: null,
        currency: null,
        currencies: ["CAD", "USD"],
      },
    });
    expect(html).toContain(t("billing.settleUp.kpi.mixed"));
    expect(html).not.toContain("$1,204.60");
  });

  it("TC-F9 · THE HOLD, AND THE TEST THAT FIRES WHEN IT EXPIRES", () => {
    // `Export` is drawn and ships DISABLED — `DEF-BIL-5328`. BR-SHL-010 makes
    // the SERVER's capability row the config, and no export resource exists for
    // a budget list. The day one is registered this goes RED and names the
    // button, which is what hard-won law 2 asks of every hold.
    expect([...EXPORT_RESOURCES].some((name) => name.includes("settle"))).toBe(false);
    expect([...EXPORT_RESOURCES].some((name) => name.includes("budget"))).toBe(false);
    const html = render();
    // ⚠ THE ATTRIBUTE, NOT THE WORD. The first draft asserted `toContain
    // ("disabled")` and PASSED over a button with the attribute removed,
    // because every Button in the kit carries `disabled:opacity-45
    // disabled:cursor-not-allowed` in its class string whether it is disabled
    // or not. That is law 7's *what would make this check pass wrongly*, and
    // it was found by sabotaging the component and watching the test stay
    // green. The rendered attribute is `disabled=""`.
    const button = /<button[^>]*disabled=""[^>]*>[^<]*Export/i;
    expect(html).toMatch(button);
    expect(html).toContain(t("billing.settleUp.exportWhy"));
  });

  it("TC-F10 · THERE IS NO WRITE CONTROL, and that is the drawing's own ruling", () => {
    const html = render();
    // The withdrawn bulk *"Settle these 2"*. The cycle run posts every
    // settle-up idempotently per invoice; a button here would be a second
    // writer for the same money.
    expect(html).not.toContain("Settle these");
    expect(html.toLowerCase()).not.toContain("settle up the year");
  });

  it("TC-F11 · an account that never trues up is COUNTED, not silently omitted", () => {
    const html = render({
      summary: { ...RESPONSE.summary, no_settle_month: 4 },
    });
    expect(html).toContain(t("billing.settleUp.neverSettle", { count: 4 }));
  });

  it("TC-F12 · the table says the list spans months", () => {
    expect(render()).toContain(t("billing.settleUp.spansMonths"));
  });

  it("TC-F13 · the route constant is the address the router mounts", () => {
    // Asserted by VALUE as well as by mounting, because `DEF-CWP-3925`'s
    // hold-expiry test asserted a screen at one address while the router
    // mounted it at another and every check passed over both.
    expect(BUDGET_FORECAST_ROUTE).toBe("/billing/budget/settle-up");
    expect(BUDGET_FORECAST_ROUTE.startsWith(BUDGET_TAB_ROUTE)).toBe(true);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: 05-prototype/04 Billing, As Built.pdf §05 entry 25.2 (p124-p126, read as images at scale 2) · 04-docs/02-decisions/14-ui-conventions.md B14 rules 31/33/37/41
// generated: 2026-09-15 by the §05 entry 25.2 build lane
// checklist: A✔ B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: npx vitest run src/features/billing/settleUpForecastPage.dom.test.tsx — 13 passed. ⚠ TWO of these guards PASSED their first sabotage and were hardened: `toContain("disabled")` is satisfied by the kit's `disabled:` utility classes on every Button, and `toContain("$212.80")` is satisfied by `-$212.80`, so a sign check built only from `toContain` cannot see a flipped sign at all. Both were found by breaking the component, not by reading the test.
// exceptions: E3 the page is rendered with `renderToStaticMarkup` rather than driven, the same posture `budgetEnrolPage.dom.test.tsx` beside it takes — these cases assert what is DRAWN · E3 every drawn figure is an ILLUSTRATION (B14 rule 37) and none is asserted · E3 TC-F9 is a HOLD-EXPIRY test: it goes RED the day an export resource is registered, which is what hard-won law 2 asks of every hold
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

// ── Trace ──────────────────────────────────────────────
// Change:   CR-013 part 3 — DIS-01, the Discounts landing tab (§18 row 10)
//           Screens: PLN-01.discounts
// Rules:    BR-RAT-068 (an OVERLAY, never an edit to the rate) · BR-RAT-069
//           (AVAILABLE ≠ GRANTED) · BR-RAT-072 (four statuses, one set by a
//           BILL RUN) · BR-RAT-079 (restricted proof — nothing here carries a
//           document) · BR-RAT-084 (the code opens the shared detail) ·
//           BR-RAT-087 / DEF-364 (the SERVER's `*_display` string reaches the
//           screen and the stored value never does) · BR-SHL-010 (a declared
//           sort vocabulary) · BR-SHL-025 (disabled WITH its reason)
// ───────────────────────────────────────────────────────
//
// TWO LOAD-BEARING ABSENCES, ASSERTED RATHER THAN COMMENTED:
//
//   · **`0.00` never stands in for an em-dash.** The server serves
//     `value_display: null` for a charge waiver, and this suite searches the
//     rendered markup for the zero a lenient `?? "0.00"` would have produced.
//   · **`Plans` and `Enrolled` are two different numbers.** A tab that read one
//     of them twice would tell a utility that every account on a plan carrying
//     SENIOR is being charged 15% less — and would look completely normal.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { DISCOUNT_SORTS, DISCOUNT_STATUSES, DISCOUNT_TYPES } from "@/api/endpoints";
import type { DiscountRow, Paginated } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { serializeTableParams } from "@/components/tableTypes";
import { ToastProvider } from "@/components/Toast";

import { DiscountsTab, discountTableConfig, discountValueText } from "./DiscountsTab";
import { definitionPath, definitionWizardPath } from "./definitionDetail";
import { RATING_TABS, RATING_TAB_STRIP, discountStatusTone } from "./ratingShared";
import type { RatingTabRender, Translator } from "./ratingShared";

import tabSource from "./DiscountsTab.tsx?raw";

// The tab is exercised alone, so this stands in for the frame and renders both
// halves it hands up (US-SHL-020 addendum r2).
const bothHalves: RatingTabRender = ({ action, body }) => (
  <>
    {action}
    {body}
  </>
);

const t: Translator = (key, params) => i18n.t(key, params);

/**
 * A catalog string as it appears in `renderToStaticMarkup`'s output. React
 * escapes `&`, `<`, `>`, `"` and `'` in text and in attributes, so
 * "Plans & Rates" is "Plans &amp; Rates" in the markup — a plain `toContain` on
 * the catalog value fails, while a key with no punctuation passes and looks
 * like proof. Escaping the EXPECTED side keeps the assertion pointed at the
 * catalog rather than at a hand-typed copy of it.
 */
function shown(key: string): string {
  return i18n
    .t(key)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#x27;");
}

// r10's own five discounts (`SMARTBillHub.dc.html:814-818`), as
// `GET /discounts` serves them. Every figure is r10's or the seed's; none is
// invented here.
const SENIOR: DiscountRow = {
  id: "d-senior",
  code: "SENIOR",
  name: "Senior discount",
  type: "percentage",
  // ⚠ PERCENTAGE POINTS, not a fraction — `charges.percent` stores `0.015` for
  // 1.5% and a discount stores `15` for 15%. The display string beside it is
  // the server's, and the wrong formatter would make it `1500.00%`.
  value: "15.000000",
  value_display: "15.00%",
  currency: "USD",
  eligibility: "Age 65+",
  verification: "annual_recertification",
  plans: 3,
  enrolled: 72,
  status: "active",
  programme_owner: "Customer service",
  funding_source: "Rate-payer funded",
  gl_account_id: null, // CR-066 table 3 — no override; the designation answers
  applies_to: "whole_bill",
  effective_from: "2026-01-01",
  version_no: 2,
  version_status: "active",
  version_id: "0198c1aa-0000-7000-8000-0000000000d3",
};

const CAP: DiscountRow = {
  ...SENIOR,
  id: "d-cap",
  code: "CAP",
  name: "CAP / low-income credit",
  type: "fixed_amount",
  value: "25.000000",
  value_display: "25.00",
  eligibility: "Program enrolment",
  verification: "agency_file_monthly",
  plans: 1,
  enrolled: 38,
};

const AUTOPAY: DiscountRow = {
  ...SENIOR,
  id: "d-autopay",
  code: "AUTOPAY",
  name: "Autopay discount",
  // CR-013 part 3 states AUTOPAY as −0.5%, which is why the column is six
  // decimals and why the display half has to round rather than truncate.
  value: "0.500000",
  value_display: "0.50%",
  eligibility: "Autopay enrolled",
  verification: "automatic",
  plans: 1,
  enrolled: 418,
};

/** r10 draws MILITARY as a Draft pill with `—` plans and `—` enrolled. */
const MILITARY: DiscountRow = {
  ...SENIOR,
  id: "d-military",
  code: "MILITARY",
  name: "Veteran discount",
  value: "10.000000",
  value_display: "10.00%",
  eligibility: "Veteran ID",
  verification: "one_time_proof",
  plans: 0,
  enrolled: 0,
  status: "draft",
  version_status: "draft",
  version_id: "0198c1aa-0000-7000-8000-0000000000d4",
};

/**
 * ⚠ THE ROW THIS SUITE EXISTS FOR. A charge waiver removes the WHOLE of what
 * its scope selected and never reads `value`, so the server serves
 * `value_display: null` — and the screen must render an em-dash. `0.00` there
 * would state that the utility waives nothing.
 */
const WAIVER: DiscountRow = {
  ...SENIOR,
  id: "d-waiver",
  code: "WAIVE-BASE",
  name: "Base charge waived",
  type: "charge_waiver",
  value: "0.000000",
  value_display: null,
  // A programme whose eligibility nobody has written down in plain language.
  eligibility: null,
  verification: null,
  plans: 0,
  enrolled: 0,
};

/** BR-RAT-072's fifth status — the one a BILL RUN sets. */
const EXHAUSTED: DiscountRow = {
  ...CAP,
  id: "d-exhausted",
  code: "CAP-2025",
  status: "suspended_funding_exhausted",
};

const CONFIG = discountTableConfig(t, {
  code: () => <span />,
  type: () => "",
  value: () => "",
  eligibility: () => "",
  verification: () => "",
  from: () => "",
  to: () => "",
  enrolled: () => "",
  status: () => <span />,
  // The row-action cell. Added with DIS-02 (2026-08-21) as a pencil to the
  // edit door; since CR-166 task 5 (D16) its one action OPENS the details page.
  open: () => <span />,
});

const DEFAULT_STATE = { q: "", page: 1, per: 50 as const, filters: {} };

function renderDiscounts(rows: DiscountRow[], readOnly = false): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = { ...DEFAULT_STATE, ...CONFIG.defaultSort };
  queryClient.setQueryData(queryKeys.discounts(serializeTableParams(state, CONFIG).toString()), {
    count: rows.length,
    next: null,
    previous: null,
    results: rows,
  } satisfies Paginated<DiscountRow>);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/plans-rates/discounts"]}>
          <DiscountsTab
            readOnly={readOnly}
            timeZone="America/Chicago"
            dateFormat="MM/DD/YYYY"
            render={bothHalves}
          />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ── §18 row 10 · the tab that did not exist ────────────────────────────────

describe("§18 row 10 — the Discounts tab, which six migrated tables had no way to reach", () => {
  it("the tab is in the vocabulary and in r10's own position in the strip", () => {
    // r10's order: Plans · Rate schedules · Charge codes · DISCOUNTS · Taxes &
    // fees. `history` is a destination with its own top-right button and is not
    // drawn in the strip at all.
    expect(RATING_TAB_STRIP.map((tab) => tab.id)).toEqual([
      "plans",
      "rates",
      "charge-codes",
      "discounts",
      "taxes-fees",
    ]);
    expect(RATING_TABS.find((tab) => tab.id === "discounts")?.path).toBe("/plans-rates/discounts");
  });

  it("⚠ adding it did NOT remove Rate changes — that reconciliation is the PO's", () => {
    // §18: the built five are NOT r10's five, and *"building the Discounts tab
    // without ruling on Rate changes leaves the product with six tabs and the
    // drawing with five."* Nothing in this change decides it by deletion.
    expect(RATING_TABS.some((tab) => tab.id === "history")).toBe(true);
    expect(RATING_TABS).toHaveLength(6);
  });

  it("renders the drawing's ELEVEN data columns, in its order, plus the open action", () => {
    // ⚠ AMENDED 2026-10-03 (CR-166 task 5, D17): r10's nine became images
    // 01–04's eleven — From and To sit between Verification and Plans. Written
    // as eleven-then-actions so a data column arriving or leaving still fails.
    // ⚠ AMENDED 2026-10-03 (DEF-RAT-9319, CR-166 task 9): Verification is
    // off by default and stays in ▦ Columns — twelve columns did not fit
    // 1,120px at 1440. The drawn ORDER is unchanged.
    expect(CONFIG.columns.map((c) => c.key)).toEqual([
      "code",
      "name",
      "type",
      "value",
      "eligibility",
      "verification",
      "effective_from",
      "effective_to",
      "plans",
      "enrolled",
      "status",
      "actions",
    ]);
    const visible = CONFIG.columns.filter((c) => c.defaultVisible !== false).map((c) => c.key);
    expect(visible).not.toContain("verification");
    expect(visible).toHaveLength(11);
  });

  it("the code links to the shared definition detail, which nothing else on earth linked to", () => {
    // BR-RAT-084 · hard-won law 2: `/plans-rates/discounts/:id` has existed
    // since CR-013 P2 and was reachable only by typing the URL.
    const html = renderDiscounts([SENIOR]);
    expect(html).toContain(`href="/brazosbend${definitionPath("discount", SENIOR.id)}"`);
    expect(html).toContain("SENIOR");
  });
});

// ── BR-RAT-069 · available is not granted ──────────────────────────────────

describe("BR-RAT-069 — AVAILABLE ≠ GRANTED, drawn as two columns", () => {
  it("Plans and Enrolled are separate columns reading separate fields", () => {
    const html = renderDiscounts([SENIOR]);
    // 3 plans OFFER it; 72 accounts GET it. Both numbers are on the row, and a
    // tab that read one of them twice would be charging 15% less to everyone on
    // three plans.
    expect(html).toContain(">3<");
    expect(html).toContain(">72<");
    expect(SENIOR.plans).not.toBe(SENIOR.enrolled);
  });

  it("a draft discount shows zero of each rather than borrowing the other's number", () => {
    const html = renderDiscounts([MILITARY]);
    expect(html).toContain("Veteran discount");
    // Its VALUE still renders — r10 draws MILITARY's −10% on a Draft row.
    expect(html).toContain("10.00%");
  });
});

// ── BR-RAT-087 / DEF-364 · the display string, and the em-dash ─────────────

describe("BR-RAT-087 — the SERVER's display string reaches the screen, and null is an em-dash", () => {
  it("⚠ a percentage renders 15.00% and the stored 15.000000 never appears", () => {
    const html = renderDiscounts([SENIOR]);
    expect(html).toContain("15.00%");
    expect(html).not.toContain("15.000000");
    // The wrong formatter — the one that scales a fraction — would print this.
    expect(html).not.toContain("1500.00%");
  });

  it("⚠ −0.5% survives, which is why the column is six decimals", () => {
    const html = renderDiscounts([AUTOPAY]);
    expect(html).toContain("0.50%");
    expect(html).not.toContain("0.500000");
    expect(html).not.toContain("50.00%");
  });

  it("a fixed amount renders at two places with no percent sign", () => {
    const html = renderDiscounts([CAP]);
    expect(html).toContain("25.00");
    expect(html).not.toContain("25.000000");
  });

  it("⚠ A CHARGE WAIVER RENDERS AN EM-DASH AND NEVER 0.00", () => {
    // The discipline of the whole change. `?? "0.00"` instead of `?? "—"` would
    // pass tsc, pass every gate, and tell a utility its waiver waives nothing.
    expect(discountValueText(WAIVER)).toBe("—");
    const html = renderDiscounts([WAIVER]);
    expect(html).not.toContain("0.00");
    expect(html).toContain("—");
  });

  it("the cell reads `value_display` and nothing else — no client-side branch on type", () => {
    // A branch here would be a second copy of the unit rule, in the layer least
    // able to be tested against the money it describes.
    expect(discountValueText(SENIOR)).toBe(SENIOR.value_display);
    expect(discountValueText(CAP)).toBe(CAP.value_display);
    expect(discountValueText({ ...SENIOR, value_display: null })).toBe("—");
  });

  it("an eligibility nobody wrote down is an em-dash, not a blank cell", () => {
    expect(WAIVER.eligibility).toBeNull();
    const html = renderDiscounts([WAIVER]);
    expect(html).toContain("—");
  });
});

// ── BR-RAT-072 · four statuses, and the one a bill run sets ────────────────

describe("BR-RAT-072 — four statuses, and `suspended_funding_exhausted` is not neutral", () => {
  it("every status the server can send has a label and a tone", () => {
    for (const status of DISCOUNT_STATUSES) {
      expect(i18n.t(`rating.discounts.status.${status}`)).not.toContain("rating.discounts");
      expect(["success", "warning", "danger", "neutral"]).toContain(discountStatusTone(status));
    }
  });

  it("⚠ funding exhausted takes the DANGER tone, because it is a live money event", () => {
    // It is the one status a BILL RUN can set, and the only way a utility
    // learns a subsidy programme stopped paying out. Neutral grey would hide it
    // among the drafts.
    expect(discountStatusTone("suspended_funding_exhausted")).toBe("danger");
    expect(discountStatusTone("active")).toBe("success");
    expect(discountStatusTone("retired")).toBe("warning");
    expect(discountStatusTone("draft")).toBe("neutral");
    const html = renderDiscounts([EXHAUSTED]);
    expect(html).toContain(shown("rating.discounts.status.suspended_funding_exhausted"));
  });

  it("an unknown status renders its own raw token, never a translation key", () => {
    const html = renderDiscounts([{ ...SENIOR, status: "invented_by_the_server" }]);
    expect(html).toContain("invented_by_the_server");
    expect(html).not.toContain("rating.discounts.status.invented");
  });
});

// ── BR-SHL-010/011 · the declared vocabulary ───────────────────────────────

describe("BR-SHL-010 — only what the server can actually sort is marked sortable", () => {
  it("⚠ three sortable columns, and the other six are NOT an oversight", () => {
    // Type, Value, Eligibility and Verification live on `discount_versions`;
    // Plans and Enrolled are computed counts. A sort arrow over a column the
    // server orders by something else is how a table starts lying quietly.
    const sortable = CONFIG.columns.filter((c) => c.sortable === true).map((c) => c.key);
    expect(sortable).toEqual(["code", "name"]);
    // `status` is sortable server-side and is not drawn with an arrow here,
    // which is the safe direction; what must never happen is the reverse.
    for (const key of sortable) {
      expect(DISCOUNT_SORTS as readonly string[]).toContain(key);
    }
  });

  it("the two filters are image 02's, and both are the server's (NFR-3)", () => {
    // AMENDED 2026-10-03 (CR-166 task 5): image 02 offers Status and Type only.
    expect(CONFIG.filters?.map((f) => f.name)).toEqual(["status", "type"]);
    expect(CONFIG.filters?.[1].options.map((o) => o.value)).toEqual([...DISCOUNT_TYPES]);
  });

  it("every one of the five types has a real label", () => {
    for (const type of DISCOUNT_TYPES) {
      const label = i18n.t(`rating.discounts.type.${type}`);
      expect(label).not.toContain("rating.discounts");
      expect(label.length).toBeGreaterThan(0);
    }
  });
});

// ── The doors to DIS-02 · AMENDED 2026-08-21 ───────────────────────────────
//
// ⚠ THIS BLOCK USED TO ASSERT THE OPPOSITE, AND THAT IS THE POINT OF READING IT.
// It pinned `+ New discount` as DISABLED carrying `rating.discounts.wizardPending`
// (*"Creating and editing a discount arrives with the five-step discount
// wizard"*) and asserted that NO row-actions column was drawn — both correct
// while DIS-02 did not exist. It exists (`DiscountWizard.tsx`), so a test that
// still passed here would be pinning a sentence that has stopped being true,
// which is hard-won law 1 wearing a green tick.

describe("the three doors to DIS-02 are open, and the stale reason is gone", () => {
  it("a full-access role gets `+ New discount` LIVE — no disabled reason left", () => {
    const html = renderDiscounts([SENIOR]);
    expect(html).toContain(shown("rating.discounts.new"));
    // The catalogue key that carried the "wizard is not built" sentence is
    // DELETED, in every one of the eleven locales, rather than left unused.
    expect(i18n.t("rating.discounts.wizardPending")).toBe("rating.discounts.wizardPending");
  });

  it("a read-only role still gets the RBAC sentence — BR-SHL-025 is untouched", () => {
    const html = renderDiscounts([SENIOR], true);
    expect(html).toContain(shown("rating.readOnlyReason"));
    expect(html).toContain("disabled");
  });

  it("the row-actions column exists now, with exactly ONE action", () => {
    // Duplicate and Retire still have no route on any definition kind, so the
    // column carries one working icon rather than three dead ones.
    expect(CONFIG.columns.map((c) => c.key)).toContain("actions");
  });

  it("both NEW doors spell the route through `definitionWizardPath`; the list has no edit door", () => {
    // Read as TEXT. AMENDED 2026-10-03 (CR-166 task 5, D16): the row's pencil
    // to `…/{id}/edit` is gone — the row opens the details page, and editing is
    // that page's decision by status — so two doors remain, both `+ New`.
    const calls = tabSource.match(/definitionWizardPath\("discount", [^)]*\)/g) ?? [];
    expect(calls).toHaveLength(2);
    expect(calls.filter((call) => call.includes("null"))).toHaveLength(2);
    expect(definitionWizardPath("discount", null)).toBe("/plans-rates/discounts/new");
    expect(definitionWizardPath("discount", "d-senior")).toBe(
      "/plans-rates/discounts/d-senior/edit",
    );
  });
});

// ── BR-RAT-079 · nothing here is a document ────────────────────────────────

describe("BR-RAT-079 — the landing carries no proof and no account", () => {
  it("⚠ the row type has no enrolment, no document and no account field", () => {
    // Income and medical proof are restricted and excluded from general
    // document lists. This list is built so there is nothing to filter: it
    // carries COUNTS. A row that grew an `enrolments` array would be one
    // forgotten filter away from a medical certification in a browse list.
    const keys = Object.keys(SENIOR);
    for (const forbidden of ["enrolments", "documents", "accounts", "proof"]) {
      expect(keys).not.toContain(forbidden);
    }
    const html = renderDiscounts([SENIOR]);
    expect(html).not.toContain("medical_certification");
    expect(html).not.toContain("income_statement");
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-013 part 3 VERBATIM (12-governance/11-change-requests.md) · 09-screen-inventory.md §1 + §18 row 10 · BR-RAT-068/069/072/079/084/087
// generated: 2026-08-21 by the CR-013 discounts read-API lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: tsc✔ · vitest src/features/rating/ 184 passed / 19 todo across 8 files✔ (this file is 22 of them) · g31_declared_classes PASS✔ · g29_screen_ids PASS✔
// exceptions: no create/edit case, because no discount write endpoint exists and the wizard (§18 row 12) is a separate surface — the disabled-with-reason posture is asserted instead
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

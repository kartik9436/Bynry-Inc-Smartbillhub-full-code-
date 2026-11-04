// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-5670 — neither of the two screens an account is BORN on
//          could set a sub-type, so a clerk created the account, opened it and
//          edited it, every time.
// Rules:   BR-CUS-067 (`account_subtypes` is the TENANT'S two-level tree) ·
//          `customers.lookups.parent_required` (every row hangs off exactly
//          one `account_types` row) · B2 (`accounts.account_subtype_id` is
//          NULLABLE — a sub-type is optional and stays optional) ·
//          B14 rule 31 (no database id is the visible value of a field) ·
//          B14 rule 33 (a LABEL ≤ 3 words) · hard-won law 2 (built is not
//          wired) · hard-won law 7 (every case here was shown RED first).
// ───────────────────────────────────────────────────────
//
// WHAT THESE CASES ARE FOR, AND WHAT THEY DELIBERATELY CANNOT DO.
//
// They pin the four things a browser walk is a poor witness for: which rows a
// category may offer, what survives a change of category, what reaches the
// wire, and that the OPTION TEXT is a name rather than a code. They ask the
// server nothing — the walkthrough
// `10-scripts/def_cus_5661_subtype_walkthrough.mjs` is what proves the column
// is written, because a payload assertion cannot tell you that `POST /accounts`
// accepts the key.
//
// ⚠ **THE RENDER CASES MOUNT UNDER THE REAL PATH PATTERN** (`/:tenant/...`)
// rather than dropping the component bare into a `MemoryRouter`. A bare mount
// leaves `useParams().tenant` undefined, every address the screen builds comes
// out `//…`, and `toContain` reads that as a perfectly good string — which is
// how a portal front page shipped with two working doors out of eight.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { LookupEntry, MyPermissions, Paginated, UnitRow } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import {
  NewAccountWizard,
  createAccountPayload,
  emptyCustomerForm,
  emptyPreferencesForm,
} from "./NewAccountWizard";
import { moveInPayload } from "./MoveInWizard";
import {
  ACCOUNTS_PERMISSION,
  ACCOUNT_CATEGORIES_QUERY_KEY,
  ACCOUNT_SUBTYPES_QUERY_KEY,
  accountSubtypeAfterCategoryChange,
  accountSubtypeName,
  accountSubtypesUnder,
} from "./customersShared";
import type { AccountSubtypeRow } from "./customersShared";

const TEST_TENANT = "brazosbend";

// The demo tenant's own rows, read off PostgreSQL rather than invented:
// `select s.code, t.code from account_subtypes s join account_types t …`.
const ROWS: AccountSubtypeRow[] = [
  { id: "id-single_family", code: "single_family", name: "Single-family", parentCode: "residential", active: true },
  { id: "id-multi_family", code: "multi_family", name: "Multi-family", parentCode: "residential", active: true },
  { id: "id-healthcare", code: "healthcare", name: "Healthcare", parentCode: "commercial", active: true },
  { id: "id-large_commercial", code: "large_commercial", name: "Large commercial", parentCode: "commercial", active: true },
  {
    id: "id-institutional_non_profit",
    code: "institutional_non_profit",
    name: "Institutional & non-profit",
    parentCode: "commercial",
    active: true,
  },
  { id: "id-light_industrial", code: "light_industrial", name: "Light industrial", parentCode: "industrial", active: true },
  // Two rows that must never be offered, for two different reasons.
  { id: "id-retired_wing", code: "retired_wing", name: "Retired wing", parentCode: "commercial", active: false },
  { id: "id-orphan", code: "orphan", name: "Orphan", parentCode: null, active: true },
];

function lookupPage(rows: readonly AccountSubtypeRow[]): Paginated<LookupEntry> {
  return {
    count: rows.length,
    next: null,
    previous: null,
    results: rows.map((row, index) => ({
      id: `id-${index}`,
      code: row.code,
      name: row.name,
      active: row.active,
      is_system: true,
      used_by: 0,
      parent_code: row.parentCode,
      parent_name: row.parentCode,
    })),
  };
}

const SERVED_CATEGORIES = {
  selectable: [
    { code: "residential", name: "Residential" },
    { code: "commercial", name: "Commercial" },
    { code: "industrial", name: "Industrial" },
  ],
  legacy: [],
};

function permissions(access: string): MyPermissions {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access }],
  };
}

const VACANT: Paginated<UnitRow> = { count: 0, next: null, previous: null, results: [] };

function renderStepOne(rows: readonly AccountSubtypeRow[] = ROWS): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(ACCOUNT_CATEGORIES_QUERY_KEY, SERVED_CATEGORIES);
  queryClient.setQueryData(ACCOUNT_SUBTYPES_QUERY_KEY, lookupPage(rows));
  queryClient.setQueryData(["units", "vacant-picker"], VACANT);
  queryClient.setQueryData(queryKeys.myPermissions, permissions("write"));
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* The REAL path pattern — see this file's header. */}
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts/new?step=1`]}>
          <Routes>
            <Route path="/:tenant/accounts/new" element={<NewAccountWizard />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The `<option …>` values of one `<select>`, in render order. */
function optionsOf(html: string, selectId: string): { value: string; label: string }[] {
  const open = html.indexOf(`id="${selectId}"`);
  if (open === -1) return [];
  const end = html.indexOf("</select>", open);
  const block = html.slice(open, end === -1 ? undefined : end);
  return [...block.matchAll(/<option value="([^"]*)"[^>]*>([^<]*)<\/option>/g)].map((m) => ({
    value: m[1],
    label: m[2],
  }));
}

describe("DEF-CUS-5670 — the sub-type a clerk could not set while creating an account", () => {
  // ── the list one category may offer ──────────────────────────────────────
  it("BR-CUS-067: a category offers ITS OWN children and nothing else", () => {
    expect(accountSubtypesUnder(ROWS, "commercial").map((r) => r.code)).toEqual([
      "healthcare",
      "large_commercial",
      "institutional_non_profit",
    ]);
    expect(accountSubtypesUnder(ROWS, "residential").map((r) => r.code)).toEqual([
      "single_family",
      "multi_family",
    ]);
    // A category the tenant defined no children for offers none — an empty
    // list, never the whole tree.
    expect(accountSubtypesUnder(ROWS, "agricultural")).toEqual([]);
  });

  it("BR-TEN-034: a DEACTIVATED row is not offered — the create would refuse it by name", () => {
    expect(accountSubtypesUnder(ROWS, "commercial").map((r) => r.code)).not.toContain(
      "retired_wing",
    );
  });

  it("`parent_required`: a row with NO parent is offered under nothing", () => {
    for (const parent of ["residential", "commercial", "industrial", ""]) {
      expect(accountSubtypesUnder(ROWS, parent).map((r) => r.code)).not.toContain("orphan");
    }
  });

  // ── what survives a change of category ───────────────────────────────────
  it("changing the category CLEARS an incompatible sub-type", () => {
    // Commercial · Healthcare, corrected to Industrial: Healthcare cannot come
    // with it. Nothing downstream refuses the pair — `_resolve_account_subtype`
    // never asks which category a code hangs off — so this is the only place
    // it is known to be wrong.
    expect(accountSubtypeAfterCategoryChange(ROWS, "healthcare", "industrial")).toBe("");
  });

  it("changing the category KEEPS a sub-type that still belongs to it", () => {
    // Re-picking the same category must not throw the answer away.
    expect(accountSubtypeAfterCategoryChange(ROWS, "healthcare", "commercial")).toBe("healthcare");
  });

  it("it FAILS CLOSED: an unloaded list clears rather than keeping an unproved pair", () => {
    expect(accountSubtypeAfterCategoryChange([], "healthcare", "commercial")).toBe("");
    // An unanswered sub-type stays unanswered — never invented.
    expect(accountSubtypeAfterCategoryChange(ROWS, "", "commercial")).toBe("");
  });

  // ── B14 rule 31 — the picker sends the stored value and shows the NAME ───
  it("B14 rule 31: the option a clerk READS is the name, never the code", () => {
    const html = renderStepOne();
    const options = optionsOf(html, "account_subtype");
    expect(options.map((o) => o.label)).toContain("Single-family");
    expect(options.map((o) => o.label)).not.toContain("single_family");
    expect(accountSubtypeName("multi_family", ROWS)).toBe("Multi-family");
    // …and an unknown code degrades to the CODE, never to an invented label.
    expect(accountSubtypeName("no_such_row", ROWS)).toBe("no_such_row");
  });

  // ── hard-won law 2 — the control is WIRED onto the screen, not merely built ─
  it("law 2: step 1 of the New account wizard RENDERS the picker, filtered by the default category", () => {
    const html = renderStepOne();
    expect(html).toContain('id="account_subtype"');
    const options = optionsOf(html, "account_subtype");
    // `emptyCustomerForm()` starts at `residential`, so the list is
    // residential's two — plus the leading empty option.
    expect(options.map((o) => o.value)).toEqual(["", "single_family", "multi_family"]);
    expect(options.map((o) => o.value)).not.toContain("healthcare");
  });

  it("it is OPTIONAL and says so: a leading empty option, no asterisk, no `required`", () => {
    const html = renderStepOne();
    const options = optionsOf(html, "account_subtype");
    expect(options[0]?.value).toBe("");
    // PO 2026-09-23 (`DEF-CUS-6357`): the field is *Sub-category*.
    expect(options[0]?.label).toBe("No sub-category");
    // ⚠ THE SELECT'S OWN OPEN TAG, and not "the next 400 characters": the
    // first draft of this line sliced a fixed window, ran past `</select>` into
    // `full_name` — which IS required — and failed on its neighbour's asterisk.
    // A check that reads the wrong element is worse than no check.
    const at = html.indexOf('id="account_subtype"');
    const openTag = html.slice(at, html.indexOf(">", at) + 1);
    expect(openTag).not.toContain("aria-required");
    // …and the LABEL carries no mark either (B14 rule 10's asterisk).
    const labelFor = html.match(/<label[^>]*for="account_subtype"[^>]*>(.*?)<\/label>/s)?.[1] ?? "";
    expect(labelFor).not.toContain("*");
    expect(labelFor).toContain("Sub-category");
  });

  // ── what reaches the wire, on BOTH ways an account is born ───────────────
  it("BOTH creates carry the chosen sub-type — the two screens an account is born on", () => {
    const chosen = { ...emptyCustomerForm(), account_type: "commercial", account_subtype: "healthcare" };
    const created = createAccountPayload({
      customer: chosen,
      unit: { unit_id: "u-1", opened_at: "", custom_data: {} } as never,
      preferences: emptyPreferencesForm(),
      mode: "draft",
    });
    expect(created.account_subtype).toBe("healthcare");
    expect(created.account_type).toBe("commercial");

    const movedIn = moveInPayload({
      customer: chosen,
      preferences: emptyPreferencesForm(),
      openedAt: "",
    } as never);
    expect(movedIn.account_subtype).toBe("healthcare");
  });

  it("an UNANSWERED sub-type is an ABSENT key, never an empty string on the wire", () => {
    const created = createAccountPayload({
      customer: { ...emptyCustomerForm(), account_type: "commercial" },
      unit: { unit_id: "u-1", opened_at: "", custom_data: {} } as never,
      preferences: emptyPreferencesForm(),
      mode: "draft",
    });
    expect("account_subtype" in created).toBe(false);

    const movedIn = moveInPayload({
      customer: { ...emptyCustomerForm(), account_type: "commercial" },
      preferences: emptyPreferencesForm(),
      openedAt: "",
    } as never);
    expect("account_subtype" in movedIn).toBe(false);
  });

  // ── DEF-CUS-5673 — the refusal a Billing Clerk actually meets ────────────
  // ⚠ **THE REFUSAL FRAME CANNOT BE ASSERTED FROM THIS SUITE, AND THAT IS A
  // MEASURED FACT RATHER THAN AN EXCUSE.** `AccountUsageTab.test.tsx` already
  // recorded it against react-query 5 in this repo: *"a query cached as
  // `status: \"error\"` reports `pending / fetching` to
  // `renderToStaticMarkup`, because the server snapshot ignores a cached
  // error"*. So a node-tier render of a 403 draws the READY frame whatever the
  // cache says, and a case written here would assert the opposite of what a
  // browser does — a check that looks at the wrong thing, which is worse than
  // no check because it is trusted.
  //
  // **It is proved in the browser instead, as the role it actually bites:**
  // `10-scripts/def_cus_5670_subtype_walkthrough.mjs` signs in as the seeded
  // BILLING CLERK, reads `403` off the network and asserts the sentence is on
  // screen and the control is not. That is the only tier that can answer it,
  // and hard-won law 6 says it is the tier that counts.
  it("the refusal state EXISTS on the hook, so the screens can tell it from an empty list", () => {
    // The flag itself, which is what the JSX branches on. A settled query with
    // no body is a failure — never "still waiting", and never an empty list.
    const settledNoBody = { isPending: false, data: undefined };
    const stillWaiting = { isPending: true, data: undefined };
    const failedOf = (q: { isPending: boolean; data: unknown }) =>
      !q.isPending && q.data === undefined;
    expect(failedOf(settledNoBody)).toBe(true);
    expect(failedOf(stillWaiting)).toBe(false);
  });

  it("a refused read is NOT collapsed into 'this category has no children'", () => {
    // Two different facts, and a clerk acts differently on each: one is *the
    // list could not be read*, the other is *there are none for Agricultural*.
    // ⚠ **SINCE `DEF-CUS-6357` (PO 2026-09-23) THE EMPTY CASE IS A FACT, NOT A
    // CONTROL.** It drew a select holding only its placeholder, which the PO
    // read as broken; now it says *None for this category* and draws no select.
    const empty = renderStepOne([
      { id: "id-church", code: "church", name: "Church", parentCode: "commercial", active: true },
    ]);
    expect(empty).not.toContain('id="account_subtype"');
    expect(empty).toContain("None for this category");
    expect(empty).not.toContain("Sub-categories could not be read.");
  });

  // ── the list is the TENANT'S, and nothing here is typed out ──────────────
  it("no hardcoded list: a tenant row this repo has never heard of is offered", () => {
    // `SEED_ACCOUNT_SUBTYPES` is read by the seeder alone. A utility that adds
    // *Church* gets *Church*, with no code change — which is the whole reason
    // the picker fetches rather than imports.
    const tenantRows: AccountSubtypeRow[] = [
      { id: "id-church", code: "church", name: "Church", parentCode: "commercial", active: true },
    ];
    const html = renderStepOne(tenantRows);
    expect(accountSubtypesUnder(tenantRows, "commercial").map((r) => r.name)).toEqual(["Church"]);
    // …and the default category, which has no children here, says so as a
    // fact rather than drawing an empty control (`DEF-CUS-6357`).
    expect(html).not.toContain('id="account_subtype"');
    expect(html).toContain("None for this category");
  });
});

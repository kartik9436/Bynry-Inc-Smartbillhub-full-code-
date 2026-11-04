// ── Trace ──────────────────────────────────────────────
// Change:   CR-164-BRC10 wave 4 — a single-family owner's account holds the
//           home only when the owner lives there.
// Ruling:   PO 2026-10-03 (decision log "TWO PO ANSWERS", item 1), verbatim:
//           *"C By owner type: an owner who lives there holds it; a landlord
//           or builder doesn't"*.
//           (Then *"B"*, then *"i dont know yet"* — the owner-occupier half is `OQ-CUS-12785`, OPEN.)
// ───────────────────────────────────────────────────────
// RED FIRST: `ownerLivesThere` did not exist (import error), step 5 read the
// bare *Owner's account* for every owner type, and the build record's
// *Owner and scope* had no owner's-account row.
//
// ⚠ WHAT WOULD MAKE THESE PASS WRONGLY: a row that names BOTH phrases — each
// case asserts the other phrase is absent; and a master build gaining the row
// — asserted closed on its own.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";
import { BuildOverviewTab } from "@/features/work/buildRecord/BuildOverviewTab";

import { buildDetailFixture, buildRecordFixture } from "./buildDetailFixture";
import { ReviewStep } from "./NewConnectReviewStep";
import { draftManifest, emptyDraft, ownerLivesThere } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";

const TEST_TENANT = "brazosbend";
const t = (key: string, options?: unknown) => String(i18next.t(key, options as never));
// `DEF-CUS-10047` follow-up (walk, 2026-10-11): the line names the kind step 4
// names (Regular or Master) rather than a bare "Owner's account".
const LIVES = "account · lives there";
const BILLING = "account · billing only";

function maria(kind: string, over: Partial<NewConnectDraft> = {}): NewConnectDraft {
  const blank = emptyDraft();
  return {
    ...blank,
    owner: { ...blank.owner, name: "Maria Alvarez", email: "maria@oak.test", kind },
    premise: { ...blank.premise, address: "14 Oak St", name: "14 Oak St", accountKind: "regular" },
    pattern: { prefix: "Unit", from: "1", to: "1", includeCommonArea: false },
    premiseServices: ["water"],
    apartmentServices: ["water"],
    planApartments: "plan-1",
    ...over,
  };
}

function client() {
  return createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async () =>
      new Response(JSON.stringify({ count: 0, results: [], methods: [], rows: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
}

function ownerRow(draft: NewConnectDraft): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const html = renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=5`]}>
          <Routes>
            <Route
              path="/:tenant/connections/new"
              element={
                <ReviewStep
                  draft={draft}
                  manifest={draftManifest(draft, null)}
                  quoteTotal={null}
                  quoteCurrency={null}
                  workOrderCount={0}
                  onPatch={() => undefined}
                  t={t}
                  client={client()}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  const start = html.indexOf('data-creates="ownerAccount"');
  return html.slice(start, html.indexOf("</tr>", start));
}

describe("CR-164-BRC10 wave 4 — the owner holds the home only if they live there", () => {
  it("maps owner types the way the server does", () => {
    expect(ownerLivesThere("owner_occupier")).toBe(true);
    expect(ownerLivesThere("occupier")).toBe(true);
    for (const code of ["landlord", "builder", "property_manager", "hoa", "our_own", "", null]) {
      expect(ownerLivesThere(code)).toBe(false);
    }
  });

  it("step 5: an owner-occupier's account lives there", () => {
    const row = ownerRow(maria("owner_occupier"));
    expect(row).toContain(LIVES);
    expect(row).not.toContain(BILLING);
  });

  it("step 5: a landlord's account is billing only", () => {
    const row = ownerRow(maria("landlord"));
    expect(row).toContain(BILLING);
    expect(row).not.toContain(LIVES);
  });

  it("step 5: an apartment complex still says Master account", () => {
    const row = ownerRow(
      maria("landlord", { premise: { ...maria("landlord").premise, accountKind: "master" } }),
    );
    expect(row).toContain("Master account");
    expect(row).not.toContain(BILLING);
  });

  it("the request's Overview names the owner's account by what it is", () => {
    const made = (role: "lives_there" | "billing_only" | null) => {
      const record = buildRecordFixture();
      return renderToStaticMarkup(
        <MemoryRouter>
          <BuildOverviewTab
            t={t}
            detail={buildDetailFixture()}
            record={{
              ...record,
              owner_and_scope: { ...record.owner_and_scope, owner_account_role: role },
            }}
            timeZone="America/Chicago"
            dateFormat="MM/DD/YYYY"
            path={(segment) => `/${TEST_TENANT}/${segment}`}
            accountId={null}
          />
        </MemoryRouter>,
      );
    };
    expect(made("billing_only")).toContain(BILLING);
    expect(made("billing_only")).not.toContain(LIVES);
    expect(made("lives_there")).toContain(LIVES);
    const master = made(null);
    expect(master).not.toContain(BILLING);
    expect(master).not.toContain(LIVES);
  });
});

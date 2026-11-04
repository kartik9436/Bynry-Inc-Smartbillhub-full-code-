// ── Trace ──────────────────────────────────────────────
// Defect:   DEF-CUS-9228 — a single-family build could carry no connection
//           charge (step 4: "No master account to bill. Remove the charges.").
// Ruling:   PO 2026-10-02 (decision log "SEVEN PO ANSWERS IN ONE MESSAGE",
//           item 1): *"A. The owner asked for the work, so the owner pays."*
//           — a single-family (Regular-type) build opens the OWNER's own
//           regular account at Create and its charges are billed there.
// ───────────────────────────────────────────────────────
// RED FIRST, against 2.466.0: `buildOpensOwnerAccount` and `noOneToBill` did
// not exist (import error), the payer option was disabled on a single-family
// build, and step 5 drew *Master account 0* and *Customer record 0*.
//
// ⚠ WHAT WOULD MAKE THESE PASS WRONGLY: a draft with no owner named (nothing
// opens for that reason) — every draft here names Maria; and a regular-type
// draft with TWO homes, which the server refuses — asserted closed on its own.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ChargesStep } from "./NewConnectChargesStep";
import { ReviewStep } from "./NewConnectReviewStep";
import {
  buildOpensOwnerAccount,
  commitPlanOf,
  draftManifest,
  emptyDraft,
  noOneToBill,
  ownerMasterRefusedForSingleUnit,
} from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";

const TEST_TENANT = "brazosbend";
const t = (key: string, options?: unknown) => String(i18next.t(key, options as never));

/** Maria's single-family home at 14 Oak St, $90 + $30 on step 4. */
function maria(over: Partial<NewConnectDraft> = {}): NewConnectDraft {
  const blank = emptyDraft();
  return {
    ...blank,
    owner: { ...blank.owner, name: "Maria Alvarez", email: "maria@oak.test" },
    premise: { ...blank.premise, address: "14 Oak St", name: "14 Oak St", accountKind: "regular" },
    pattern: { prefix: "Unit", from: "1", to: "1", includeCommonArea: false },
    premiseServices: ["water"],
    apartmentServices: ["water"],
    planApartments: "plan-1",
    quoteLines: [
      { chargeCode: "CONN", basis: "per meter" },
      { chargeCode: "INSPECT", basis: "per premise" },
    ],
    quoteDueDays: "30",
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

function mount(node: React.ReactNode): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new?step=4`]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={node} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DEF-CUS-9228 — the owner pays a single-family build's charges", () => {
  it("opens the owner's own account and sends it on the commit", () => {
    const draft = maria();
    expect(buildOpensOwnerAccount(draft)).toBe(true);
    expect(commitPlanOf(draft, null).create_owner_account).toBe(true);
    expect(ownerMasterRefusedForSingleUnit(draft)).toBe(false);
    expect(noOneToBill(draft)).toBe(false);
    // The manifest counts Maria as the customer Create makes.
    expect(draftManifest(draft, null).customers).toBe(1);
  });

  it("two homes on a single-family type open nothing, and step 4 still says so", () => {
    const draft = maria({ pattern: { prefix: "Unit", from: "1", to: "2", includeCommonArea: false } });
    expect(buildOpensOwnerAccount(draft)).toBe(false);
    expect(commitPlanOf(draft, null).create_owner_account).toBe(false);
    expect(noOneToBill(draft)).toBe(true);
  });

  it("a home added at an address on file opens nothing from here", () => {
    const draft = maria({
      scope: "new_units",
      premise: { ...maria().premise, premisesId: "p-on-file" },
    });
    expect(buildOpensOwnerAccount(draft)).toBe(false);
  });

  it("step 4 offers the owner's account as payer, by name", () => {
    const html = mount(
      <ChargesStep draft={maria()} onPatch={() => undefined} t={t} dateFormat="MM/DD/YYYY" client={client()} />,
    );
    expect(html).not.toMatch(/<option value="owner_account" disabled/);
    // ⊕ `DEF-CUS-10047` (PO 2026-10-11) — the case's own word, *Regular
    // account*, where this read *Owner's account* until then.
    expect(html).toContain("Regular account · Maria Alvarez");
  });

  it("step 5 says what Create makes for a single-family home", () => {
    const draft = maria();
    const html = mount(
      <ReviewStep
        draft={draft}
        manifest={draftManifest(draft, null)}
        quoteTotal="120.00"
        quoteCurrency="USD"
        workOrderCount={0}
        onPatch={() => undefined}
        t={t}
        client={client()}
      />,
    );
    const row = (key: string) => {
      const start = html.indexOf(`data-creates="${key}"`);
      return html.slice(start, html.indexOf("</tr>", start));
    };
    // `DEF-CUS-10047` follow-up — the same kind step 4 names.
    expect(row("ownerAccount")).toContain("Regular account");
    expect(row("ownerAccount")).not.toContain("Master account");
    expect(row("ownerAccount")).toMatch(/data-creates-count="ownerAccount"[^>]*><span[^>]*>1</);
    expect(row("customer")).toMatch(/data-creates-count="customer"[^>]*><span[^>]*>1</);
    expect(html).not.toContain("data-owner-master-single-unit");
  });

  it("an apartment complex still says Master account", () => {
    const draft = maria({ premise: { ...maria().premise, accountKind: "master" } });
    const html = mount(
      <ReviewStep
        draft={draft}
        manifest={draftManifest(draft, null)}
        quoteTotal={null}
        quoteCurrency={null}
        workOrderCount={0}
        onPatch={() => undefined}
        t={t}
        client={client()}
      />,
    );
    const start = html.indexOf('data-creates="ownerAccount"');
    expect(html.slice(start, html.indexOf("</tr>", start))).toContain("Master account");
  });
});

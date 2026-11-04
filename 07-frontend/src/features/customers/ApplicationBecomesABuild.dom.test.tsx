// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-6109 (no application could become a build, and the two
//          halves were inverted) · DEF-MET-6117 (the false reason under it)
// Rules:   PO ruling 2026-09-21 — *"then approve applciation may create a new
//          conenct request - as draft request … we should not make it
//          dependent on applciation #"* · BR-MET-1178 (provenance, never a
//          dependency) · BR-MET-112 (nothing is written until the last button)
//          · CLAUDE.md hard-won law 2 (built is not wired — in BOTH directions)
// Drawing: 05-prototype/02 Accounts Menu Blueprint.pdf **p089**, read AS AN
//          IMAGE at scale 2.4 (B14 rule 42). Its `WHAT APPROVING WILL DO`
//          table's fourth row is *"Next · The build's own wizard asks for
//          units, services, plans and charges"* — which is the navigation
//          asserted here.
// ───────────────────────────────────────────────────────
//
// WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2)
// ---------------------------------------------------
// * **Asserting that the wizard fetched SOMETHING.** It fetches the tenant's
//   services and its plans on every mount, so a URL list that merely has
//   entries in it proves nothing. Every case below matches the ADDRESS.
// * **Mounting the wizard outside its route.** A bare `MemoryRouter` leaves
//   `useParams().tenant` undefined and every address the screen builds comes
//   out `//connections/…`, which reads as a perfectly good string to
//   `toContain` — the fixture fault that hid `DEF-CWP-3925`. Both mounts below
//   use the real path pattern.
// * **Asserting the draft was hydrated by reading component state.** There is
//   none to read; the assertion is on the VALUE IN THE INPUT the clerk sees.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { NewConnectWizard } from "./NewConnectWizard";
import { commitPlanOf, draftFromRaisedBuild, emptyDraft } from "./newConnectDraft";
import type { ConnectionDetail } from "./newConnectEndpoints";

const BUILD_ID = "01a0b111-2222-7333-8444-555566667777";
const PREMISES_ID = "01a0c888-9999-7aaa-8bbb-ccccddddeeee";
const CUSTOMER_ID = "01a0d111-2222-7333-8444-999988887777";

/** A draft raised from an application whose address did NOT resolve. */
const UNRESOLVED = {
  id: BUILD_ID,
  connection_no: "CON-26-0142",
  state: "draft",
  premises: null,
  prefill: {
    request_id: "01a0e111-2222-7333-8444-000011112222",
    request_no: "SR-26-0004",
    applicant_kind: "person",
    applicant_name: "Willow, Ada",
    applicant_email: "ada@example.com",
    applicant_phone: "(512) 555-0199",
    matched_customer_id: CUSTOMER_ID,
    address_as_given: "14 Willow Bend",
    address_unit_as_given: null,
    plot_or_parcel: "R-77012",
    property_type: "single_family",
    what_is_being_built: "A house",
    units_on_property: 1,
  },
  unit_summary: null,
  applicant: "Willow, Ada",
  request_no: "SR-26-0004",
  mode: "our_crew",
  started_at: null,
  target_activation: "2026-11-02",
  waiting_on: null,
  units: 0,
  orders: { done: 0, total: 0 },
  services: [],
  work_orders: [],
  unit_rows: [],
  assets: [],
  sub_meter_links: null,
  quote_total: { amount: null, display: null, currency: null },
  quote_settled_at: null,
  charges: null,
  deposit: null,
  outstanding: [],
  history: [],
  owner_account_no: null,
  unavailable: [],
} as unknown as ConnectionDetail;

/** The same draft where the resolver DID match a property on file. */
const RESOLVED = {
  ...UNRESOLVED,
  premises: {
    id: PREMISES_ID,
    premise_no: "P-00074",
    name: "Willow Bend House",
    address: "14 Willow Bend",
  },
} as unknown as ConnectionDetail;

function mountWizard(buildParam: string | null): string[] {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = String(input);
      urls.push(url);
      if (url.includes(`/connections/${BUILD_ID}`)) {
        return new Response(JSON.stringify(UNRESOLVED), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        });
      }
      return new Response(JSON.stringify({ count: 0, results: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const entry =
    buildParam === null
      ? "/brazosbend/connections/new?step=2"
      : `/brazosbend/connections/new?step=2&build=${buildParam}`;
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <ToastProvider>
        <MemoryRouter initialEntries={[entry]}>
          <Routes>
            <Route
              path="/:tenant/connections/new"
              element={<NewConnectWizard client={client} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return urls;
}

describe("DEF-CUS-6109 · an approved application becomes a build", () => {
  afterEach(cleanup);

  // ════════════════════════════════════════════════════════════════════════
  // 1 · THE WIZARD OPENS ON THE DRAFT AND READS IT
  // ════════════════════════════════════════════════════════════════════════
  it("`?build=` makes the wizard read THAT build, and step 2 opens on the address the applicant typed", async () => {
    const urls = mountWizard(BUILD_ID);
    await waitFor(() =>
      expect(urls.some((u) => u.includes(`/connections/${BUILD_ID}`))).toBe(true),
    );
    // The VALUE IN THE INPUT — what the clerk actually finds filled in.
    await waitFor(() =>
      expect((screen.getByLabelText(/Street address/i) as HTMLInputElement).value).toBe(
        "14 Willow Bend",
      ),
    );
  });

  it("no `?build=` reads no build at all — a wizard a clerk starts directly is untouched", () => {
    const urls = mountWizard(null);
    // ⛔ `BR-MET-1178` — provenance, never a dependency. A wizard that fetched
    // anything here would have made the directly-raised build depend on a
    // door that only an application path has.
    expect(urls.filter((u) => /\/connections\/[0-9a-f-]{36}$/u.test(u))).toEqual([]);
  });

  // ════════════════════════════════════════════════════════════════════════
  // 2 · WHAT THE COMMIT SENDS
  // ════════════════════════════════════════════════════════════════════════
  it("the last button FINISHES the draft it was opened on, and sends no application id", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), UNRESOLVED);
    const plan = commitPlanOf(draft, null, []);
    expect(plan.connection_id).toBe(BUILD_ID);
    // ⛔ The application is already on the `connections` row; sending it again
    // from a browser would be a second writer for one fact.
    expect(plan.service_request_id).toBeNull();
    // The address is sent whole, because on this shape it does not exist yet.
    expect(plan.premises.id).toBeNull();
    expect(plan.premises.address).toBe("14 Willow Bend");
  });

  it("a build a clerk starts directly sends `connection_id: null` — the ordinary case stays ordinary", () => {
    expect(commitPlanOf(emptyDraft(), null, []).connection_id).toBeNull();
  });

  // ════════════════════════════════════════════════════════════════════════
  // 3 · THE TWO SHAPES, IN THE PURE FUNCTION
  // ════════════════════════════════════════════════════════════════════════
  it("a draft raised against a property on file NAMES it, so the wizard creates no second address", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), RESOLVED);
    expect(draft.premise.premisesId).toBe(PREMISES_ID);
    expect(draft.premise.address).toBe("14 Willow Bend");
    // `commitPlanOf` reads `premises.id` FIRST, and set it means nothing is
    // created — hard rule 8, and this wizard is the one door that could make a
    // second row for a building that already has one.
    expect(commitPlanOf(draft, null, []).premises.id).toBe(PREMISES_ID);
    // The shape question follows the row rather than the default: a draft that
    // already names a premises is not *a new premise*.
    expect(draft.scope).toBe("new_units");
  });

  it("the applicant is OFFERED as the owner and does not satisfy step 1", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), UNRESOLVED);
    expect(draft.owner.name).toBe("Willow, Ada");
    expect(draft.owner.email).toBe("ada@example.com");
    // `business` is the application's word and `company` is the account
    // door's; reading one as the other is `DEF-MET-5438` one table over.
    expect(draft.owner.partyKind).toBe("person");
    // A customer the application already matched is NAMED, never re-described.
    expect(draft.owner.matchedCustomerId).toBe(CUSTOMER_ID);
    // ⚠ **THE UNIT PATTERN IS NOT PREFILLED although the request says one unit
    // is on the property.** Turning a COUNT into LABELS would be this function
    // inventing names that then reach `uq_units_tenant_premises_label` and
    // every bill after it.
    expect(draft.pattern.from).toBe("");
    expect(draft.pattern.to).toBe("");
  });

  it("carries the application forward as PROVENANCE and nothing more", () => {
    const draft = draftFromRaisedBuild(emptyDraft(), UNRESOLVED);
    expect(draft.requestNo).toBe("SR-26-0004");
    expect(draft.connectionId).toBe(BUILD_ID);
    // ⛔ Nothing in the eight steps branches on either of them; only the commit
    // reads `connectionId`, and `requestNo` is shown and never sent.
    expect(commitPlanOf(draft, null, [])).not.toHaveProperty("request_no");
  });
});

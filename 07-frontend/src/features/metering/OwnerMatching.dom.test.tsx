// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-039 wave C tasks 12-13 — the typed owner and the matching
//          surface. PO ruling 2026-08-27: *"category is okay, no richer text"*.
// Rules:   BR-MET-150 (the typed record) · BR-MET-151 (matching, never
//          guessing) · BR-TEN-150 (the vocabulary)
// Screens: S14 Premises tab (PRM-04 panel) · PRM-01 edit modal · S16 wizard
// ───────────────────────────────────────────────────────
// ⚠ **PROVED RED FIRST (2d), AND THE FAILURES ARE QUOTED IN THE LANE REPORT.**
// Run with `OwnerField.tsx` and `OwnerMatchingPanel.tsx` present and neither
// screen rendering either — the hard-won-law-2 shape, a component built and not
// wired — this file reports the panel and the picker as MISSING while the
// payload assertions still pass, which is precisely the half-green a built-not-
// wired feature produces.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { api } from "@/api/client";
import type { PremisesRow, PremisesType } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";
import type { OwnerAccount } from "@/features/metering/premisesOwnerContract";

import { addPremisePayload, emptyAddPremiseForm } from "@/features/metering/addPremise/addPremiseModel";
import type { AddPremiseForm } from "@/features/metering/addPremise/addPremiseModel";

/**
 * ⚠ `CR-177-BRC10` (2026-10-09): the old wizard's `singlePayload` is retired
 * with it. These cases ask the redesigned screen's payload builder the same
 * question, from the same fixture: the fixture's form is laid over an empty
 * one, a picked `master_account` becomes the LINKED owner, and `services: null`
 * (the old *never asked*) is an empty pick — the new screen always asks.
 */
function singlePayload(fixture: Record<string, unknown>): Record<string, unknown> {
  const picked = fixture.master_account as { id: string; account_no: string | null; name: string | null } | null | undefined;
  const form = {
    ...emptyAddPremiseForm(),
    ...(fixture as Partial<AddPremiseForm>),
    services: Array.isArray(fixture.services) ? (fixture.services as string[]) : [],
    custom_data: (fixture.custom_data as Record<string, unknown> | undefined) ?? {},
    unit_custom_data: (fixture.unit_custom_data as Record<string, unknown> | undefined) ?? {},
    service_point_custom_data:
      (fixture.service_point_custom_data as Record<string, Record<string, unknown>> | undefined) ?? {},
  } as AddPremiseForm;
  const owner =
    picked === null || picked === undefined
      ? null
      : {
          id: picked.id,
          account_no: picked.account_no,
          name: picked.name,
          account_type: "",
          account_type_name: null,
          party_kind: null,
          managed_by: null,
          status: "",
          status_name: null,
        };
  return addPremisePayload(form, { owner, addAnyway: false });
}
import { OwnerMatchingPanel, unmatchedOwnersQueryKey } from "./OwnerMatchingPanel";
import { PremisesEditModal } from "./PremisesListPage";

const TEST_TENANT = "brazosbend";

const TYPES: PremisesType[] = [
  { id: "t-1", code: "single_family", name: "Single family", active: true, is_system: true },
];


function premise(overrides: Partial<PremisesRow> = {}): PremisesRow {
  return {
    id: "p-101",
    premise_no: "P-11800",
    name: null,
    address_line: "4 Quarry Hill Rd",
    city: "Katy",
    state: "TX",
    postal_code: "77494",
    premises_type: "single_family",
    premises_type_name: "Single family",
    inside_city_limits: null,
    area_code: null,
    area_name: null,
    area_parent_code: null,
    area_path: null,
    services_available: null,
    owner_manager: null,
    owner: null,
    owner_unmatched: false,
    external_ref: null,
    status: "active",
    unit_count: 1,
    ...overrides,
  } as unknown as PremisesRow;
}

function client(queryClient: QueryClient, node: React.ReactNode) {
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises`]}>{node}</MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function freshClient(): QueryClient {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  queryClient.setQueryData(queryKeys.tenantServices, []);
  return queryClient;
}

// Read at runtime through a non-literal dynamic import — the pattern
// `src/styles/tailwindTheme.test.ts` established and
// `src/features/customers/accountStatusTone.test.tsx` documents: the app
// carries no `@types/node` on purpose, so a static `import { readFileSync }`
// would fail `tsc --noEmit` and break `npm run build`.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(path: string, encoding: string): string;
};
afterEach(cleanup);

// ── BR-MET-150 · the picker is WIRED, not merely built ─────────────────────

describe("PRM-01 draws the OWNER beside the free text — one vocabulary", () => {
  // ⛔ **THIS TEST ASSERTED TWO OF THE FIVE WORDINGS THE PO COUNTED**, and it
  // passed the whole time they were on screen — which is why it is REWRITTEN
  // rather than deleted. It read:
  //     expect(screen.getByLabelText(/Owner \(record\)/i)).toBeInTheDocument();
  //     expect(screen.getByLabelText(/Owner \/ manager/i)).toBeInTheDocument();
  // PO 2026-09-22: *"owner and master account is confusing we ahve to use one
  // volcabory"*. **Owner** is the surviving noun; the second box is a DIFFERENT
  // fact and is named for what it is, in the blueprint's own word.
  it("renders both controls, because both are real and they are different facts", () => {
    const queryClient = freshClient();
    client(
      queryClient,
      <PremisesEditModal
        row={premise({ owner_manager: "Mill Pond Apartments LP", owner_unmatched: true })}
        types={TYPES}
        client={api}
        onClose={() => undefined}
        onSaved={() => undefined}
      />,
    );
    // The master account this property names. ⚠ **THE WORD CHANGED ON
    // 2026-09-23 AND THE FIELD DID NOT.** It read `Owner` from 2026-09-22,
    // when the PO ruled *"owner and master account is confusing we ahve to
    // use one volcabory"* and the repo picked `Owner`; they reversed the
    // choice the next day — *"it should show master account"* — and asked for
    // it short: *"make it small m acct or somehing line this"*. `OQ-MET-12610`
    // records both rulings, because two genuine rulings eight days apart is
    // hard-won law 13's own mechanism. Still ONE word for one thing, which is
    // the part that never moved.
    const owner = screen.getByLabelText("Master a/c");
    expect(owner).toBeInTheDocument();
    expect(owner.getAttribute("id")).toBe("owner_master_account");
    // …and the free-text box, which `open_account` still reads for the default
    // payer (`OQ-500`) and which `BR-MET-151` matches an import against. A form
    // that drew only the search would hide the field that routes the money.
    expect(screen.getByLabelText(/Managed by/i)).toBeInTheDocument();
    // ⛔ AND THE RETIRED WORDINGS ARE GONE FROM THE SCREEN, not merely unused.
    // An absence is invisible to every other check this repo has.
    expect(screen.queryByLabelText(/Owner \(record\)/i)).toBeNull();
    expect(screen.queryByLabelText(/Owner \/ manager/i)).toBeNull();
    // ⛔ AND `Owner` ITSELF IS NOW A RETIRED WORDING on this field. Added with
    // the 2026-09-23 reversal so the list of dead words keeps growing rather
    // than being replaced — a screen that drifts back is what this block is for.
    expect(screen.queryByLabelText(/^Owner$/i)).toBeNull();
  });
});

describe("CR-039 C12 — S16's payload carries the party the clerk picked", () => {
  const SINGLE_FORM = {
    address_line: "1901 Bluestem Ln",
    city: "Katy",
    state: "TX",
    postal_code: "77494",
    premises_type: "single_family",
    area: { top: "", sub: "" },
    services: null,
    inside_city_limits: null as boolean | null,
    master_account: null as OwnerAccount | null,
    owner_manager: "",
    // `DEF-MET-5840` — the owner's account type. "" is the SHIPPED
    // answer: no account type chosen, so no owner account.
    owner_account_type: "",
    // `OQ-MET-12472` — the owner's kind and identifier, blank here on purpose:
    // no identity means no owner account, and the address still saves.
    owner_kind: "",
    owner_ssn: "",
    owner_driving_licence: "",
    owner_phone: "",
    owner_tax_id: "",
    external_ref: "",
    gis_parcel_id: "",
    // CR-089 wave A `PUJ-04` — the three answers the create form now
    // collects. `gis_unchecked: true` is the default: nobody has checked a
    // property that does not exist yet.
    lat: "",
    lng: "",
    gis_unchecked: true,
    // CR-089 wave B: `route` (B6, optional at creation) and `common_areas`
    // (B5, recorded while creating) join the form the wizard collects.
    route: "",
    common_areas: [],
    // CR-089 `p008` §5 — `How many units?` is a NUMBER now, so the two
    // booleans this replaced are gone rather than defaulted around.
    unit_count: "0",
    unit_type: "",
  };

  /** A master account the clerk picked. B14 rule 31: the NUMBER is what a
   *  screen shows; this id only ever travels in a payload. */
  const ACCOUNT_ID = "01a0c23c-bd23-7f85-a7d5-b55bace9a4f3";

  // ⛔ **THESE TWO ASSERTED `owner_id` UNTIL 2026-09-22 AND THE KEY IS NOW
  // `master_account_id` (`CR-130-BRC07`, PO ruling of that date).** A premises
  // names its MASTER ACCOUNT directly; there is no owner record in the chain.
  it("sends master_account_id when an account was picked", () => {
    const payload = singlePayload({
      ...SINGLE_FORM,
      master_account: { id: ACCOUNT_ID, account_no: "AC-2026-00051", name: "Ridge Property LLC", owns_count: null },
    });
    expect(payload.master_account_id).toBe(ACCOUNT_ID);
    // And the retired key is not sent under its old name by some other route.
    expect("owner_id" in payload).toBe(false);
  });

  it("OMITS master_account_id when none was — absent means *leave it alone*", () => {
    // ⚠ Not `null`, and the difference matters: a create that states *no owner*
    // is making a claim the clerk never made. Absent is this API's documented
    // "leave it alone".
    expect("master_account_id" in singlePayload(SINGLE_FORM)).toBe(false);
  });
});

// ── BR-MET-151 · the matching surface ──────────────────────────────────────

describe("CR-039 C13 — the matching panel", () => {
  it("shows one row PER NAME with every address under it", () => {
    const queryClient = freshClient();
    queryClient.setQueryData(unmatchedOwnersQueryKey, {
      results: [
        {
          owner_manager: "Whitfield Rentals LLC",
          premises: [
            { id: "p-1", premise_no: "P-1", address_line: "21 Elm" },
            { id: "p-2", premise_no: "P-2", address_line: "23 Elm" },
          ],
          premises_count: 2,
          suggested_owner_ids: [],
        },
      ],
      names: 1,
      premises: 2,
    });
    client(queryClient, <OwnerMatchingPanel client={api} />);
    expect(screen.getByText("Whitfield Rentals LLC")).toBeInTheDocument();
    expect(screen.getByText(/21 Elm · 23 Elm/)).toBeInTheDocument();
  });

  it("pre-selects NO category — BR-MET-151 clause 3, at the UI layer", () => {
    // ⚠ **THE ONE ASSERTION THIS FILE EXISTS FOR.** A select that defaulted to
    // the first or the commonest kind would break the rule by convenience
    // rather than by decision, and every other test here would still pass.
    const queryClient = freshClient();
    queryClient.setQueryData(unmatchedOwnersQueryKey, {
      results: [
        {
          owner_manager: "Chen, David",
          premises: [{ id: "p-9", premise_no: "P-9", address_line: "2201 Cane Island Pkwy" }],
          premises_count: 1,
          suggested_owner_ids: [],
        },
      ],
      names: 1,
      premises: 1,
    });
    queryClient.setQueryData(["lookups", "owner_categories"], {
      results: [
        { id: "c-1", code: "owner_occupier", name: "Owner-occupier", active: true, is_system: true },
        { id: "c-2", code: "landlord", name: "Landlord", active: true, is_system: true },
      ],
      count: 2,
      page: 1,
      per: 200,
    });
    client(queryClient, <OwnerMatchingPanel client={api} />);
    const select = screen.getByLabelText(/Owner type/i) as HTMLSelectElement;
    expect(select.value).toBe("");
    // And the commit is refused until a person chooses.
    expect(screen.getByRole("button", { name: /Create this owner and link/i })).toBeDisabled();
  });

  it("is actually MOUNTED by the Premises tab, not merely built", () => {
    // ⚠ **HARD-WON LAW 2, AND THIS TEST EXISTS BECAUSE THE SABOTAGE FOUND THE
    // HOLE.** Every other assertion in this describe renders
    // `OwnerMatchingPanel` DIRECTLY, so all of them stay green with the panel
    // built and no screen using it — a component nothing mounts is dead UI, and
    // four defects in one day came from exactly that shape. Proved: deleting
    // `<OwnerMatchingPanel client={client} />` from `PremisesListPage.tsx` left
    // this file at 6 passed until this case was added.
    //
    // A SOURCE SCAN rather than a full page render, and the precedent is this
    // repo's own `RoutesCyclesRulings.test.tsx`: mounting S14 needs six queries
    // this assertion has no opinion about, and a test that heavy fails for
    // reasons that have nothing to do with the thing it is guarding.
    // ⚠ A PATH RELATIVE TO THE VITEST ROOT, not `import.meta.url`: under the
    // jsdom environment this file'''s `import.meta.url` is not a `file:` URL and
    // `fileURLToPath` throws. The node-env precedent
    // (`accountStatusTone.test.tsx`) can use the URL form; a jsdom test cannot.
    const source = nodeFs.readFileSync(
      "src/features/metering/PremisesListPage.tsx",
      "utf8",
    );
    expect(source).toContain("<OwnerMatchingPanel");
    expect(source).toContain("<OwnerField");
  });

  it("renders NOTHING when there is nothing to match", () => {
    // A zero-state panel is a permanent piece of furniture describing an empty
    // set. The work is finite and the surface ends with it.
    const queryClient = freshClient();
    queryClient.setQueryData(unmatchedOwnersQueryKey, { results: [], names: 0, premises: 0 });
    const { container } = client(queryClient, <OwnerMatchingPanel client={api} />);
    expect(container.textContent).toBe("");
  });
});

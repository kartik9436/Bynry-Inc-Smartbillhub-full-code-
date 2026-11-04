// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  `+ New unit` on a building FORGETS the building · the empty units
//          list offers a create it cannot complete instead of the property list.
// Change:  CR-089 wave E `E3` (`PUJ-23`) — *"adding units starts by naming the
//          building"*; blueprint page 54's amber block, verbatim: *"Pressing
//          '+ New unit' on a building forgets the building"*.
// Screens: PRM-02 (the property's page, header + Units tab) → S16 (Add units) ·
//          S15 · PRM-01U (the units list's empty state) → S14 (the property list)
// Drawn:   04-docs/05-modules/04-metering/conformance/CR-089-p053-add-units-details.md
//          · CR-089-p050-units-list.md §8
// Rules:   B14 rule 4 (one primary per screen) · hard-won law 2 and its mirror
//          (a live screen behind a door that does not carry what it should)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY THIS FILE EXISTS AND WHY IT IS A `jsdom` FILE.**
// `UnitsPage.test.tsx` already asserted `unitsAddPath("p-101")` builds
// `/premises/units/new?premises=p-101` — and it did, correctly, for a helper
// **nothing but that assertion ever called**. The two `+ New unit` buttons on
// the property's own page navigated to the BARE route, so a clerk standing on
// `412 Cypress Row` was handed an empty building box. A pure-string test can
// never see that: the destination of an `onClick` is not in the markup, so
// `renderToStaticMarkup` cannot be asked the question at all.
//
// **So the assertion here is about the ADDRESS THE BROWSER ENDS ON**, reached
// by pressing the control a person actually presses. That is the shape
// `CLAUDE.md` asks for in as many words — *"assert the destination by ADDRESS
// and by the screen id it opens"*.
//
// ⚠ **AND IT MOUNTS UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter` with
// no `/:tenant/…` route leaves the tenant segment undefined and every URL the
// page builds comes out `//premises/…`, which reads as a perfectly good string
// to `toContain`.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import type { PremisesDetail } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import type { UnitRow } from "@/api/endpoints";
import { parseTableParams, serializeTableParams } from "@/components/tableTypes";

import { PremisesDetailPage, premisesDetailQueryKey, premisesAssetsQueryKey } from "./PremisesDetailPage";
import { PremisesTabsPage, premisesRollupQueryKey } from "./PremisesTabsPage";
import {
  unitPremisesPickerKey,
  unitsQueryKey,
  unitsTableConfig,
} from "./UnitsListPage";
import { PREMISES_TAB_UNITS, unitsAddPath } from "./meteringShared";

const TEST_TENANT = "brazosbend";
const PREMISES_ID = "p-00080";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

afterEach(cleanup);

function premise(over: Partial<PremisesDetail> = {}): PremisesDetail {
  return {
    id: PREMISES_ID,
    premise_no: "P-00080",
    name: null,
    address_line: "412 Cypress Row",
    city: "Silver Creek",
    state: "TX",
    postal_code: "78611",
    inside_city_limits: null,
    area_code: null,
    area_name: null,
    area_parent_code: null,
    area_path: null,
    premises_type: "apartment",
    premises_type_name: "Apartment complex",
    services_available: ["electric", "water"],
    owner_manager: "Creekside Holdings LP",
    owner: null,
    owner_unmatched: false,
    external_ref: null,
    gis_unchecked: false,
    lat: null,
    lng: null,
    gis_checked_at: null,
    gis_checked_by: null,
    status: "active",
    units: 0,
    unit_rows: [],
    units_common: 0,
    ...over,
  };
}

/** The address the browser ended on, printed where a test can read it. */
function WhereAmI() {
  const location = useLocation();
  return <output data-testid="where">{`${location.pathname}${location.search}`}</output>;
}

function mount(detail: PremisesDetail, tab?: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(premisesDetailQueryKey(detail.id), detail);
  queryClient.setQueryData(premisesAssetsQueryKey(detail.id), {
    count: 0,
    next: null,
    previous: null,
    results: [],
  });
  const at = `/${TEST_TENANT}/premises/${detail.id}${tab === undefined ? "" : `?tab=${tab}`}`;
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[at]}>
          <Routes>
            <Route path="/:tenant/premises/:premisesId" element={<PremisesDetailPage />} />
            <Route path="/:tenant/premises/units/new" element={<WhereAmI />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-089 E3 — `+ New unit` on a building carries the building", () => {
  it("the header's primary lands on the wizard WITH this property on it", async () => {
    mount(premise());
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: t("metering.units.action.new") }));
    // The whole defect in one assertion: the address, not merely the route.
    expect(screen.getByTestId("where")).toHaveTextContent(
      `/${TEST_TENANT}${unitsAddPath(PREMISES_ID)}`,
    );
  });

  it("the Units tab's empty state lands on the same address, not a barer one", async () => {
    mount(premise(), "units");
    const user = userEvent.setup();
    // Two `+ New unit` controls are on screen once the tab is open — the
    // header's primary and the empty state's secondary. Both are doors onto one
    // screen and they must not disagree about what travels with the press, so
    // the LAST one (the empty state's) is the one pressed here.
    const doors = screen.getAllByRole("button", { name: t("metering.units.action.new") });
    expect(doors.length).toBeGreaterThan(1);
    await user.click(doors[doors.length - 1]);
    expect(screen.getByTestId("where")).toHaveTextContent(
      `/${TEST_TENANT}${unitsAddPath(PREMISES_ID)}`,
    );
  });
});

// ── THE OTHER DOOR ON THIS PAIR OF SCREENS ────────────────────────────────
// The units list's EMPTY state. It offered `+ New unit` — a button onto a
// wizard whose first required box is a building, over a tenant that has no
// buildings — and the frame draws the opposite: *"Says a property must exist
// first, and links to the property list."* A label assertion cannot tell a
// working link from a dead one, so this presses it.

/** The cells contract, stubbed: this file asks about the DOOR, not the row. */
const LIST_CONFIG = unitsTableConfig(t, [], [], {
  select: () => <span />,
  unitNo: () => <span />,
  premise: () => <span />,
  owed: () => <span />,
  label: () => <span />,
  type: () => <span />,
  services: () => <span />,
  offered: () => <span />,
  missing: () => <span />,
  meters: () => <span />,
  occupancy: () => <span />,
  occupant: () => <span />,
  status: () => <span />,
  actions: () => <span />,
});

function mountEmptyUnitsList() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const state = parseTableParams(new URLSearchParams(), LIST_CONFIG);
  const none = { count: 0, next: null, previous: null, results: [] as UnitRow[] };
  queryClient.setQueryData(unitsQueryKey(serializeTableParams(state, LIST_CONFIG).toString()), none);
  queryClient.setQueryData(unitPremisesPickerKey, { ...none, rollup: null });
  queryClient.setQueryData(premisesRollupQueryKey, { ...none, rollup: null });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/units`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units"
              element={<PremisesTabsPage tab={PREMISES_TAB_UNITS} />}
            />
            <Route path="/:tenant/premises" element={<WhereAmI />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CR-089 U1 — an empty units list sends you to the properties", () => {
  it("says a property must exist first, and the link actually opens that list", async () => {
    mountEmptyUnitsList();
    expect(screen.getByText(t("metering.units.emptyNeedsPremises"))).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(
      screen.getByRole("button", { name: t("metering.units.emptyOpenPremises") }),
    );
    expect(screen.getByTestId("where")).toHaveTextContent(`/${TEST_TENANT}/premises`);
  });

  it("the empty state offers ONE way out, and it is not a create it cannot finish", () => {
    mountEmptyUnitsList();
    // ⚠ **SCOPED TO THE EMPTY BLOCK, NOT TO THE PAGE.** The header's own
    // `+ New unit` is a different control on a different row and is untouched
    // by this frame; asserting over the whole document would either pass on the
    // header's button or demand its removal. What the drawing refuses is a
    // SECOND create INSIDE the empty state, over a tenant with no building to
    // put a unit in.
    const frame = document.querySelector(".state-empty");
    expect(frame).not.toBeNull();
    const buttons = Array.from(frame!.querySelectorAll("button")).map((b) => b.textContent);
    expect(buttons).toEqual([t("metering.units.emptyOpenPremises")]);
    // …and the two sentences about CSV imports that used to stand here are
    // gone: B14 rule 32 gives this section ONE sentence.
    expect(frame!.textContent).not.toContain("from a CSV");
  });
});

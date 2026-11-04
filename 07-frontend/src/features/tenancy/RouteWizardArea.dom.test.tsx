// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-TEN-5842 (SET-06 step 1 drew ONE area control under a label
//          reading `Area · sub-area` — the PO ruled two controls on
//          2026-09-08 and the ruling never reached this wizard) ·
//          DEF-TEN-5843 (the premises picker ignored the area step 1 had just
//          asked for, and offered every premises in the tenant)
// Rules:   BR-MET-071 (two controls, ONE stored column — `areaPayloadCode`) ·
//          BR-MET-072 (the area filter is MULTI-SELECT and a PARENT matches
//          its sub-areas too) · BR-MET-073 (a route carries ONE area) ·
//          BR-SHL-025 (disabled WITH its reason) · NFR-3 (server pagination)
// ───────────────────────────────────────────────────────
/**
 * TWO FAULTS THE HUMAN QA TEAM REPORTED ON 2026-09-19, BOTH ON SET-06 STEP 1.
 *
 * ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, WHICH IS THE QUESTION WORTH ASKING
 * FIRST (hard-won law 7).** A case asserting *"the picker shows fewer rows"*
 * passes on a screen that has simply not loaded yet, and a case asserting
 * *"a sub-area control exists"* passes on a control that is drawn and wired to
 * nothing. So the picker cases assert the **REQUEST** — which `area` values
 * went on the wire — and the field cases assert the **STORED PAYLOAD**, which
 * is the only thing that survives the screen.
 *
 * ⚠ **THE STUB RECORDS EVERY REQUEST AND SERVES ONLY WHAT WAS ASKED FOR.** A
 * fixture that returned the same rows whatever the filters said could not tell
 * a picker that narrows from one that does not — `DEF-CWP-3925`'s shape, and
 * the exact reason `DEF-MET-5743`'s own fixture had to be built to page.
 */
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";
import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { RouteWizard, areaSelectionFromEntries } from "./RoutesCyclesWizards";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/**
 * The seeded hierarchy, in the shape `GET /lookups/areas` publishes it
 * (`BR-MET-066b/066c`): four districts, three sub-areas under two of them.
 * Downtown and Industrial corridor are deliberately childless — that is the
 * ratified fixture, and it is what makes *"this area has no sub-areas"*
 * demonstrable at all.
 */
const AREAS = [
  { id: "a1", code: "NORTH", name: "North district", active: true, is_system: false, used_by: 0, parent_code: null, parent_name: null, is_sub_area: false },
  { id: "a2", code: "NORTH-NE", name: "NE", active: true, is_system: false, used_by: 0, parent_code: "NORTH", parent_name: "North district", is_sub_area: true },
  { id: "a3", code: "NORTH-NW", name: "NW", active: true, is_system: false, used_by: 0, parent_code: "NORTH", parent_name: "North district", is_sub_area: true },
  { id: "a4", code: "DTWN", name: "Downtown", active: true, is_system: false, used_by: 0, parent_code: null, parent_name: null, is_sub_area: false },
];

interface PickerCall {
  areas: string[];
}

/** Every premises the tenant has, each tagged with the area it sits in. */
const PREMISES = [
  { id: "p1", premise_no: "P-00001", address_line: "101 Silver Creek Rd", area_code: "NORTH-NW", area_path: "North district · NW" },
  { id: "p2", premise_no: "P-00002", address_line: "103 Silver Creek Rd", area_code: "NORTH-NE", area_path: "North district · NE" },
  { id: "p3", premise_no: "P-00003", address_line: "107 Mill Pond Ln", area_code: "DTWN", area_path: "Downtown" },
];

function pickerRow(row: (typeof PREMISES)[number]) {
  return {
    ...row,
    premises_type: "Single-family",
    units: 1,
    unit_ids: [`${row.id}-u1`],
    meters: 1,
    area_name: row.area_path,
    current_route: null,
    current_route_id: null,
    on_this_route: false,
  };
}

/**
 * ⚠ **`area` IS A REPEATED QUERY PARAM, NOT A COMMA LIST** — that is how
 * `GET /routes/premises-picker` receives a multi-select (`params.getlist`), and
 * a stub that read it any other way would be testing a wire format the server
 * does not speak.
 */
function routeClient(calls: PickerCall[]): ApiClient {
  return {
    get: async (path: string) => {
      const ok = (data: unknown) => ({ data, status: 200, headers: new Headers() });
      if (path === "/routes/next-code") {
        return ok({ code: "RT-0007", warnings: [] });
      }
      if (path === "/settings/services") {
        return ok([{ service: "water", name: "Water", enabled: true }]);
      }
      if (path === "/lookups/areas") {
        return ok({ count: AREAS.length, next: null, previous: null, results: AREAS });
      }
      if (path.startsWith("/routes/premises-picker")) {
        // The screen builds its own query string for this one, so the areas
        // are read back off the URL exactly as the server would read them.
        const query = new URLSearchParams(path.split("?")[1] ?? "");
        const areas = query.getAll("area");
        calls.push({ areas });
        // ⚠ **BR-MET-072 — A PARENT MATCHES ITS SUB-AREAS TOO.** The stub does
        // the server's job here; a stub that matched the code exactly would
        // report `North district` as covering nothing, and the screen would
        // look broken for a reason that is entirely the fixture's.
        const matched =
          areas.length === 0
            ? PREMISES
            : PREMISES.filter((row) =>
                areas.some((code) => {
                  const entry = AREAS.find((one) => one.code === code);
                  if (entry === undefined) return false;
                  return entry.is_sub_area
                    ? row.area_code === code
                    : row.area_code === code ||
                        AREAS.some(
                          (sub) => sub.parent_code === code && sub.code === row.area_code,
                        );
                }),
              );
        return ok({
          count: matched.length,
          next: null,
          previous: null,
          results: matched.map(pickerRow),
        });
      }
      return ok({ count: 0, next: null, previous: null, results: [] });
    },
    post: vi.fn(),
    patch: vi.fn(),
  } as unknown as ApiClient;
}

function renderRouteWizard(calls: PickerCall[]): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* ⚠ **MOUNTED UNDER THE REAL PATH PATTERN (`DEF-CWP-3925`).** A routed
            component rendered bare has `useParams().tenant` undefined, so every
            address it builds comes out `//…` and still reads as a good string
            to `toContain`. */}
        <MemoryRouter initialEntries={["/brazosbend/settings/reference-data/routes-cycles/routes/new"]}>
          <Routes>
            <Route
              path="/:tenant/settings/reference-data/routes-cycles/routes/new"
              element={
                <RouteWizard
                  route={null}
                  client={routeClient(calls)}
                  readOnly={false}
                  onDone={() => undefined}
                  onCancel={() => undefined}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** Step 1 refuses to advance without a NAME (`settings.routes.wizard.nameRequired`),
 *  so the helper supplies one — the area is what these cases are about. */
async function toStepTwo(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  const name = screen.getByLabelText(t("settings.routes.wizard.name"));
  if ((name as HTMLInputElement).value === "") {
    await user.type(name, "Silver Creek walk");
  }
  await user.click(screen.getByRole("button", { name: t("wizard.continue") }));
}

describe("DEF-TEN-5842 · Area and sub-area are TWO controls on the route wizard", () => {
  it("both boxes are drawn, and the sub-area one is present-and-disabled until an area is picked", async () => {
    renderRouteWizard([]);
    // ⚠ **PRESENT AND EMPTY RATHER THAN ABSENT.** `AreaFields` made this
    // decision for the premises screens and its reason holds here: *"a control
    // that materialises when you touch its neighbour is a control people do
    // not find."*
    const sub = await screen.findByLabelText(t("metering.premises.field.subArea"));
    expect(screen.getByLabelText(t("metering.premises.field.area"))).toBeInTheDocument();
    expect(sub).toBeDisabled();
    // BR-SHL-025 — disabled WITH its reason, never a dead box.
    expect(sub).toHaveAttribute("title", t("metering.premises.field.subAreaPickAreaFirst"));
  });

  it("choosing an area fills the sub-area box with THAT area's children and nothing else", async () => {
    const user = userEvent.setup();
    renderRouteWizard([]);
    const top = await screen.findByLabelText(t("metering.premises.field.area"));
    await user.selectOptions(top, "NORTH");
    const sub = screen.getByLabelText(t("metering.premises.field.subArea"));
    expect(sub).toBeEnabled();
    await waitFor(() => {
      expect(screen.getByRole("option", { name: "NW" })).toBeInTheDocument();
    });
    expect(screen.getByRole("option", { name: "NE" })).toBeInTheDocument();
    // Downtown is a DISTRICT, so it must never appear in the sub-area box.
    expect(screen.queryByRole("option", { name: "Downtown" })?.closest("select")).not.toBe(sub);
  });

  it("changing the area clears a chosen sub-area rather than leaving it contradicting", async () => {
    const user = userEvent.setup();
    renderRouteWizard([]);
    const top = await screen.findByLabelText(t("metering.premises.field.area"));
    await user.selectOptions(top, "NORTH");
    const sub = screen.getByLabelText(t("metering.premises.field.subArea"));
    await waitFor(() => expect(sub).toBeEnabled());
    await user.selectOptions(sub, "NORTH-NW");
    expect(sub).toHaveValue("NORTH-NW");
    // Keeping `North district · NW` selected under `Downtown` would store a
    // code that contradicts the box above it.
    await user.selectOptions(top, "DTWN");
    expect(sub).toHaveValue("");
  });

  it("the stored code is the SUB-AREA when one is chosen and the area otherwise — one column, unchanged", () => {
    // `areaSelectionFromEntries` is the half that re-opens an edit, and it is
    // the half a bare `area_code` cannot do on its own: the route serializer
    // publishes no `area_parent_code`, so the pair is RESOLVED against the
    // lookup rather than guessed. Guessing would put every sub-area in the Area
    // box and silently re-tag the route to its PARENT on the next save.
    expect(areaSelectionFromEntries("NORTH-NW", AREAS)).toEqual({ top: "NORTH", sub: "NORTH-NW" });
    expect(areaSelectionFromEntries("NORTH", AREAS)).toEqual({ top: "NORTH", sub: "" });
    expect(areaSelectionFromEntries("", AREAS)).toEqual({ top: "", sub: "" });
    // ⚠ **AN UNKNOWN CODE IS THE EMPTY PAIR, NOT AN INVENTED TOP-LEVEL ONE.** A
    // route tagged to a district somebody has since deleted must not quietly
    // re-tag itself to a code nobody chose.
    expect(areaSelectionFromEntries("GONE", AREAS)).toEqual({ top: "", sub: "" });
  });
});

describe("DEF-TEN-5843 · the premises picker DEFAULTS to the area step 1 asked for", () => {
  it("opens filtered to that area — asserted on the REQUEST, not on the row count", async () => {
    const user = userEvent.setup();
    const calls: PickerCall[] = [];
    renderRouteWizard(calls);
    await user.selectOptions(
      await screen.findByLabelText(t("metering.premises.field.area")),
      "NORTH",
    );
    await toStepTwo(user);
    // ⚠ **THE REQUEST IS THE ASSERTION.** Counting rendered rows cannot see
    // this defect: three rows appear whether the browser asked for three or for
    // forty thousand, which is `DEF-MET-5743`'s own finding one screen along.
    await waitFor(() => {
      expect(calls.at(-1)?.areas).toEqual(["NORTH"]);
    });
    // And the narrowing is VISIBLE — a clerk seeing 2 rows of 3 can read why.
    expect(
      screen.getByText(t("settings.routes.wizard.areaChip", { area: "North district" })),
    ).toBeInTheDocument();
  });

  it("a sub-area narrows further than its district — the two are not the same filter", async () => {
    const user = userEvent.setup();
    const calls: PickerCall[] = [];
    renderRouteWizard(calls);
    await user.selectOptions(
      await screen.findByLabelText(t("metering.premises.field.area")),
      "NORTH",
    );
    const sub = screen.getByLabelText(t("metering.premises.field.subArea"));
    await waitFor(() => expect(sub).toBeEnabled());
    await user.selectOptions(sub, "NORTH-NW");
    await toStepTwo(user);
    await waitFor(() => {
      expect(calls.at(-1)?.areas).toEqual(["NORTH-NW"]);
    });
    // BR-MET-072 in the rows: the district covers two, its sub-area covers one.
    await waitFor(() => {
      expect(screen.getByText("101 Silver Creek Rd")).toBeInTheDocument();
    });
    expect(screen.queryByText("103 Silver Creek Rd")).toBeNull();
  });

  it("IT IS A DEFAULT AND NOT A LOCK — removing the chip widens it back to the tenant", async () => {
    const user = userEvent.setup();
    const calls: PickerCall[] = [];
    renderRouteWizard(calls);
    await user.selectOptions(
      await screen.findByLabelText(t("metering.premises.field.area")),
      "NORTH",
    );
    await toStepTwo(user);
    await waitFor(() => expect(calls.at(-1)?.areas).toEqual(["NORTH"]));
    // ⚠ **THIS IS THE HALF THAT MATTERS MOST.** A route genuinely picks up a
    // stray property outside its area, and a filter with no way out turns a
    // small annoyance into an impossible task — so the derived default is an
    // ordinary REMOVABLE chip and not a hidden clause in the query.
    await user.click(
      screen.getByLabelText(
        t("settings.routes.wizard.removeAreaFilter", { area: "North district" }),
      ),
    );
    await waitFor(() => {
      expect(calls.at(-1)?.areas).toEqual([]);
    });
    await waitFor(() => {
      expect(screen.getByText("107 Mill Pond Ln")).toBeInTheDocument();
    });
  });

  it("the clerk can ADD a second area — a route crossing two of them is expressible", async () => {
    const user = userEvent.setup();
    const calls: PickerCall[] = [];
    renderRouteWizard(calls);
    await user.selectOptions(
      await screen.findByLabelText(t("metering.premises.field.area")),
      "NORTH",
    );
    await toStepTwo(user);
    await waitFor(() => expect(calls.at(-1)?.areas).toEqual(["NORTH"]));
    await user.selectOptions(
      screen.getByLabelText(t("settings.routes.wizard.addFilter")),
      "DTWN",
    );
    await waitFor(() => {
      expect(calls.at(-1)?.areas).toEqual(["NORTH", "DTWN"]);
    });
    // All three premises are now in scope — the street that crosses two areas.
    await waitFor(() => {
      expect(screen.getByText("107 Mill Pond Ln")).toBeInTheDocument();
    });
    expect(screen.getByText("101 Silver Creek Rd")).toBeInTheDocument();
  });

  it("going BACK and changing the area re-derives the filter instead of leaving the old one", async () => {
    const user = userEvent.setup();
    const calls: PickerCall[] = [];
    renderRouteWizard(calls);
    await user.selectOptions(
      await screen.findByLabelText(t("metering.premises.field.area")),
      "NORTH",
    );
    await toStepTwo(user);
    await waitFor(() => expect(calls.at(-1)?.areas).toEqual(["NORTH"]));
    // ⚠ **THIS IS WHAT A COPY-ON-ARRIVAL IMPLEMENTATION GETS WRONG.** Seeding
    // the chips when step 2 opens looks identical until somebody steps back:
    // the screen then filters by an area no control on it still shows, which is
    // the two-disconnected-states bug wearing a different hat.
    await user.click(screen.getByRole("button", { name: t("wizard.back") }));
    await user.selectOptions(screen.getByLabelText(t("metering.premises.field.area")), "DTWN");
    await toStepTwo(user);
    await waitFor(() => {
      expect(calls.at(-1)?.areas).toEqual(["DTWN"]);
    });
  });
});

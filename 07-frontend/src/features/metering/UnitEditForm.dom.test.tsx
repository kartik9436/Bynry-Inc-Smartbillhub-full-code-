// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Drawn:   04-docs/05-modules/04-metering/conformance/CR-089-p087-edit-a-unit.md
//          — `U10`, blueprint pages 87-90.
// Defects: DEF-MET-4762 (the form told a clerk a unit never moves, a year after
//          the rule changed) · DEF-MET-4763 (the frame was never diffed against
//          the built form) · DEF-MET-4731 (two forms for one unit).
// Rules:   BR-MET-118 (a unit's services ARE its premises', inherited LIVE —
//          PO 2026-09-10) · BR-MET-095 (a unit MAY move) · BR-MET-101 (a common
//          area is a unit with a flag) · BR-MET-1162 (a unit may carry its own
//          point) · B14 rule 31 (no database id is a visible value) · B14 rule
//          32 (one sentence per section) · B14 rule 37 (a drawn figure is an
//          illustration, never a fact to build to)
// ───────────────────────────────────────────────────────
// **WHAT THIS ASSERTS AND WHAT IT DELIBERATELY DOES NOT.**
//
// Nothing in this repository reads rendered output, so *the screen matches its
// drawing* is a person's job and stays one. What a test CAN hold is the part of
// a drawing that is structural — which groups exist, in which order, what kind
// of control answers each question, and which sentences are on screen. That is
// the half of `DEF-MET-4763` that can go red on its own, and it is the half
// that rotted: four waves each added a field from a task sentence and no lane
// owned the shape.
//
// ⚠ **AND ONE SENTENCE HERE IS A PROMISE ABOUT THE SERVER, NOT ABOUT THE
// SCREEN.** *"These come from the building"* is `BR-MET-118`'s inheritance
// claim, and a screen that promised it over a stored copy would be hard-won law
// 1 exactly. The claim is verified where it lives — `unit_detail_dict` reads
// `unit.premises.services_available` at read time and `units` has no services
// column in the model or in any migration — and what this file can add is that
// the screen renders the payload's list rather than anything of its own.
//
// ⚠ **PROVED RED FIRST (hard-won law 7), through `vitest run`.** Against the
// pre-fix form every case fails, and the messages are the specification:
//   · groups: `expected [] to deeply equal [ 'name', 'where', 'capacity', … ]`
//   · the retired sentence: `expected '…A unit never moves between premises. To
//     relocate it, deactivate it and create it under the other premise.…' not
//     to contain 'never moves between premises'`
//   · common area: `Unable to find a label with the text of: /This is a common
//     area/` — it was a tick-box on the OTHER form and absent from this one
//   · the title: `expected 'Edit unit U-00501' to be 'Edit Unit 2'`
//   · the point offer: `Unable to find an accessible element with the role
//     "button" and name "Give this unit its own point"`
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { CityGisState } from "@/api/endpoints";
import { cityGisQueryKey } from "@/features/metering/CityGis";
import type { UnitRow } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { UNIT_FORM_SECTIONS, UnitEditModal } from "./UnitEditModal";

const TENANT = "brazosbend";

/** ⚠ Every figure here is the FIXTURE's, never the blueprint's — B14 rule 37,
 *  PO 2026-09-10: *"Treat every number drawn in a wireframe as an illustration,
 *  never a fact to build to."* */
function unit(over: Partial<UnitRow> = {}): UnitRow {
  return {
    id: "u-501",
    unit_no: "U-00501",
    premises_id: "p-101",
    premise_no: "P-00101",
    premise_address: "1408 Bluestem Ln",
    label: "2",
    unit_type: "residential",
    floor_label: "Ground",
    square_feet: 820,
    rate_plan_id: null,
    plan_effective_from: null,
    plan_locked: false,
    vacant_standby_auto: false,
    is_common_area: false,
    services: ["electric", "water"],
    lat: null,
    lng: null,
    point: { lat: "30.752104", lng: "-98.238391", source: "premises" },
    active: true,
    metered_services: [],
    meters: [],
    occupancy: "occupied",
    occupant: "Dana Whitfield",
    account_no: "A-90001",
    status: "active",
    sub_metered: false,
    ...over,
  };
}

interface Sent {
  url: string;
  method: string;
  body: string;
}

function mountForm(row: UnitRow, sent: Sent[] = [], city: CityGisState = "working") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  // GIS Lane D (`DEF-MET-10003`, 2026-10-07) — *Where it is* is the unit's own
  // CITY point and is drawn only where a City GIS is in use. Every case below
  // that reads it is a utility WITH one; the answer is seeded so the form draws
  // on its first render, exactly as it does once the state read has answered.
  queryClient.setQueryData(cityGisQueryKey, { state: city, message_key: null });
  const client = createApiClient({
    tenant: TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      sent.push({
        url,
        method: String(init?.method ?? "GET").toUpperCase(),
        body: String(init?.body ?? ""),
      });
      return new Response(JSON.stringify(url.includes("/plans") ? { results: [], count: 0 } : row), {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    },
  });
  // Mounted under the real path pattern (hard-won law 2) — this form's own
  // links and its plan picker both read `useParams().tenant`.
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}/premises/units/${row.id}`]}>
          <Routes>
            <Route
              path="/:tenant/premises/units/:unitId"
              element={
                <UnitEditModal
                  unit={row}
                  client={client}
                  regional={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}
                  onClose={() => undefined}
                  onSaved={() => undefined}
                />
              }
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("U10 — the drawn shape of the unit edit form", () => {
  it("draws the four drawn groups, in the drawn order", () => {
    mountForm(unit());
    const groups = [...document.querySelectorAll("[data-unit-section]")].map((node) =>
      node.getAttribute("data-unit-section"),
    );
    expect(groups).toEqual(UNIT_FORM_SECTIONS.map((section) => section.id));
    // The headings a clerk actually reads, not the ids a test does.
    expect(screen.getByText("What this unit is called")).toBeInTheDocument();
    expect(screen.getByText(/Where it is/)).toBeInTheDocument();
    expect(screen.getByText("What it can take")).toBeInTheDocument();
    expect(screen.getByText(/What it is charged on/)).toBeInTheDocument();
  });

  it("B14 rule 31 — the title is what is written on the door, not the series number", () => {
    mountForm(unit());
    // ⚠ **`Edit {{unit}}` AND NOT THE DRAWN `Edit Unit 2`.** A browser walk
    // read `Edit Unit Unit B` on real data — this product's unit labels
    // already carry the noun (`Unit A`, `Suite 200`, `Master`, `Apt 101`),
    // which the frame's bare `2` does not. The label is the deliverable; the
    // word in front of it was the frame's example, not its rule.
    expect(screen.getByText("Edit 2")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("Edit Unit 2");
    expect(screen.queryByText(/U-00501/)).toBeNull();
  });

  it("DEF-MET-4762 — the undrawn Premise field is gone, and its retired sentence with it", () => {
    mountForm(unit());
    // ⚠ **THE FIELD IS ASSERTED, NOT ONLY THE SENTENCE, AND THAT IS THE WHOLE
    // POINT OF THIS CASE.** Written as a text assertion alone it PASSED on the
    // pre-fix form — because the catalogue key had already been retired in the
    // same change, so the old field rendered its help as nothing. A check whose
    // green depends on the order two edits landed in is not a check. The FIELD
    // is structural and cannot go quiet.
    expect(screen.queryByLabelText(/^Premise/)).toBeNull();
    // `BR-MET-095` superseded `BR-MET-046` on 2026-08-21 and `MoveUnitModal`
    // shipped with it. The form went on giving advice for a door that existed.
    expect(document.body.textContent).not.toContain("never moves between premises");
    expect(document.body.textContent).not.toContain("deactivate it and create it");
  });

  it("BR-MET-118 — the services are the BUILDING's, read-only, and the form says so", () => {
    mountForm(unit({ services: ["electric", "water"] }));
    // No control: not a picker, not a chip with an ✕, nothing that writes.
    expect(screen.queryByLabelText(/Utility services/)).toBeNull();
    expect(
      screen.getByText("These come from the building. Change them there."),
    ).toBeInTheDocument();
    // And what it renders is the PAYLOAD's list rather than anything of its
    // own. Asserted on the accessible NAME, not on the letter square: `E` and
    // `W` are what a sighted reader sees and neither is a service.
    const badges = screen.getAllByRole("img");
    expect(badges.map((badge) => badge.getAttribute("aria-label"))).toEqual([
      "Electric",
      "Water",
    ]);
  });

  it("BR-MET-101 — common area is a question with its answer in WORDS", () => {
    mountForm(unit());
    // The frame's own reasoning: *"a question with an answer in words, not a
    // tick-box, because it changes who gets billed."*
    const field = screen.getByLabelText(/This is a common area/) as HTMLSelectElement;
    expect(field.tagName).toBe("SELECT");
    expect([...field.options].map((option) => option.textContent)).toEqual([
      "No — it is a unit somebody lives in",
      "Yes — shared space that bills the owner",
    ]);
    expect(field.value).toBe("no");
  });

  it("BR-MET-1162 — the point is an OFFER, and it says whose point is in force", async () => {
    const user = userEvent.setup();
    mountForm(unit());
    expect(
      screen.getByText("Using 1408 Bluestem Ln's point — 30.752104, -98.238391"),
    ).toBeInTheDocument();
    // Two empty boxes on every unit would imply every unit ought to have them.
    expect(screen.queryByLabelText(/Latitude/)).toBeNull();

    await user.click(screen.getByRole("button", { name: "Give this unit its own point" }));
    expect(screen.getByLabelText(/Latitude/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Longitude/)).toBeInTheDocument();
    // The sentence moves with the offer, or the button reads as dead.
    expect(screen.getByText(/This unit has its own point/)).toBeInTheDocument();
  });

  it("DEF-MET-10003 — no City GIS: no Where it is, and saving sends no point", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mountForm(
      unit({ lat: "30.751880", lng: "-98.238004", point: { lat: "30.751880", lng: "-98.238004", source: "unit" } }),
      sent,
      "none",
    );
    const groups = [...document.querySelectorAll("[data-unit-section]")].map((node) =>
      node.getAttribute("data-unit-section"),
    );
    expect(groups).toEqual(
      UNIT_FORM_SECTIONS.map((section) => section.id).filter((id) => id !== UNIT_FORM_SECTIONS[1].id),
    );
    expect(screen.queryByText(/Where it is/)).toBeNull();
    expect(screen.queryByLabelText(/Latitude/)).toBeNull();
    await user.selectOptions(screen.getByLabelText(/This is a common area/), "yes");
    await user.click(screen.getByRole("button", { name: "Save changes ✓" }));
    const writes = sent.filter((call) => call.method === "PATCH");
    expect(writes).toHaveLength(1);
    const body = JSON.parse(writes[0].body) as Record<string, unknown>;
    // The stored point is not cleared by a form that never drew it.
    expect("lat" in body).toBe(false);
    expect("lng" in body).toBe(false);
  });

  it("a unit that already carries its own point is offered the building's back", () => {
    mountForm(
      unit({
        lat: "30.751880",
        lng: "-98.238004",
        point: { lat: "30.751880", lng: "-98.238004", source: "unit" },
      }),
    );
    expect(screen.getByText(/This unit has its own point/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Use the building's point" })).toBeInTheDocument();
  });

  it("one PATCH carries the label, the flag and the point — never two writes", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mountForm(unit(), sent);

    await user.click(screen.getByRole("button", { name: "Give this unit its own point" }));
    await user.type(screen.getByLabelText(/Latitude/), "30.751880");
    await user.type(screen.getByLabelText(/Longitude/), "-98.238004");
    await user.selectOptions(screen.getByLabelText(/This is a common area/), "yes");
    await user.click(screen.getByRole("button", { name: "Save changes ✓" }));

    const writes = sent.filter((call) => call.method === "PATCH");
    expect(writes).toHaveLength(1);
    const body = JSON.parse(writes[0].body) as Record<string, unknown>;
    expect(body.is_common_area).toBe(true);
    expect(body.lat).toBe("30.751880");
    expect(body.lng).toBe("-98.238004");
  });

  it("a form opened to fix a floor label sends NO coordinates at all", async () => {
    const user = userEvent.setup();
    const sent: Sent[] = [];
    mountForm(unit(), sent);

    await user.clear(screen.getByLabelText(/Floor$/));
    await user.type(screen.getByLabelText(/Floor$/), "First");
    await user.click(screen.getByRole("button", { name: "Save changes ✓" }));

    const body = JSON.parse(sent.filter((c) => c.method === "PATCH")[0].body) as Record<
      string,
      unknown
    >;
    // Sending them unchanged would write the same numbers back and stamp an
    // audit row for a change nobody made.
    expect("lat" in body).toBe(false);
    expect("lng" in body).toBe(false);
    expect(body.floor_label).toBe("First");
  });
});

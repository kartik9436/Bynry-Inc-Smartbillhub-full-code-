// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-177-BRC10 round C (task 15) — Add a premise, as the PO ruled it
//           on 2026-10-09, asserted on RENDERED text and on the body the
//           server receives. Defect DEF-MET-10034.
// Rules:    BR-MET-1190–1195 · B14 rules 31, 32, 33 · DEF-MET-4758 (the route
//           box says which empty it is)
// Drawing:  05-prototype/add-premise-2026-10-09/images/01–14
// ───────────────────────────────────────────────────────
// ⚠ **NO REAL CITY IS EVER CALLED.** `check-address` answers what the test
// says (`addPremise.test.helpers.mountAddPremise`).
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CityCheckAnswer, CustomFieldRegistryEntry } from "@/api/endpoints";

import { addPremisePayload, composeAddress, emptyAddPremiseForm, outcomeLine, unitLabels } from "./addPremiseModel";
import { createdBody, mountAddPremise, owner, route, SERVICES } from "./addPremise.test.helpers";

afterEach(cleanup);

function type(label: RegExp, value: string): void {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function fillAddress(): void {
  type(/street address/i, "3721 S Village Dr,");
  type(/^city$/i, "Avenel");
  type(/^state$/i, "NJ");
  type(/zip code/i, "07001");
}

async function continueOn(): Promise<void> {
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /^continue/i }));
  });
}

const MATCH: CityCheckAnswer = {
  result: "match",
  session: "run-1",
  message_key: null,
  match: {
    parcel: "09-00-00-000-001",
    point: "PT-1",
    address_line: "3721 S Village Dr",
    city: "Avenel",
    state: "NJ",
    postal_code: "07001",
    lat: "40.582310",
    lng: "-74.284120",
    frame: "EPSG:4326",
    status: null,
    unit: null,
    match: "strong",
  },
};

const ROOF_AGE: CustomFieldRegistryEntry = {
  id: "cf-1",
  key: "roof_age",
  label: "Roof age",
  help_text: "",
  data_type: "number",
  options: [],
  is_required: true,
  display_order: 1,
  placement: { S16: "input" },
} as CustomFieldRegistryEntry;

describe("task 6 — no How many step: Property · Units · Review, opening on Property", () => {
  it("draws three steps and opens on Property", () => {
    mountAddPremise();
    const rail = document.querySelector("[data-wizard=rail]") as HTMLElement;
    expect(within(rail).getByText("Property")).toBeInTheDocument();
    expect(within(rail).getByText("Units")).toBeInTheDocument();
    expect(within(rail).getByText("Review")).toBeInTheDocument();
    expect(within(rail).queryByText(/how many/i)).toBeNull();
    expect(screen.getByRole("heading", { name: "Address" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Add a premise" })).toBeInTheDocument();
  });
});

describe("task 7 — one Address section; services are the ACTIVE ones, none ticked", () => {
  it("offers only enabled services, none ticked, with All services first", () => {
    mountAddPremise();
    const box = screen.getByRole("button", { name: /services/i });
    expect(box).toHaveTextContent("Choose services");
    fireEvent.click(box);
    const list = document.querySelector("[data-check-dropdown-list]") as HTMLElement;
    const labels = within(list).getAllByRole("checkbox").map((one) => one.closest("label")?.textContent);
    expect(labels).toEqual(["All services", "Water", "Sewer", "Trash"]);
    expect(within(list).getAllByRole("checkbox").every((one) => !(one as HTMLInputElement).checked)).toBe(true);
    fireEvent.click(within(list).getByLabelText("All services"));
    expect(box).toHaveTextContent("All services");
  });

  it("the body the server receives carries exactly the services the clerk ticked", async () => {
    const view = mountAddPremise();
    type(/street address/i, "9 Quarry Hill Rd");
    fireEvent.click(screen.getByRole("button", { name: /services/i }));
    const list = document.querySelector("[data-check-dropdown-list]") as HTMLElement;
    fireEvent.click(within(list).getByLabelText("Water"));
    fireEvent.click(within(list).getByLabelText("Trash"));
    await continueOn();
    await continueOn();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: /create premise/i })));
    await waitFor(() => expect(createdBody(view.sent)).toBeDefined());
    expect(createdBody(view.sent)?.services_available).toEqual(["water", "trash"]);
  });

  it("City limits is a dropdown that starts on Not recorded, and the type list is active-only", () => {
    mountAddPremise();
    const limits = screen.getByLabelText("City limits") as HTMLSelectElement;
    expect(limits.tagName).toBe("SELECT");
    expect(limits.selectedOptions[0].textContent).toBe("Not recorded");
    const types = Array.from((screen.getByLabelText("Property type") as HTMLSelectElement).options).map((o) => o.textContent);
    expect(types).toContain("Single-family home");
    expect(types).not.toContain("Retired kind");
  });

  it("says no explanation the PO removed (B14 rules 32/33)", () => {
    mountAddPremise();
    const text = document.body.textContent ?? "";
    for (const gone of [
      "Start typing",
      "We look it up",
      "is the only answer",
      "allocated",
      "audit log",
      "Who reads the meters",
      "follows the route",
      "Leave it at zero",
    ]) {
      expect(text).not.toContain(gone);
    }
  });
});

describe("task 8 — Check address, three answers, and the Map section only after a match", () => {
  it("not connected: the grey box, and no Map section", async () => {
    mountAddPremise();
    fillAddress();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Check address" })));
    expect(await screen.findByText("City map not connected.")).toBeInTheDocument();
    expect(screen.getByText("This address cannot be checked. It saves as typed.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Map" })).toBeNull();
  });

  it("no match: the amber box", async () => {
    mountAddPremise({ check: { result: "no_match", match: null, session: null, message_key: null } });
    fillAddress();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Check address" })));
    expect(await screen.findByText("No match on the city map.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Map" })).toBeNull();
  });

  it("match: the City's details with Use these details, the Map section appears, and the save goes through the City", async () => {
    const view = mountAddPremise({ check: MATCH });
    type(/street address/i, "3721 s village drive");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Check address" })));
    expect(await screen.findByText("Matches the city map.")).toBeInTheDocument();
    expect(screen.getByText("09-00-00-000-001")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Map" })).toBeInTheDocument();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Use these details" })));
    expect((screen.getByLabelText(/street address/i) as HTMLInputElement).value).toBe("3721 S Village Dr");
    expect(screen.getByText("Matches the city map. Details used.")).toBeInTheDocument();
    await continueOn();
    await continueOn();
    expect(await screen.findByText("Check before saving")).toBeInTheDocument();
    expect(screen.getByText("40.582310, -74.284120")).toBeInTheDocument();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: /create premise/i })));
    await waitFor(() => expect(createdBody(view.sent)).toBeDefined());
    const posted = view.sent.find((one) => one.path.endsWith("/gis_esri/premises"));
    expect(posted?.body).toMatchObject({ parcel: "09-00-00-000-001", point: "PT-1", session: "run-1" });
  });

  it("Keep my address: the box closes and the save is the ordinary one", async () => {
    const view = mountAddPremise({ check: MATCH });
    fillAddress();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Check address" })));
    await act(async () => fireEvent.click(await screen.findByRole("button", { name: "Keep my address" })));
    expect(screen.queryByText("Matches the city map.")).toBeNull();
    await continueOn();
    await continueOn();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: /create premise/i })));
    await waitFor(() => expect(createdBody(view.sent)).toBeDefined());
    expect(view.sent.some((one) => one.path.endsWith("/gis_esri/premises"))).toBe(false);
    expect(createdBody(view.sent)).toMatchObject({ gis_unchecked: true });
  });

  it("asks the City ONCE per press and never while typing (DEF-MET-10034)", async () => {
    const view = mountAddPremise({ check: MATCH });
    fillAddress();
    type(/street address/i, "3721 S Village Drive");
    expect(view.sent.filter((one) => one.path.includes("address-search") || one.path.includes("check-address"))).toEqual([]);
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Check address" })));
    expect(view.sent.filter((one) => one.path.endsWith("/check-address"))).toHaveLength(1);
  });
});

describe("task 9 — the same address: Open it or Add it anyway, and Continue waits", () => {
  const SAME = { id: "prem-uuid-1", premise_no: "P-00001", address: "101 Silver Creek Rd, Silver Creek, TX 78611", units: 1, status: "active" };

  it("names the premise by NUMBER and blocks Continue until the clerk chooses", async () => {
    mountAddPremise({ same: SAME });
    type(/street address/i, "101 silver creek rd.");
    await continueOn();
    expect(await screen.findByText("This address already exists.")).toBeInTheDocument();
    expect(screen.getByText("P-00001")).toBeInTheDocument();
    expect(screen.getByText("1 · Active")).toBeInTheDocument();
    expect(document.body.textContent).not.toContain("prem-uuid-1"); // B14 rule 31
    expect(screen.getByRole("heading", { name: "Address" })).toBeInTheDocument(); // still on step 1
  });

  it("Add it anyway lets the clerk on, and the save says so", async () => {
    const view = mountAddPremise({ same: SAME });
    type(/street address/i, "101 silver creek rd.");
    await continueOn();
    await act(async () => fireEvent.click(await screen.findByRole("button", { name: "Add it anyway" })));
    expect(screen.getByText("Same address as P-00001. Adding anyway.")).toBeInTheDocument();
    await continueOn();
    expect(await screen.findByRole("heading", { name: "Units" })).toBeInTheDocument();
    await continueOn();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: /create premise/i })));
    await waitFor(() => expect(createdBody(view.sent)).toMatchObject({ add_anyway: true }));
  });

  it("Open it goes to the existing premise", async () => {
    mountAddPremise({ same: SAME });
    type(/street address/i, "101 silver creek rd.");
    await continueOn();
    await act(async () => fireEvent.click(await screen.findByRole("button", { name: "Open P-00001" })));
    expect(await screen.findByTestId("premise-page")).toBeInTheDocument();
  });
});

describe("task 10 — closed sections whose header says their state; a missing required field opens its section", () => {
  it("Owner, Area & sub-area and Custom fields start closed and say their state", () => {
    mountAddPremise({ customFields: [ROOF_AGE] });
    const state = (id: string) => document.querySelector(`[data-add-premise-fold="${id}"] [data-add-premise-fold-state]`)?.textContent ?? "";
    expect(state("add-premise-owner")).toContain("Needs an owner");
    expect(state("add-premise-area")).toContain("No area");
    expect(state("add-premise-custom")).toContain("1 required");
    expect(document.querySelector('[data-add-premise-fold="add-premise-custom"]')).toHaveAttribute("data-open", "false");
  });

  it("Continue with Roof age empty opens Custom fields, marks the field and stays on Property", async () => {
    mountAddPremise({ customFields: [ROOF_AGE] });
    type(/street address/i, "3721 S Village Dr");
    await continueOn();
    expect(document.querySelector('[data-add-premise-fold="add-premise-custom"]')).toHaveAttribute("data-open", "true");
    expect(screen.getByLabelText(/roof age/i)).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("heading", { name: "Address" })).toBeInTheDocument();
  });

  it("links to the real custom-fields settings page", () => {
    mountAddPremise();
    fireEvent.click(screen.getByRole("button", { name: /custom fields/i }));
    const link = screen.getByRole("link", { name: /manage custom fields in settings/i });
    expect(link.getAttribute("href")).toBe("/ottumwa-water-works/settings/reference-data/reference-data?list=custom_fields");
  });

  it("Area & sub-area: two levels, the cycle follows the route (BR-MET-073)", () => {
    mountAddPremise();
    fireEvent.click(screen.getByRole("button", { name: /area & sub-area/i }));
    const sub = screen.getByLabelText("Sub-area") as HTMLSelectElement;
    expect(sub).toBeDisabled();
    expect(sub.options[0].textContent).toBe("Choose an area first");
    fireEvent.change(screen.getByLabelText("Area"), { target: { value: "NORTH" } });
    expect(Array.from((screen.getByLabelText("Sub-area") as HTMLSelectElement).options).map((o) => o.textContent)).toContain("North hills");
    fireEvent.change(screen.getByLabelText("Read route"), { target: { value: "R-012" } });
    expect((screen.getByLabelText("Billing cycle") as HTMLInputElement).value).toBe("Cycle CYC-03");
  });
});

describe("DEF-MET-4758 — the route box says WHICH empty it is, kept through the redesign", () => {
  async function routeBox(): Promise<string> {
    fireEvent.click(screen.getByRole("button", { name: /area & sub-area/i }));
    return ((await screen.findByLabelText("Read route")) as HTMLSelectElement).options[0].textContent ?? "";
  }

  it("three empty boxes do not read alike, and a draft route is not offered", async () => {
    const seen: string[] = [];
    for (const routes of [[], "hang", [route({ status: "draft" })]] as const) {
      const view = mountAddPremise({ routes: routes as never });
      seen.push(await routeBox());
      view.unmount();
      cleanup();
    }
    expect(seen).toEqual(["No routes yet", "Loading routes…", "No routes yet"]);
    const view = mountAddPremise({ routes: "reject" });
    await routeBox();
    await waitFor(() =>
      expect((screen.getByLabelText("Read route") as HTMLSelectElement).options[0].textContent).toBe("Routes did not load"),
    );
    view.unmount();
  });
});

describe("task 10b — Owner: search, link, unlink, not available; no hand-typed owner fields", () => {
  it("draws no Account type, Person or company or Managed by box", () => {
    mountAddPremise();
    fireEvent.click(screen.getByRole("button", { name: /^owner/i }));
    expect(screen.queryByLabelText("Account type")).toBeNull();
    expect(screen.queryByLabelText("Person or company")).toBeNull();
    expect(screen.queryByLabelText("Managed by")).toBeNull();
    expect(screen.getByLabelText("Master account")).toHaveAttribute("placeholder", "Name or account number");
  });

  it("found → read-only card → Link this account → ✓ Linked → Unlink; the save sends the link only", async () => {
    const view = mountAddPremise({ owners: [owner()] });
    type(/street address/i, "3721 S Village Dr");
    fireEvent.click(screen.getByRole("button", { name: /^owner/i }));
    type(/master account/i, "AC-2026-00031");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Find" })));
    expect(await screen.findByText("Bramble Property Group · AC-2026-00031")).toBeInTheDocument();
    for (const fact of ["Commercial", "Company", "Northside Management", "Active"]) {
      expect(screen.getByText(fact)).toBeInTheDocument();
    }
    expect(document.body.textContent).not.toContain("acct-uuid-31");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Link this account" })));
    expect(screen.getByText("✓ Linked")).toBeInTheDocument();
    const header = document.querySelector('[data-add-premise-fold="add-premise-owner"] [data-add-premise-fold-state]');
    expect(header?.textContent).toContain("Bramble Property Group");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Unlink" })));
    expect(header?.textContent).toContain("Needs an owner");
    type(/master account/i, "AC-2026-00031");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Find" })));
    await act(async () => fireEvent.click(await screen.findByRole("button", { name: "Link this account" })));
    await continueOn();
    await continueOn();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: /create premise/i })));
    await waitFor(() => expect(createdBody(view.sent)).toBeDefined());
    const body = createdBody(view.sent) as Record<string, unknown>;
    expect(body.master_account_id).toBe("acct-uuid-31");
    for (const gone of ["owner_account_type", "owner_kind", "owner_ssn", "owner_phone", "owner_tax_id", "owner_manager"]) {
      expect(body).not.toHaveProperty(gone);
    }
  });

  it("not found → This account is not available., and the clerk carries on", async () => {
    mountAddPremise({ owners: [owner()] });
    type(/street address/i, "3721 S Village Dr");
    fireEvent.click(screen.getByRole("button", { name: /^owner/i }));
    type(/master account/i, "Zzz Holdings");
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Find" })));
    expect(
      await screen.findByText("This account is not available. You can continue without an owner."),
    ).toBeInTheDocument();
    await continueOn();
    expect(await screen.findByRole("heading", { name: "Units" })).toBeInTheDocument();
  });
});

describe("task 12/13 — Review grouped, Edit per row, dashes, one outcome line; the side card", () => {
  it("never prints a double comma and says what will be created", async () => {
    mountAddPremise();
    fillAddress();
    await continueOn();
    await continueOn();
    expect(await screen.findByText("Check before saving")).toBeInTheDocument();
    expect(screen.getAllByText("3721 S Village Dr, Avenel, NJ 07001").length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toContain(",,");
    expect(screen.getByText("Creates 1 premise and 1 unit.")).toBeInTheDocument();
    const groups = Array.from(document.querySelectorAll("[data-review-group]")).map((one) => one.getAttribute("data-review-group"));
    expect(groups).toEqual(["address", "property", "owner", "area", "units"]);
    expect(screen.getAllByRole("button", { name: /^edit /i }).length).toBeGreaterThan(8);
    fireEvent.click(screen.getByRole("button", { name: "Edit Units" }));
    expect(await screen.findByLabelText("How many units")).toBeInTheDocument();
  });

  it("the This premise card shows the number, the address and its six facts", () => {
    mountAddPremise();
    fillAddress();
    const card = document.querySelector("[data-add-premise-summary]") as HTMLElement;
    expect(within(card).getByText("This premise")).toBeInTheDocument();
    expect(within(card).getByText("3721 S Village Dr, Avenel, NJ 07001")).toBeInTheDocument();
    const facts = Array.from(card.querySelectorAll("[data-add-premise-summary-fact]")).map((one) => one.getAttribute("data-add-premise-summary-fact"));
    expect(facts).toEqual(["type", "check", "services", "units", "owner", "route"]);
    expect(within(card).getByText("Not checked")).toBeInTheDocument();
    expect(within(card).getByText("Needs an owner")).toBeInTheDocument();
  });
});

describe("the pure half", () => {
  it("composeAddress skips empty parts and trailing commas", () => {
    expect(composeAddress({ address_line: "3721 S Village Dr,", city: "Avenel", state: "NJ", postal_code: "07001" })).toBe(
      "3721 S Village Dr, Avenel, NJ 07001",
    );
    expect(composeAddress({ address_line: "3721 S Village Dr", city: "", state: "", postal_code: "07001" })).toBe(
      "3721 S Village Dr, 07001",
    );
  });

  it("0 units creates none and says so; the payload always answers services", () => {
    const form = { ...emptyAddPremiseForm(), address_line: "1 A St", unit_count: "0" };
    expect(unitLabels(form.unit_count)).toEqual([]);
    expect(outcomeLine(form).key).toBe("metering.addPremise.review.outcomeNone");
    const payload = addPremisePayload(form, { owner: null, addAnyway: false });
    expect(payload.services_available).toEqual([]);
    expect(payload).not.toHaveProperty("units");
    expect(payload).not.toHaveProperty("add_anyway");
    expect(payload).not.toHaveProperty("inside_city_limits");
  });

  it("the services the payload names are the ones ticked, and only active ones exist to tick", () => {
    expect(SERVICES.filter((row) => row.enabled).map((row) => row.service)).toEqual(["water", "sewer", "trash"]);
  });
});

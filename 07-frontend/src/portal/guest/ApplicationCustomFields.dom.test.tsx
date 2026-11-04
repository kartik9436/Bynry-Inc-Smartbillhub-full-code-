// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Change:   CR-161-BRC10 wave W7 — the utility's own questions on the portal
//           new-service form (CWP-047 steps 2 and 3, CWP-009 step 4).
// Rules:    PO 2026-10-02 Part 2 row 16 · *"Required means required only
//           where it's typed in"* · `DEF-CWP-9215` (an error tied to its box
//           and announced — accessibility questions 3 and 7)
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
//   * *"a utility that asks nothing draws nothing"* passes on a screen that
//     never renders the block at all — so the asking case is in the same file
//     and finds the box by its label;
//   * *"the answer is sent"* passes on a payload that always carries
//     `custom_data` — so the no-questions case asserts the key is ABSENT;
//   * *"the error is announced"* passes on any element with text — so the
//     box's own `aria-describedby` is followed to the element that holds the
//     sentence, and that element must be a live region.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ApiError } from "@/api/client";

import type { ApplicationDraft, Availability, PortalCustomField } from "../api/guestClient";

const t = (key: string): string => i18n.t(key);

let draft: ApplicationDraft;
let saves: Record<string, unknown>[] = [];
let saveRefusal: ApiError | null = null;
let submitRefusal: ApiError | null = null;

vi.mock("../api/guestClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/guestClient");
  return {
    ...actual,
    getDraft: async () => draft,
    saveDraft: async (_token: string, patch: Record<string, unknown>) => {
      saves.push(patch);
      if (saveRefusal !== null) throw saveRefusal;
      const custom = patch.custom_data as ApplicationDraft["custom_data"] | undefined;
      draft = { ...draft, ...(custom ? { custom_data: custom } : {}) };
      return draft;
    },
    getAvailability: async (): Promise<Availability> => AVAILABILITY,
    submitApplication: async () => {
      if (submitRefusal !== null) throw submitRefusal;
      return { reference: "SR-26-0099", request_id: "r", consent_recorded: false, idempotent_replay: false };
    },
  };
});

const { ApplyForServiceBody } = await import("./ApplyForService");

const AVAILABILITY: Availability = {
  matched: true,
  address: "2201 Cane Island Pkwy",
  job: "new_connection",
  rows: [
    {
      service_code: "water",
      service_name: "Water",
      available: true,
      to_connect: { kind: "amount", amount: "185.0000", display: "$185.00", currency: "USD" },
      deposit: { kind: "amount", amount: "150.0000", display: "$150.00", currency: "USD" },
    },
  ],
  if_you_apply: {
    before_we_start: { kind: "amount", amount: "185.0000", display: "$185.00", currency: "USD" },
    on_first_bill: { kind: "amount", amount: "150.0000", display: "$150.00", currency: "USD" },
    working_days: 2,
  },
};

const ROOF: PortalCustomField = {
  key: "roof_material",
  label: "Roof Material",
  help_text: "",
  data_type: "select",
  options: ["Metal", "Tile", "Shingle"],
  is_required: true,
};
const NAME: PortalCustomField = {
  key: "preferred_name",
  label: "Preferred name",
  help_text: "",
  data_type: "text",
  options: [],
  is_required: false,
};

const BASE: ApplicationDraft = {
  token: "draft-token",
  address_as_given: "2201 Cane Island Pkwy",
  address_unit_as_given: null,
  service_codes: ["water"],
  applicant_kind: "person",
  first_name: "Amara",
  last_name: "Okafor",
  company_name: null,
  email: "amara@example.test",
  phone: "(281) 555-0144",
  date_of_birth: null,
  tax_id: null,
  requested_start: "2026-10-30",
  submitted: false,
  reference: null,
  document_requirements: ["photo_id", "proof_of_address"],
  // `DEF-CWP-9818` — the applicant's category (REQUIRED) and the offered list.
  account_type_code: "residential",
  account_subtype_code: null,
  categories: [
    { code: "residential", name: "Residential", subcategories: [{ code: "single_family", name: "Single-family" }] },
    { code: "commercial", name: "Commercial", subcategories: [{ code: "healthcare", name: "Healthcare" }] },
    { code: "industrial", name: "Industrial", subcategories: [] },
  ],
};

function draw() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/brazosbend/portal/start-service/draft-token"]}>
        <Routes>
          <Route path="/:tenant/portal/start-service/:draft" element={<ApplyForServiceBody />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  saves = [];
  saveRefusal = null;
  submitRefusal = null;
});
afterEach(cleanup);

describe("CR-161 W7 · a utility that asks nothing", () => {
  it("draws no question block and sends no custom_data key", async () => {
    draft = { ...BASE, requested_start: null, custom_fields: { customers: [], accounts: [], premises: [] } };
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-step="when"]')).not.toBeNull());
    expect(container.querySelector("[data-portal-questions]")).toBeNull();
    // ⊕ DEF-CUS-10250 — *person or business* moved to About you (image 04),
    // so the save this case watches is the start date's, typed in the
    // product's date picker.
    fireEvent.change(container.querySelector('[data-step="when"] #requested_start') as Element, {
      target: { value: "12/01/2026" },
    });
    await waitFor(() => expect(saves.length).toBeGreaterThan(0));
    expect(saves.every((patch) => !("custom_data" in patch))).toBe(true);
  });
});

describe("CR-161 W7 · the property's question on step 2", () => {
  beforeEach(() => {
    draft = {
      ...BASE,
      custom_fields: { customers: [], accounts: [], premises: [ROOF] },
      custom_data: {},
    };
  });

  it("is drawn with its label, required mark and the utility's options, and holds Continue", async () => {
    const { container } = draw();
    // A resumed draft with the required answer missing opens on step 2.
    await waitFor(() =>
      expect(container.querySelector('[data-portal-questions="premises"]')).not.toBeNull(),
    );
    const box = screen.getByLabelText(/Roof Material/) as HTMLSelectElement;
    expect(box.tagName).toBe("SELECT");
    expect(box).toHaveAttribute("aria-required", "true");
    expect([...box.options].map((o) => o.textContent)).toEqual([
      t("portal.apply.questions.choose"),
      "Metal",
      "Tile",
      "Shingle",
    ]);
    const go = container.querySelector('[data-action="continue"]') as HTMLButtonElement;
    expect(go.disabled).toBe(true);
    expect(container.querySelector('[data-step-held="property_questions"]')?.textContent).toBe(
      t("portal.apply.held.questions"),
    );
  });

  it("a box left blank says so on the box, tied to it and announced", async () => {
    const { container } = draw();
    await waitFor(() =>
      expect(container.querySelector('[data-portal-questions="premises"]')).not.toBeNull(),
    );
    const box = screen.getByLabelText(/Roof Material/);
    fireEvent.focus(box);
    fireEvent.blur(box);
    await waitFor(() => expect(box).toHaveAttribute("aria-invalid", "true"));
    const describedBy = box.getAttribute("aria-describedby") ?? "";
    const line = document.getElementById(describedBy);
    expect(line?.textContent).toBe(t("portal.apply.questions.required"));
    expect(line).toHaveAttribute("aria-live", "polite");
  });

  it("choosing Tile saves it as the property's answer and frees Continue", async () => {
    const { container } = draw();
    await waitFor(() =>
      expect(container.querySelector('[data-portal-questions="premises"]')).not.toBeNull(),
    );
    fireEvent.change(screen.getByLabelText(/Roof Material/), { target: { value: "Tile" } });
    await waitFor(() =>
      expect(saves.at(-1)?.custom_data).toEqual({ premises: { roof_material: "Tile" } }),
    );
    await waitFor(() =>
      expect((container.querySelector('[data-action="continue"]') as HTMLButtonElement).disabled).toBe(
        false,
      ),
    );
  });

  it("a refused answer is printed on its own box, not on the start date", async () => {
    saveRefusal = new ApiError(422, {
      code: "VAL-002",
      message_key: "customFields.invalid",
      params: {},
      field_errors: [
        {
          field: "custom_data.premises.roof_material",
          code: "VAL-005",
          message_key: "customFields.option_unknown",
          params: { value: "Thatch" },
        },
      ],
    });
    const { container } = draw();
    await waitFor(() =>
      expect(container.querySelector('[data-portal-questions="premises"]')).not.toBeNull(),
    );
    fireEvent.change(screen.getByLabelText(/Roof Material/), { target: { value: "Tile" } });
    await waitFor(() =>
      expect(container.querySelector('[data-field-error="cf-premises-roof_material"]')).not.toBeNull(),
    );
    expect(container.querySelector('[data-field-error="requested_start"]')).toBeNull();
  });
});

describe("CR-161 W7 · step 3 and step 4", () => {
  it("the applicant's question is on step 3, and Check and send restates both answers", async () => {
    draft = {
      ...BASE,
      custom_fields: { customers: [NAME], accounts: [], premises: [ROOF] },
      custom_data: { premises: { roof_material: "Tile" }, customers: { preferred_name: "Ama" } },
    };
    const { container } = draw();
    // Complete: opens on Check and send.
    await waitFor(() => expect(container.querySelector('[data-screen="CWP-009"]')).not.toBeNull());
    expect(container.querySelector('[data-kv="cf-premises-roof_material"]')?.textContent).toContain(
      "Tile",
    );
    expect(
      container.querySelector('[data-kv="cf-customers-preferred_name"]')?.textContent,
    ).toContain("Ama");
    fireEvent.click(container.querySelector('[data-change="about"]') as Element);
    await waitFor(() =>
      expect(container.querySelector('[data-portal-questions="customers"]')).not.toBeNull(),
    );
    expect((screen.getByLabelText(/Preferred name/) as HTMLInputElement).value).toBe("Ama");
    expect(container.querySelector('[data-portal-questions="premises"]')).toBeNull();
  });

  it("Send refused on the property's questions takes the applicant back to the box, marked", async () => {
    draft = {
      ...BASE,
      custom_fields: { customers: [], accounts: [], premises: [ROOF] },
      custom_data: { premises: { roof_material: "Tile" } },
    };
    submitRefusal = new ApiError(422, {
      code: "VAL-003",
      message_key: "portal.application.stepIncomplete",
      params: { step: "property_questions" },
    });
    const { container } = draw();
    await waitFor(() => expect(container.querySelector('[data-screen="CWP-009"]')).not.toBeNull());
    // The utility made it required after it was answered blank on the server:
    draft = { ...draft, custom_data: {} };
    fireEvent.click(container.querySelector('[data-action="send"]') as Element);
    await waitFor(() => expect(container.querySelector('[data-action="fix-step"]')).not.toBeNull());
    fireEvent.click(container.querySelector('[data-action="fix-step"]') as Element);
    await waitFor(() =>
      expect(container.querySelector('[data-portal-questions="premises"]')).not.toBeNull(),
    );
  });
});

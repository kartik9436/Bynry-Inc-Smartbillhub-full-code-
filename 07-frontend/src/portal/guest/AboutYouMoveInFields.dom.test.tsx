// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defects: DEF-CUS-10250 — Portal apply asks Move-in's fields, in Move-in's
//          order, in the portal look (PO 2026-10-18, image 04-portal.png):
//          I'm applying as · first and last name · mobile phone (required) ·
//          email (OPTIONAL) · how should we contact you · date of birth (the
//          product's date picker) · last 4 of SSN · the co-applicant card · the
//          mailing block · Preferences (no autopay). NO category.
// Rules:   22-product-maintenance-process.md §6 — the portal's accessibility
//          questions: every control has a label, an error is tied to its input,
//          the form works from the keyboard, targets are at least 44px.
// ───────────────────────────────────────────────────────
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a box that is
// drawn and never saved (every case reads the LAST SAVE's patch, not the box);
// a native `type="date"` box hidden behind a picker (the visible box is asserted
// to be the text one); the bare component outside `/:tenant/portal/…` (it is
// mounted under the real path pattern, hard-won law 2's last clause).
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import i18n from "@/i18n";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { RELATIONSHIPS } from "@/features/customers/CoOwnerCards";

import type { ApplicationDraft, Availability } from "../api/guestClient";

let draft: ApplicationDraft;
let saves: Record<string, unknown>[] = [];

vi.mock("../api/guestClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/guestClient");
  return {
    ...actual,
    getDraft: async () => draft,
    saveDraft: async (_token: string, patch: Record<string, unknown>) => {
      saves.push(patch);
      draft = { ...draft, ...(patch as Partial<ApplicationDraft>) };
      return draft;
    },
    getAvailability: async (): Promise<Availability> => AVAILABILITY,
  };
});

const { ApplyForServiceBody } = await import("./ApplyForService");

const AVAILABILITY: Availability = {
  matched: true,
  address: "143 Willow Bend Dr",
  job: "new_connection",
  rows: [
    {
      service_code: "water",
      service_name: "Water",
      available: true,
      to_connect: { kind: "amount", amount: "0.0000", display: "$0.00", currency: "USD" },
      deposit: { kind: "amount", amount: "0.0000", display: "$0.00", currency: "USD" },
    },
  ],
  if_you_apply: null,
} as unknown as Availability;

/** Step 2 done (a start date), step 3 not begun — the draft opens on About you. */
function aboutDraft(): ApplicationDraft {
  return {
    token: "draft-token",
    address_as_given: "143 Willow Bend Dr",
    address_unit_as_given: null,
    service_address: "143 Willow Bend Dr, Ann Arbor, MI 48108",
    service_codes: ["water"],
    applicant_kind: "person",
    first_name: null,
    last_name: null,
    company_name: null,
    email: null,
    phone: null,
    date_of_birth: null,
    tax_id: null,
    requested_start: "2026-11-02",
    submitted: false,
    reference: null,
    document_requirements: ["photo_id", "proof_of_address"],
    locales: ["en", "es"],
  };
}

const t = (key: string, params?: Record<string, unknown>) => i18n.t(key, params) as string;

function draw() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <TenantRegionalProvider value={{ timeZone: "America/Detroit", dateFormat: "MM/DD/YYYY" }}>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/annarbor/portal/start-service/draft-token"]}>
          <Routes>
            <Route path="/:tenant/portal/start-service/:draft" element={<ApplyForServiceBody />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    </TenantRegionalProvider>,
  );
}

async function onAboutYou() {
  draw();
  await waitFor(() => expect(document.querySelector('[data-step="about"]')).not.toBeNull());
}

/** The fields the form sends, merged across every save so far. */
function sent(): Record<string, unknown> {
  return Object.assign({}, ...saves);
}

const box = (id: string) => document.querySelector(`#${id}`) as HTMLInputElement;
const continueButton = () => document.querySelector('[data-action="continue"]') as HTMLButtonElement;

beforeEach(() => {
  draft = aboutDraft();
  saves = [];
});
afterEach(cleanup);

describe("DEF-CUS-10250 · About you is Move-in's form in the portal look (image 04)", () => {
  it("draws the drawing's sections, in its order, and asks NO category", async () => {
    await onAboutYou();
    const order = [
      "[data-form-section=\"applying-as\"]",
      "[data-form-section=\"about-fields\"]",
      "[data-form-section=\"co-applicant\"]",
      "[data-form-section=\"mailing\"]",
      "[data-form-section=\"preferences\"]",
    ].map((selector) => document.querySelector(selector));
    for (const node of order) expect(node).not.toBeNull();
    for (let i = 1; i < order.length; i += 1) {
      expect(order[i - 1]!.compareDocumentPosition(order[i]!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    }
    expect(box("account_type_code")).toBeNull();
    expect(box("account_subtype_code")).toBeNull();
    // The service address on one line under a ticked *Same as service address*.
    expect(document.querySelector("[data-mailing-service-line]")?.textContent).toContain("143 Willow Bend Dr");
  });

  it("every control has a label a screen reader reads (accessibility question 1)", async () => {
    await onAboutYou();
    for (const label of [
      t("portal.apply.firstName"),
      t("portal.apply.lastName"),
      t("portal.apply.mobile"),
      t("portal.apply.email"),
      t("portal.apply.contactBy"),
      t("portal.apply.dateOfBirth"),
      t("portal.apply.ssnLast4"),
    ]) {
      expect(screen.getByLabelText(new RegExp(`^${label.replace(/[?()]/g, "\\$&")}`))).toBeInTheDocument();
    }
    expect(screen.getByRole("radiogroup", { name: t("portal.apply.applyingAs") })).toBeInTheDocument();
  });

  it("the date of birth is the product's date picker, never a native date box", async () => {
    await onAboutYou();
    expect(box("date_of_birth").type).toBe("text");
    expect(document.querySelector('[data-portal-date="date_of_birth"], [data-regional-date="MM/DD/YYYY"]')).not.toBeNull();
    expect(screen.getAllByRole("button", { name: /calendar/i }).length).toBeGreaterThan(0);
  });

  it("fills EVERY box and every one is saved with the value typed", async () => {
    const user = userEvent.setup();
    await onAboutYou();
    await user.type(box("first_name"), "Maria");
    await user.type(box("last_name"), "Lopez");
    await user.type(box("phone"), "(734) 555-0182");
    await user.type(box("email"), "maria.lopez@example.com");
    await user.selectOptions(box("contact_by"), "text");
    await user.type(box("date_of_birth"), "04/12/1988");
    await user.type(box("ssn_last4"), "4471");
    await user.click(box("co_applicant"));
    await user.type(box("co_applicant_name"), "Daniel Lopez");
    // DEF-CUS-10257 — chosen from Move-in's own list, never typed.
    expect(box("co_applicant_relationship").tagName).toBe("SELECT");
    expect(
      Array.from((box("co_applicant_relationship") as unknown as HTMLSelectElement).options)
        .map((option) => option.value)
        .filter(Boolean),
    ).toEqual([...RELATIONSHIPS]);
    await user.selectOptions(box("co_applicant_relationship"), "spouse");
    await user.type(box("co_applicant_phone"), "(734) 555-0144");
    await user.type(box("co_applicant_email"), "dan.lopez@example.com");
    await user.type(box("co_applicant_date_of_birth"), "09/30/1986");
    await user.click(box("mailing_same"));
    await user.type(box("mailing_line1"), "PO Box 2210");
    await user.type(box("mailing_city"), "Ypsilanti");
    await user.selectOptions(box("mailing_state"), "MI");
    await user.type(box("mailing_postal_code"), "48197");
    await user.click(box("preferences_on"));
    await user.selectOptions(box("pref_paperless"), "on");
    await user.selectOptions(box("pref_text_reminders"), "on");
    await user.selectOptions(box("pref_language"), "es");
    await user.click(box("first_name")); // leave the last box, which saves it
    await waitFor(() =>
      expect(sent()).toMatchObject({
        applicant_kind: "person",
        first_name: "Maria",
        last_name: "Lopez",
        phone: "(734) 555-0182",
        email: "maria.lopez@example.com",
        contact_by: "text",
        date_of_birth: "1988-04-12",
        ssn_last4: "4471",
        co_applicant: true,
        co_applicant_name: "Daniel Lopez",
        co_applicant_relationship: "spouse",
        co_applicant_phone: "(734) 555-0144",
        co_applicant_email: "dan.lopez@example.com",
        co_applicant_date_of_birth: "1986-09-30",
        mailing_same_as_service: false,
        mailing_line1: "PO Box 2210",
        mailing_city: "Ypsilanti",
        mailing_state: "MI",
        mailing_postal_code: "48197",
        paperless: true,
        text_reminders: true,
        preferred_language: "es",
      }),
    );
    // No category, and no autopay, is ever sent from the portal.
    expect(sent()).not.toHaveProperty("autopay");
    expect(continueButton()).not.toBeDisabled();
  });

  it("email is OPTIONAL: Continue is live with a name and a mobile number only", async () => {
    const user = userEvent.setup();
    await onAboutYou();
    expect(screen.getByText(t("portal.apply.optional"))).toBeInTheDocument();
    await user.type(box("first_name"), "Maria");
    await user.type(box("last_name"), "Lopez");
    expect(continueButton()).toBeDisabled();
    expect(document.querySelector('[data-step-held="contact"]')).not.toBeNull();
    await user.type(box("phone"), "(734) 555-0182");
    await waitFor(() => expect(continueButton()).not.toBeDisabled());
  });

  it("only the LAST FOUR of the SSN can be typed — digits, four of them", async () => {
    const user = userEvent.setup();
    await onAboutYou();
    await user.type(box("ssn_last4"), "123-45-6789");
    expect(box("ssn_last4").value).toBe("1234");
    expect(box("ssn")).toBeNull();
    expect(box("drivers_licence")).toBeNull();
  });

  it("a malformed email is named on its box, tied to it, and never sent (accessibility question 3)", async () => {
    const user = userEvent.setup();
    await onAboutYou();
    await user.type(box("email"), "maria@");
    await user.click(box("first_name"));
    const error = document.querySelector('[data-field-error="email"]');
    expect(error?.textContent).toBe(t("customers.form.emailInvalid"));
    // F-03 (`DEF-CWP-10548`): the box now names its helper line too; the
    // error is one of the lines it points at.
    expect(box("email").getAttribute("aria-describedby")?.split(" ")).toContain(error?.id);
    expect(box("email").getAttribute("aria-invalid")).toBe("true");
    expect(saves.some((patch) => patch.email === "maria@")).toBe(false);
  });

  it("a ticked co-applicant holds Continue until named, and says so", async () => {
    const user = userEvent.setup();
    await onAboutYou();
    await user.type(box("first_name"), "Maria");
    await user.type(box("last_name"), "Lopez");
    await user.type(box("phone"), "(734) 555-0182");
    await user.click(box("co_applicant"));
    await waitFor(() => expect(continueButton()).toBeDisabled());
    expect(document.querySelector('[data-step-held="co_applicant"]')?.textContent).toBe(
      t("portal.apply.held.coApplicant"),
    );
  });

  it("the header ticks and the folding card are keyboard controls with a 44px target (questions 2 and 4)", async () => {
    const user = userEvent.setup();
    await onAboutYou();
    const tick = box("co_applicant");
    tick.focus();
    await user.keyboard(" ");
    expect(tick.checked).toBe(true);
    expect(tick.closest("label")?.className).toContain("min-h-11");
    const toggle = document.querySelector("[data-co-applicant-toggle]") as HTMLButtonElement;
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    expect(toggle.className).toContain("min-h-11");
    toggle.focus();
    await user.keyboard("{Enter}");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
  });
});

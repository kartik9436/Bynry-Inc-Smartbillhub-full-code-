// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   **`REQ-03` six steps into four — PO approval 2026-09-29.** Lane
//           SCREEN-A, tasks 5–7: the Applicant step, Documents moved onto it,
//           and the Property step. Drawings:
//           `05-prototype/new-request-four-steps-2026-09-29/`.
// Defects:  `DEF-CUS-7850` (`+ Premises` drew in BOTH states and was a door out
//           of the wizard) · `DEF-CUS-7851` (two document buttons for one act)
// Rules:    B14 rule 33 · rule 42 · rule 43 · hard rule 8 · `BR-CUS-070` ·
//           `BR-CUS-092` · `BR-CUS-1022`
// Harness:  mounted under the REAL route pattern `/:tenant/requests/new`, so
//           `useTenantPath` builds `/brazosbend/…` and not `//…` — CLAUDE.md
//           hard-won law 2's fixture clause.
//
// ⚠ **EVERY CASE HERE READS RENDERED OUTPUT, NEVER A PROP.** The one class of
// defect this repo cannot otherwise see is *the screen does not match its
// design* — nearly half of everything that goes wrong on a screen — and a prop
// assertion cannot see it. Each case was proved RED first against a screen
// broken back to what it did on 2026-09-28; the broken forms are named in the
// lane report.
// ───────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";
import { createApiClient } from "@/api/client";

import { CAPTURE_STEPS, ServiceRequestCapturePage } from "./ServiceRequestCapturePage";
import { serviceAddressLines } from "./CaptureMailingAddressPanel";

afterEach(cleanup);

const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

const BALCONES = {
  id: "prem-1",
  premise_no: "P-0001",
  address_line: "1200 Balcones Dr",
  city: "Ottumwa",
  state: "Iowa",
  postal_code: "12365",
  services: null,
  units: [],
};

interface ServerOptions {
  premises?: readonly (typeof BALCONES)[];
  /** `DEF-CUS-10040` — the City's answer to *Check address*. */
  cityCheck?: Record<string, unknown>;
}

function makeClient(options: ServerOptions = {}) {
  const calls: string[] = [];
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = new URL(String(input), "http://x");
      const path = url.pathname.replace(/^\/api\/brazosbend/, "");
      const method = (init?.method ?? "GET").toUpperCase();
      calls.push(`${method} ${path}`);
      const json = (body: unknown, status = 200): Response =>
        new Response(JSON.stringify(body), {
          status,
          headers: { "Content-Type": "application/json" },
        });
      if (path === "/service-requests/categories") {
        return json({
          selectable: [
            { code: "residential", name: "Residential" },
            { code: "commercial", name: "Commercial" },
          ],
          legacy: [],
        });
      }
      if (path === "/settings/services") {
        return json([{ service: "water", name: "Water", enabled: true }]);
      }
      if (path === "/premises/picker") {
        const rows = options.premises ?? [];
        return json({ count: rows.length, next: null, previous: null, results: rows });
      }
      if (path === "/integrations/gis_esri/check-address") {
        return json(
          options.cityCheck ?? { result: "not_connected", match: null, session: null, message_key: null },
        );
      }
      if (path === "/service-requests/capture-defaults") {
        return json({ requested_start: "2026-10-15", working_days: 15, holidays_counted: 0 });
      }
      return json({ count: 0, next: null, previous: null, results: [] });
    },
  });
  return { client, calls };
}

function mount(search: string, options: ServerOptions = {}) {
  const { client } = makeClient(options);
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[`/brazosbend/requests/new${search}`]}>
        <Routes>
          <Route
            path="/:tenant/requests/new"
            element={<ServiceRequestCapturePage client={client} />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Every visible label on the screen, in DOM order. Reading ORDER off the
 *  rendered document is the only way to assert a drawn sequence — a list of
 *  `getByLabelText` calls passes whatever order they are in. */
function labelsInOrder(): string[] {
  return Array.from(document.querySelectorAll("label")).map((node) =>
    (node.textContent ?? "").replace(/\*/g, "").trim(),
  );
}

// ══════════════════════════════════════════════════════════════════════════
// 0 · THE FRAME
// ══════════════════════════════════════════════════════════════════════════

describe("REQ-03 · four steps, not six", () => {
  it("the stepper is FOUR, in the drawn order", () => {
    expect([...CAPTURE_STEPS]).toEqual(["applicant", "property", "service", "review"]);
  });

  it("step 1 says `Step 1 of 4 · Applicant`, read off the page", async () => {
    mount("?step=1");
    expect(
      await screen.findByText(
        t("customers.serviceRequest.capture.stepOfN", {
          n: 1,
          total: 4,
          name: t("customers.serviceRequest.capture.stepShort.applicant"),
        }),
      ),
    ).toBeInTheDocument();
  });

  it("step 2's page title is the drawn question", async () => {
    mount("?step=2");
    expect(
      await screen.findByText(t("customers.serviceRequest.capture.stepTitle.property")),
    ).toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE APPLICANT STEP — task 5
// ══════════════════════════════════════════════════════════════════════════

// ⊕ **AMENDED 2026-10-18 (lane CF-1) — STEP 1 IS THE SHARED CUSTOMER FORM.**
// The two describes below read *"the eleven fields render in the drawn order"*
// and *"REQ-03 step 1 · Documents"* off `01-applicant-1440.png`. The PO then
// ruled that every create screen uses Move-in's customer form (decision log
// 2026-10-18) and approved image 03 of `customer-forms-2026-10-18` for the
// request: Who is applying · Identity (NO *Search customer ID*) · About the
// customer · Co-applicants · Documents · Mailing address · Preferences (no
// Autopay). These cases assert THAT drawing, read off the rendered page.
describe("REQ-03 step 1 · the shared customer form (image 03)", () => {
  it("draws the panels in image 03's order, with no Search customer ID", async () => {
    mount("?step=1");
    await screen.findByRole("heading", { name: t("customers.form.whoApplying") });
    const panels = Array.from(document.querySelectorAll("[data-customer-panel], [data-tick-panel], [data-billing-section]"))
      .map((node) =>
        node.getAttribute("data-customer-panel") ??
        node.getAttribute("data-tick-panel") ??
        node.getAttribute("data-billing-section"),
      )
      .filter((name, at, all) => all.indexOf(name) === at);
    expect(panels).toEqual(["who", "identity", "co_owner", "mailing", "preferences"]);
    // Documents sits between the co-applicants and the mailing address.
    const html = document.body.innerHTML;
    expect(html.indexOf(t("customers.moveIn.customer.docs.title"))).toBeGreaterThan(
      html.indexOf(t("customers.form.coApplicants.title")),
    );
    expect(html.indexOf(t("customers.moveIn.customer.docs.title"))).toBeLessThan(
      html.indexOf(t("customers.account.field.mailingAddress")),
    );
    expect(document.querySelector("[data-search-customer-id]")).toBeNull();
    expect(screen.queryByRole("button", { name: t("customers.moveIn.customer.search") })).toBeNull();
  });

  it("a person: Who's fields in the drawn order, then SSN · licence · government ID", async () => {
    mount("?step=1");
    await screen.findByRole("heading", { name: t("customers.form.whoApplying") });
    await screen.findByRole("option", { name: "Residential" });
    const labels = labelsInOrder();
    const order = [
      t("customers.accounts.filter.category"),
      t("customers.account.field.fullName"),
      t("customers.account.field.email"),
      t("customers.account.field.phone"),
      t("customers.account.field.dob"),
      t("customers.moveDetail.col.contactBy"),
      t("customers.newAccount.field.ssn"),
      t("customers.newAccount.field.drivingLicence"),
      t("customers.account.field.govId"),
    ];
    const at = order.map((label) => labels.indexOf(label));
    expect(at.every((index) => index >= 0)).toBe(true);
    expect([...at].sort((a, b) => a - b)).toEqual(at);
  });

  it("a company: no person's evidence, and its Tax ID is asked in Who", async () => {
    mount("?step=1");
    await screen.findByRole("heading", { name: t("customers.form.whoApplying") });
    await userEvent.click(screen.getByRole("radio", { name: t("customers.customer.kind.company") }));
    expect(document.querySelector('[data-customer-panel="identity"]')).toBeNull();
    expect(document.getElementById("dob")).toBeNull();
    expect(document.getElementById("tax_id")).not.toBeNull();
  });

  it("Co-applicants: closed until ticked, then one full card", async () => {
    mount("?step=1");
    const tick = await screen.findByLabelText(t("customers.form.coApplicants.tick"));
    expect(document.getElementById("co_owner_0_full_name")).toBeNull();
    await userEvent.click(tick);
    for (const field of ["full_name", "relationship", "responsible_for_bills", "phone", "email", "date_of_birth", "ssn", "driving_licence"]) {
      expect(document.getElementById(`co_owner_0_${field}`), field).not.toBeNull();
    }
    expect(screen.getByRole("button", { name: t("customers.form.coApplicants.add") })).toBeInTheDocument();
  });

  it("Preferences: paperless, text reminders and language — never Autopay", async () => {
    mount("?step=1");
    const tick = await screen.findByLabelText(t("customers.moveIn.prefs.tick"));
    await userEvent.click(tick);
    expect(document.getElementById("paperless")).not.toBeNull();
    expect(document.getElementById("sms_reminders")).not.toBeNull();
    expect(document.getElementById("autopay")).toBeNull();
  });

  it("Mailing address: ticked prints the service address; cleared, five live US fields", async () => {
    mount("?step=1");
    const tick = await screen.findByLabelText(t("customers.account.field.mailingSame"));
    expect(tick).toBeChecked();
    expect(document.querySelector('[data-mailing="service"]')).not.toBeNull();
    expect(document.getElementById("mailing_line1")).toBeNull();
    await userEvent.click(tick);
    for (const id of ["mailing_line1", "mailing_line2", "mailing_city", "mailing_state", "mailing_postal_code"]) {
      expect(document.getElementById(id), id).toBeEnabled();
    }
  });
});

describe("REQ-03 step 2 · the property", () => {
  it("`+ Premises` is absent when NOTHING matched", async () => {
    mount("?step=2", { premises: [] });
    const box = await screen.findByLabelText(
      t("customers.serviceRequest.capture.streetOrPremise"),
      { exact: false },
    );
    await userEvent.type(box, "Lot 14, Willow Bend");
    expect(
      await screen.findByText(t("customers.serviceRequest.capture.noPremisesMatch")),
    ).toBeInTheDocument();
    // ⚠ **AND THE SECOND HALF OF THE DRAWN SENTENCE, WHICH WAS MISSING.** The
    // line said an address was not found and never said it was KEPT — the one
    // thing `BR-CUS-070` promises and the one thing a clerk at a greenfield
    // site needs to read.
    expect(
      screen.getByText(t("customers.serviceRequest.capture.typedAddressIsKept")),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: t("customers.serviceRequest.capture.addPremises") }),
    ).toBeNull();
    // `BR-CUS-070` — and what the applicant said is still in the box.
    expect(box).toHaveValue("Lot 14, Willow Bend");
  });

  it("`+ Premises` is absent when something DID match", async () => {
    mount("?step=2", { premises: [BALCONES] });
    const box = await screen.findByLabelText(
      t("customers.serviceRequest.capture.streetOrPremise"),
      { exact: false },
    );
    await userEvent.type(box, "Balcones");
    expect(await screen.findByText(/1200 Balcones Dr/)).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: t("customers.serviceRequest.capture.addPremises") }),
    ).toBeNull();
  });

  // ⚠ `DEF-CUS-10039` (PO 2026-10-11): this case asserted all three boxes
  // were read-only with NOTHING picked, which is the defect itself — a clerk
  // could not give the town for an address the register does not hold.
  it("City, State and ZIP are TYPED while no premise is picked — DEF-CUS-10039", async () => {
    mount("?step=2", { premises: [] });
    await screen.findByLabelText(t("customers.serviceRequest.capture.streetOrPremise"), {
      exact: false,
    });
    const typed: Record<string, string> = {
      address_city_as_given: "Ottumwa",
      address_state_as_given: "IA",
      address_postal_code_as_given: "52501",
    };
    for (const [id, value] of Object.entries(typed)) {
      const node = document.getElementById(id) as HTMLInputElement;
      expect(node).not.toHaveAttribute("readonly");
      await userEvent.type(node, value);
      expect(node).toHaveValue(value);
    }
    expect(
      screen.queryByText(t("customers.serviceRequest.capture.fromTheMatchedPremise")),
    ).toBeNull();
  });

  it("once a premise is picked they are the premise's own and read-only — hard rule 8", async () => {
    mount("?step=2", { premises: [BALCONES] });
    const box = await screen.findByLabelText(
      t("customers.serviceRequest.capture.streetOrPremise"),
      { exact: false },
    );
    await userEvent.type(box, "Balcones");
    await userEvent.click(await screen.findByText(/1200 Balcones Dr/));
    const city = document.getElementById("address_city_as_given");
    expect(city).toHaveAttribute("readonly");
    expect(city).toHaveValue("Ottumwa");
    expect(document.getElementById("address_postal_code_as_given")).toHaveValue("12365");
    expect(
      screen.getByText(t("customers.serviceRequest.capture.fromTheMatchedPremise")),
    ).toBeInTheDocument();
    // `DEF-CUS-10040` — nothing to check once the register answered.
    expect(
      screen.queryByRole("button", { name: t("metering.addPremise.check.button") }),
    ).toBeNull();
  });

  it("Check address with no City map connected says so — DEF-CUS-10040", async () => {
    mount("?step=2", { premises: [] });
    const box = await screen.findByLabelText(
      t("customers.serviceRequest.capture.streetOrPremise"),
      { exact: false },
    );
    await userEvent.type(box, "main st 25");
    await userEvent.click(
      screen.getByRole("button", { name: t("metering.addPremise.check.button") }),
    );
    expect(
      await screen.findByText(t("metering.addPremise.check.notConnectedTitle")),
    ).toBeInTheDocument();
  });

  it("Check address that matches fills City, State, ZIP from `Use these details` — DEF-CUS-10040", async () => {
    mount("?step=2", {
      premises: [],
      cityCheck: {
        result: "match",
        session: null,
        message_key: null,
        match: {
          parcel: "007-123-456",
          point: null,
          address_line: "25 Main St",
          city: "Ottumwa",
          state: "IA",
          postal_code: "52501",
          lat: null,
          lng: null,
          frame: "",
          status: null,
          match: "strong",
        },
      },
    });
    const box = await screen.findByLabelText(
      t("customers.serviceRequest.capture.streetOrPremise"),
      { exact: false },
    );
    await userEvent.type(box, "main st 25");
    await userEvent.click(
      screen.getByRole("button", { name: t("metering.addPremise.check.button") }),
    );
    await userEvent.click(
      await screen.findByRole("button", { name: t("metering.addPremise.check.use") }),
    );
    expect(document.getElementById("address_city_as_given")).toHaveValue("Ottumwa");
    expect(document.getElementById("address_state_as_given")).toHaveValue("IA");
    expect(document.getElementById("address_postal_code_as_given")).toHaveValue("52501");
  });

  it("`Found in Premises` is drawn with its own sentence when nothing matched", async () => {
    mount("?step=2", { premises: [] });
    expect(
      await screen.findByText(t("customers.serviceRequest.capture.whatTheRegisterMatched")),
    ).toBeInTheDocument();
    expect(
      screen.getByText(t("customers.serviceRequest.capture.nothingMatchedYet")),
    ).toBeInTheDocument();
  });

  it("the mailing address is NOT on step 2 any more — it moved to step 1 (lane CF-1)", async () => {
    // ⊕ **AMENDED 2026-10-18 (lane CF-1).** Three cases here proved the step-2
    // mailing block; the block is the shared `MailingAddressBlock` on STEP 1
    // now (image 03), proved in the describe above. This one proves it left.
    mount("?step=2", { premises: [] });
    await screen.findByLabelText(t("customers.serviceRequest.capture.streetOrPremise"), { exact: false });
    expect(document.querySelector('[data-tick-panel="mailing"]')).toBeNull();
    expect(screen.queryByText(t("customers.serviceRequest.capture.billingAddress"))).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 4 · THE PRINTED ADDRESS — pure, so the two drawn lines are pinned
// ══════════════════════════════════════════════════════════════════════════

describe("serviceAddressLines", () => {
  it("draws the two lines the image draws", () => {
    expect(
      serviceAddressLines({
        street: "Mark 234",
        unit: "12",
        city: "Ottumwa",
        state: "Iowa",
        postalCode: "12365",
        unitWord: "Unit",
      }),
    ).toEqual(["Mark 234, Unit 12", "Ottumwa, Iowa 12365"]);
  });

  it("an empty part drops out rather than leaving a stray comma", () => {
    expect(
      serviceAddressLines({
        street: "Lot 14",
        unit: "",
        city: "",
        state: "",
        postalCode: "",
        unitWord: "Unit",
      }),
    ).toEqual(["Lot 14"]);
  });
});

// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Change:   CR-190-BRC10 lane AGREEMENT — the agreement link's page
// Cases:    the agreement as published, with the PDF link, the tick, the date
//           and the typed name · Submit posts exactly those three and lands on
//           the confirmation · a field refusal is shown under its field · a
//           dead link shows the call-the-office dead end with the utility's
//           number · the page is mounted under the REAL route pattern
//           (`DEF-CWP-3925`), so the PDF href carries the tenant
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { ApiError } from "@/api/client";
import type { ApiClient } from "@/api/client";

import type { PortalFront } from "../api/guestClient";
import type { AgreementLink } from "../api/agreementClient";
import { AGREEMENT_ROUTE, AgreementPage } from "./AgreementPage";

const FRONT: PortalFront = {
  tenant: { slug: "pine-hill", name: "Pine Hill Water & Power", brand_primary_hex: "#EC3013", brand_accent_hex: "#E15B47" },
  is_live: false,
  regional: { timezone: "America/Chicago", date_format: "MM/DD/YYYY", language: null },
  locales: ["en", "es"],
  cards: [],
  links: { help: false, visit: false },
  services: [],
  strapline: null,
  office_hours_text: null,
  emergency_phone: null,
};

const OPEN: AgreementLink = {
  state: "open",
  utility_name: "Pine Hill Water & Power",
  customer_name: "Ana Ruiz",
  account_no: "AC-2026-00042",
  agreement_name: "Service agreement",
  version: 3,
  effective_from: "2026-01-01",
  text: "We supply water.\n\nYou pay at our published rates.",
  expires_at: "2026-10-29T12:00:00Z",
  today: "2026-10-22",
};

function client(link: AgreementLink, post?: (path: string, body: unknown) => Promise<unknown>): ApiClient {
  return {
    get: vi.fn(async (path: string) => ({
      data: path === "/portal/public/front" ? FRONT : link,
      status: 200,
    })),
    post: vi.fn(async (path: string, body: unknown) => ({
      data: post ? await post(path, body) : null,
      status: 200,
    })),
  } as unknown as ApiClient;
}

function draw(api: ApiClient) {
  const queries = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queries}>
      <MemoryRouter initialEntries={["/pine-hill/portal/agreements/tok-123"]}>
        <Routes>
          <Route path={`/:tenant/${AGREEMENT_ROUTE}`} element={<AgreementPage client={api} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("the agreement link's page (CR-190-BRC10)", () => {
  it("shows the agreement as published, its PDF, and the three things asked for", async () => {
    draw(client(OPEN));
    expect(await screen.findByRole("heading", { name: "Service agreement" })).toBeInTheDocument();
    expect(screen.getByText("Ana Ruiz")).toBeInTheDocument();
    expect(screen.getByText("AC-2026-00042")).toBeInTheDocument();
    expect(document.querySelector("[data-agreement-text]")?.textContent).toContain("published rates");
    const pdf = screen.getByRole("link", { name: "Download PDF" });
    expect(pdf.getAttribute("href")).toContain("/pine-hill/agreements/public/tok-123/document");
    expect(screen.getByLabelText("I have read and agree")).not.toBeChecked();
    expect(screen.getByRole("textbox", { name: /Your full name/ })).toBeInTheDocument();
    // No token, no id on the glass (B14 rule 31).
    expect(document.body.textContent).not.toContain("tok-123");
  });

  it("posts the tick, the date and the typed name, then confirms", async () => {
    const seen: unknown[] = [];
    const api = client(OPEN, async (_path, body) => {
      seen.push(body);
      return { state: "accepted", agreement_name: "Service agreement", accepted_date: "2026-10-22", accepted_name: "Ana Ruiz" };
    });
    draw(api);
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText("I have read and agree"));
    await user.type(screen.getByRole("textbox", { name: /Your full name/ }), "Ana Ruiz");
    const dateBox = document.getElementById(
      document.querySelector("[data-field] input[aria-describedby$='-error']")?.id ?? "",
    );
    expect(dateBox).not.toBeNull();
    await user.type(dateBox as HTMLElement, "10/22/2026");
    await user.click(screen.getByRole("button", { name: "Submit" }));
    await waitFor(() => expect(seen).toHaveLength(1));
    expect(seen[0]).toMatchObject({ agreed: true, name: "Ana Ruiz", date: "2026-10-22" });
    expect(await screen.findByRole("heading", { name: "Thank you" })).toBeInTheDocument();
    expect(document.querySelector("[data-agreement-done]")?.textContent).toContain("Ana Ruiz");
  });

  it("puts a refusal under its own field", async () => {
    const api = client(OPEN, async () => {
      throw new ApiError(422, {
        code: "VAL-003",
        message_key: "customers.agreement.acceptRefused",
        field_errors: [{ field: "date", code: "VAL-003", message_key: "customers.agreement.dateMustBeToday" }],
      });
    });
    draw(api);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Submit" }));
    expect(await screen.findByText("Enter today's date.")).toBeInTheDocument();
    // Correcting the field takes its refusal away (found on the browser walk).
    const dateBox = document.querySelector("[data-field] input[aria-describedby$='-error']");
    await user.type(dateBox as HTMLElement, "10/22/2026");
    await waitFor(() => expect(screen.queryByText("Enter today's date.")).toBeNull());
  });

  it("a dead link is the call-the-office dead end, with the utility's number", async () => {
    draw(client({ state: "unavailable", support_phone: "(512) 555-0100" }));
    expect(await screen.findByRole("heading", { name: "This link has expired" })).toBeInTheDocument();
    const call = screen.getByRole("link", { name: "(512) 555-0100" });
    expect(call.getAttribute("href")).toBe("tel:5125550100");
    expect(screen.queryByRole("button", { name: "Submit" })).toBeNull();
  });
});

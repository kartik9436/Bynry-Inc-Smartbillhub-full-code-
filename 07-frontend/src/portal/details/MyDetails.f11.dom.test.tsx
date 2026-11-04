// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defect:   DEF-CWP-10549 (F-11) · DEF-CWP-10547 (F-02) · DEF-CWP-10552 (F-04)
// Ruling:   PO/QA 2026-10-23 (decision log "three product answers", point 3)
// Cases:    phone `abc` and ZIP `1` are refused ON THE FIELD and nothing is
//           sent; the server's refusal of the same lands on the same boxes; an
//           emptied phone says "Phone removed." (+ the text-reminder sentence
//           when they are on); a save that changed nothing never reads
//           "Saved on 0 accounts."; the result is announced and focused.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { ApiError } from "@/api/client";

import type { MyDetailsSaved, PortalMyDetails } from "../api/portalClient";
import { PortalAnnouncer } from "../components/a11y";

const sent: unknown[] = [];
let answer: () => Promise<MyDetailsSaved> = async () => ({ accounts_updated: 4, account_ids: [] });
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getMyDetails: async () => DETAILS,
    saveMyDetails: async (body: unknown) => {
      sent.push(body);
      return answer();
    },
  };
});

const { MyDetailsView } = await import("./MyDetails");

const DETAILS: PortalMyDetails = {
  as_of: "2026-10-23",
  email: "maria@example.invalid",
  email_varies: false,
  phone: "(512) 555-4218",
  phone_varies: false,
  postal: { line1: "1408 Elm St", line2: null, city: "Austin", state: "TX", postal_code: "78704", country: null },
  postal_varies: false,
  legal_name: "Maria Example",
  returned_post_accounts: 0,
  account_count: 3,
  refused: ["legal_name", "account_holder"],
  locales: ["en", "es"],
  locale: "en",
  security: { password_changed_on: "2026-03-04", code_channel: "sms", devices_signed_in: 1 },
};

async function draw() {
  render(
    <MemoryRouter initialEntries={["/pine-hill/portal/my-details"]}>
      <PortalAnnouncer>
        <Routes>
          <Route path="/:tenant/portal/my-details" element={<MyDetailsView />} />
        </Routes>
      </PortalAnnouncer>
    </MemoryRouter>,
  );
  await screen.findByDisplayValue("(512) 555-4218");
}

const box = (id: string) => document.getElementById(id) as HTMLInputElement;
const save = () => fireEvent.click(screen.getByRole("button", { name: /Save changes/ }));
const alertText = () => document.querySelector("[data-portal-alert]")?.textContent ?? "";
const statusText = () => document.querySelector("[data-portal-status]")?.textContent ?? "";

afterEach(() => {
  cleanup();
  sent.length = 0;
  answer = async () => ({ accounts_updated: 4, account_ids: [] });
});

describe("F-11 · My details refuses a malformed phone or ZIP on the field", () => {
  it("phone `abc` and ZIP `1`: both boxes marked, messages linked, summary focused, nothing sent", async () => {
    await draw();
    fireEvent.change(box("my-phone"), { target: { value: "abc" } });
    fireEvent.change(box("my-postal-code"), { target: { value: "1" } });
    save();
    expect(sent).toEqual([]);
    expect(box("my-phone")).toHaveAttribute("aria-invalid", "true");
    expect(box("my-phone").getAttribute("aria-describedby")).toContain("my-phone-error");
    expect(document.getElementById("my-phone-error")).toHaveTextContent("Enter a 10-digit phone number.");
    expect(box("my-postal-code")).toHaveAttribute("aria-invalid", "true");
    expect(document.getElementById("my-postal-code-error")).toHaveTextContent("Enter a 5-digit ZIP.");
    expect(document.activeElement).toBe(document.querySelector("[data-error-summary]"));
    expect(alertText()).toContain("Enter a 10-digit phone number.");
  });

  it("the SERVER's refusal of the same lands on the same box", async () => {
    answer = async () => {
      throw new ApiError(400, {
        code: "VAL-002",
        message_key: "portal.myDetails.phoneFormat",
        field_errors: [{ field: "phone", code: "VAL-002", message_key: "portal.myDetails.phoneFormat" }],
      });
    };
    await draw();
    // A phone the screen accepts but the server refuses (rules differing is
    // exactly what the server half is there to catch).
    fireEvent.change(box("my-phone"), { target: { value: "(281) 555-0164" } });
    save();
    await waitFor(() => expect(box("my-phone")).toHaveAttribute("aria-invalid", "true"));
    expect(document.getElementById("my-phone-error")).toHaveTextContent("Enter a 10-digit phone number.");
  });
});

describe("F-11 · an emptied phone is REMOVED, and says so", () => {
  it("'Phone removed.' and, with text reminders on, 'Text reminders stop without a phone.' — heard and focused", async () => {
    answer = async () => ({ accounts_updated: 3, account_ids: [], phone_removed: true, text_reminders_on: true });
    await draw();
    fireEvent.change(box("my-phone"), { target: { value: "" } });
    save();
    await screen.findByText("Phone removed.");
    expect(sent).toEqual([{ phone: "", postal: DETAILS.postal }]);
    expect(screen.getByText("Text reminders stop without a phone.")).toBeInTheDocument();
    const result = document.querySelector("[data-my-details-saved]");
    expect(document.activeElement).toBe(result);
    expect(statusText()).toContain("Phone removed.");
  });

  it("without text reminders the second sentence is not said", async () => {
    answer = async () => ({ accounts_updated: 3, account_ids: [], phone_removed: true, text_reminders_on: false });
    await draw();
    fireEvent.change(box("my-phone"), { target: { value: "" } });
    save();
    await screen.findByText("Phone removed.");
    expect(screen.queryByText("Text reminders stop without a phone.")).toBeNull();
  });

  it("a save that changed nothing never reads 'Saved on 0 accounts.'", async () => {
    answer = async () => ({ accounts_updated: 0, account_ids: [] });
    await draw();
    fireEvent.change(box("my-postal-code"), { target: { value: "78704-1234" } });
    save();
    await screen.findByText("No changes were saved.");
    expect(document.body.textContent).not.toContain("Saved on 0");
  });
});

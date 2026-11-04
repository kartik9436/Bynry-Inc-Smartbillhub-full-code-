// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Change:   DEF-CWP-10401 — a signed-in customer's NEW email is confirmed by a
//           one-time code sent to it; only then do the contact email and the
//           sign-in email move (PO 2026-10-22, Q2 option A).
// Screen:   CWP-024, mounted under its real route pattern (law 2's fixture
//           clause: a bare mount cannot tell a working address from a broken
//           one).
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import type { PortalMyDetails } from "../api/portalClient";

const calls: { saved: unknown[]; started: unknown[]; confirmed: unknown[] } = {
  saved: [],
  started: [],
  confirmed: [],
};
let confirmAnswer: { ok: boolean; reason?: string } = { ok: true };

vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getMyDetails: async () => BASE,
    saveMyDetails: async (body: unknown) => {
      calls.saved.push(body);
      return { accounts_updated: 1, account_ids: [] };
    },
  };
});
vi.mock("../api/updateEmailClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/updateEmailClient");
  return {
    ...actual,
    startSignedInEmailChange: async (body: unknown) => {
      calls.started.push(body);
      return { ok: true, ref: "row-1", sent_to: "m•••@new.example", expires_in_minutes: 10 };
    },
    confirmSignedInEmailChange: async (body: unknown) => {
      calls.confirmed.push(body);
      return confirmAnswer;
    },
  };
});

const { MyDetailsView } = await import("./MyDetails");

const BASE: PortalMyDetails = {
  as_of: "2026-10-22",
  email: "m.alvarez@example.com",
  email_varies: false,
  phone: "(512) 555-4218",
  phone_varies: false,
  postal: { line1: "1408 Elm St", line2: null, city: "Austin", state: "TX", postal_code: "78704", country: null },
  postal_varies: false,
  legal_name: "Maria Alvarez",
  returned_post_accounts: 0,
  account_count: 1,
  refused: ["legal_name", "account_holder"],
  locales: ["en"],
  locale: "en",
  security: { password_changed_on: null, code_channel: "email", devices_signed_in: 1 },
};

function draw() {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/my-details"]}>
      <Routes>
        <Route path="/:tenant/portal/my-details" element={<MyDetailsView />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  calls.saved = [];
  calls.started = [];
  calls.confirmed = [];
  confirmAnswer = { ok: true };
});
afterEach(cleanup);

async function typeNewEmailAndSave() {
  const box = await screen.findByDisplayValue("m.alvarez@example.com");
  fireEvent.change(box, { target: { value: "maria.new@example.test" } });
  fireEvent.click(screen.getByRole("button", { name: i18n.t("portal.myDetails.save") }));
  return screen.findByText(i18n.t("portal.myDetails.emailCode.title"));
}

describe("CWP-024 · a new email is confirmed by a code (DEF-CWP-10401)", () => {
  it("Save sends a code to the NEW address and never saves the email itself", async () => {
    const { container } = draw();
    await typeNewEmailAndSave();
    expect(calls.started).toEqual([{ email: "maria.new@example.test" }]);
    // No contact write before the code comes back.
    expect(calls.saved).toEqual([]);
    expect(container.querySelector("[data-my-email-sentto]")?.textContent).toBe("m•••@new.example");
    expect(container.querySelector("[data-my-email-code]")).toBeTruthy();
  });

  it("the code and the typed address go back together, then 'Email changed.'", async () => {
    const { container } = draw();
    await typeNewEmailAndSave();
    fireEvent.change(container.querySelector("#my-email-code")!, { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: i18n.t("portal.updateEmail.confirm") }));
    expect(await screen.findByText(i18n.t("portal.myDetails.emailCode.done"))).toBeTruthy();
    expect(calls.confirmed).toEqual([
      { ref: "row-1", code: "123456", email: "maria.new@example.test" },
    ]);
  });

  it("DEF-CWP-10569 (F-22): a Confirm with no code is disabled AND says why, as text tied to it", async () => {
    draw();
    await typeNewEmailAndSave();
    const confirm = screen.getByRole("button", { name: i18n.t("portal.updateEmail.confirm") });
    expect(confirm).toBeDisabled();
    const reasonId = confirm.getAttribute("aria-describedby");
    expect(reasonId).toBeTruthy();
    expect(document.getElementById(reasonId as string)?.textContent).toBe(i18n.t("portal.addAccount.needCode"));
    expect(i18n.t("portal.addAccount.needCode")).toBe("Enter the code");
  });

  it("a wrong code says so and keeps the step open", async () => {
    confirmAnswer = { ok: false, reason: "wrong" };
    const { container } = draw();
    await typeNewEmailAndSave();
    fireEvent.change(container.querySelector("#my-email-code")!, { target: { value: "000000" } });
    fireEvent.click(screen.getByRole("button", { name: i18n.t("portal.updateEmail.confirm") }));
    expect(await screen.findByText(i18n.t("portal.enrol.code.wrong"))).toBeTruthy();
    expect(container.querySelector("[data-my-email-code]")).toBeTruthy();
    expect(container.querySelector("[data-my-details-email-moved]")).toBeNull();
  });

  it("a phone change alone still saves at once, with no email in the body", async () => {
    draw();
    const phone = await screen.findByDisplayValue("(512) 555-4218");
    fireEvent.change(phone, { target: { value: "(512) 555-9911" } });
    fireEvent.click(screen.getByRole("button", { name: i18n.t("portal.myDetails.save") }));
    await screen.findByText(i18n.t("portal.myDetails.saved", { count: 1 }));
    expect(calls.saved).toHaveLength(1);
    expect(calls.saved[0]).not.toHaveProperty("email");
    expect(calls.started).toEqual([]);
  });
});

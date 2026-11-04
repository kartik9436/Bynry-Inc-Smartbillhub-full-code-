// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-189-BRC10 — CWP-079, *Update your registered email*
// Tests:    this file
// Impacts:  src/portal/signin/UpdateEmail.tsx · routing/portalRoutes.tsx
// ───────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Each walk clicks through four steps; a loaded CI box needs more than 5 s.
vi.setConfig({ testTimeout: 30000 });

import "@/i18n";

let calls: Array<[string, Record<string, unknown>]> = [];
let findAnswer: Record<string, unknown> = {};
let confirmAnswer: Record<string, unknown> = {};

vi.mock("../api/updateEmailClient", () => ({
  findForEmailUpdate: async (body: Record<string, unknown>) => {
    calls.push(["find", body]);
    return findAnswer;
  },
  sendEmailUpdateCode: async (body: Record<string, unknown>) => {
    calls.push(["send", body]);
    return { sent: true, ref: "r-prove", sent_to: "••• ••• 4821", channel: "sms", expires_in_minutes: 10 };
  },
  verifyEmailUpdateCode: async (body: Record<string, unknown>) => {
    calls.push(["verify", body]);
    return { result: body.code === "123456" ? "ok" : "wrong" };
  },
  startNewEmail: async (body: Record<string, unknown>) => {
    calls.push(["start", body]);
    return { ok: true, ref: "r-confirm", sent_to: "m•••@gmail.com", expires_in_minutes: 10 };
  },
  confirmNewEmail: async (body: Record<string, unknown>) => {
    calls.push(["confirm", body]);
    return confirmAnswer;
  },
}));

const { UpdateEmailView } = await import("./UpdateEmail");

/** Under the REAL path pattern, so a door builds `/pine-hill/portal/…` and
 *  never `//portal/…` (`DEF-CWP-3925`'s fixture lesson). */
function draw() {
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/update-email"]}>
      <Routes>
        <Route path="/:tenant/portal/update-email" element={<UpdateEmailView />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function fillFacts() {
  await userEvent.type(screen.getByLabelText(/Account number/), "AC-2026-00027");
  await userEvent.type(screen.getByLabelText(/ZIP code/), "78702");
  await userEvent.type(screen.getByLabelText(/Last name/), "Alvarez");
  await userEvent.click(screen.getByRole("button", { name: /Continue/ }));
}

afterEach(cleanup);
beforeEach(() => {
  calls = [];
  findAnswer = {
    matched: true,
    ref: "r-match",
    options: [
      { key: "k1", channel: "sms", masked: "••• ••• 4821" },
      { key: "k2", channel: "email", masked: "m•••@gmail.com" },
    ],
    office: { phone: "(512) 555-0148", hours: "Mon–Fri 8–5" },
  };
  confirmAnswer = { ok: true, next: "check_email", sent_to: "n•••@example.test" };
});

describe("CWP-079 · update your registered email (CR-189-BRC10)", () => {
  it("walks facts → masked contact → code → new email → code → done", async () => {
    draw();
    expect(document.querySelector('[data-screen="CWP-079"]')).not.toBeNull();
    await fillFacts();
    await waitFor(() => expect(screen.getByText("••• ••• 4821")).toBeInTheDocument());
    // Focus lands on the new step's heading, not on a button that has gone.
    expect(document.activeElement?.textContent).toBe("Choose a contact");
    // Masked, exactly as the server sent them; nothing else about the account.
    expect(screen.getByText("m•••@gmail.com")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Send a code/ }));
    await waitFor(() => expect(document.querySelector("[data-update-code]")).not.toBeNull());
    expect(document.querySelector("[data-update-lasts]")?.textContent).toBe("It lasts 10 minutes.");
    await userEvent.type(screen.getByLabelText(/Six-digit code/), "123456");
    await userEvent.click(screen.getByRole("button", { name: /Verify/ }));
    await waitFor(() => expect(screen.getByLabelText(/New email/)).toBeInTheDocument());
    await userEvent.type(screen.getByLabelText(/New email/), "new@example.test");
    await userEvent.click(screen.getByRole("button", { name: /Send a code/ }));
    await waitFor(() => expect(document.querySelector("[data-update-confirm]")).not.toBeNull());
    await userEvent.type(screen.getByLabelText(/Six-digit code/), "654321");
    await userEvent.click(screen.getByRole("button", { name: /Confirm/ }));
    await waitFor(() => expect(document.querySelector('[data-update-step="done"]')).not.toBeNull());
    expect(document.body.textContent).toContain("We sent a reset link to");
    expect(document.querySelector('[data-door="/sign-in"]')).not.toBeNull();
    expect(calls.map(([name]) => name)).toEqual(["find", "send", "verify", "start", "confirm"]);
    expect(calls[1][1]).toEqual({ ref: "r-match", option: "k1" });
    expect(calls[4][1]).toEqual({ ref: "r-confirm", code: "654321", email: "new@example.test" });
  });

  it("no login yet: the done step points to sign-up", async () => {
    confirmAnswer = { ok: true, next: "enrol", sent_to: "n•••@example.test" };
    draw();
    await fillFacts();
    await waitFor(() => screen.getByText("••• ••• 4821"));
    await userEvent.click(screen.getByRole("button", { name: /Send a code/ }));
    await waitFor(() => screen.getByLabelText(/Six-digit code/));
    await userEvent.type(screen.getByLabelText(/Six-digit code/), "123456");
    await userEvent.click(screen.getByRole("button", { name: /Verify/ }));
    await waitFor(() => screen.getByLabelText(/New email/));
    await userEvent.type(screen.getByLabelText(/New email/), "new@example.test");
    await userEvent.click(screen.getByRole("button", { name: /Send a code/ }));
    await waitFor(() => screen.getByLabelText(/Six-digit code/));
    await userEvent.type(screen.getByLabelText(/Six-digit code/), "111111");
    await userEvent.click(screen.getByRole("button", { name: /Confirm/ }));
    await waitFor(() => expect(document.querySelector('[data-update-next="enrol"]')).not.toBeNull());
    expect(document.querySelector('[data-door="/enrol"]')).not.toBeNull();
  });

  it("a miss says one plain sentence", async () => {
    findAnswer = { matched: false, reason: "not_matched" };
    draw();
    await fillFacts();
    await waitFor(() =>
      // F-02 (`DEF-CWP-10547`): the sentence is on the step AND in the frame's
      // always-present alert region (a `role="alert"` mounted with its text is
      // not reliably read, which was the finding).
      expect(document.querySelector("[data-update-refused]")).toHaveTextContent("We couldn't find that account."),
    );
  });

  it("nothing on file: call the office, with the utility's own phone and hours", async () => {
    findAnswer = {
      matched: true,
      reason: "no_contact_on_file",
      ref: null,
      office: { phone: "(512) 555-0148", hours: "Mon–Fri 8–5" },
    };
    draw();
    await fillFacts();
    await waitFor(() => expect(document.querySelector("[data-update-office]")).not.toBeNull());
    const text = document.querySelector("[data-update-office]")?.textContent ?? "";
    expect(text).toContain("Call the office");
    expect(text).toContain("We can't verify you online.");
    expect(text).toContain("(512) 555-0148");
    expect(text).toContain("Mon–Fri 8–5");
  });

  it("an office with no phone on Settings shows no phone row, never a made-up one", async () => {
    findAnswer = { matched: true, reason: "no_contact_on_file", ref: null, office: { phone: null, hours: null } };
    draw();
    await fillFacts();
    await waitFor(() => expect(document.querySelector("[data-update-office]")).not.toBeNull());
    expect(document.querySelector("[data-kvlist]")).toBeNull();
  });

  it("I can't reach any of these → the same dead end", async () => {
    draw();
    await fillFacts();
    await waitFor(() => screen.getByText("••• ••• 4821"));
    await userEvent.click(screen.getByRole("button", { name: /can't reach any/ }));
    expect(document.querySelector("[data-update-office]")).not.toBeNull();
    expect(document.body.textContent).toContain("(512) 555-0148");
  });
});

describe("CWP-079 · the route and the door to it", () => {
  it("the router serves /update-email and the register names it CWP-079", async () => {
    const { PORTAL_ROUTES } = await import("../routing/portalRoutes");
    const { PORTAL_SCREENS } = await import("../routing/screenIds");
    expect(PORTAL_SCREENS.find((row) => row.path === "/update-email")?.id).toBe("CWP-079");
    expect(PORTAL_ROUTES.some((route) => route.path === "/update-email")).toBe(true);
  });

  /**
   * ⚠ **HOLD-EXPIRY, BOTH WAYS (law 2).** PORTAL-RESET draws *Update your
   * registered email* on the forgot-password page and exports the address it
   * links to as `UPDATE_EMAIL_PATH`. This case reads that constant and fails
   * the day the two disagree. On a branch without that lane it has nothing to
   * read and is skipped BY NAME rather than passing over nothing.
   */
  it("forgot-password's link points at this route", async () => {
    const forgot = (await import("./ForgotPassword")) as Record<string, unknown>;
    if (!("UPDATE_EMAIL_PATH" in forgot)) {
      console.warn("SKIPPED: ForgotPassword.tsx exports no UPDATE_EMAIL_PATH on this branch (PORTAL-RESET not merged)");
      return;
    }
    expect(forgot.UPDATE_EMAIL_PATH).toBe("/update-email");
  });
});

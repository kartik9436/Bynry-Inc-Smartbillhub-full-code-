// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-020 (EP-CWP-05) — forgotten password, answered the same way
//           either way. Screen: CWP-019
// Rules:    BR-CWP-038 (the SAME *check your email* panel whether or not the
//           address has a login) · B14 rule 33 (a reason on screen is a FACT;
//           the RATIONALE is not on screen at all) · rule 36 (compose the kit)
// Cases:    the wireframe's `s5` — the link is described BEFORE the ask; the
//           confirmation says what to do next; there is a way back
//
//           ⚠ **`ForgotPassword.tsx` HAS NAMED A TEST FILE SINCE WAVE E AND
//           NONE EXISTED (`DEF-CWP-3862`).** Its own header says so in
//           capitals — *"NONE — `SignIn.test.tsx` DOES NOT EXIST"* — so
//           `BR-CWP-038`'s one-answer guarantee was asserted on the server
//           side only, and every word on this screen was unchecked. This file
//           is that gap closed, and hard-won law 1 is why it is a file rather
//           than a `Tests:` line.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

let asked: Array<Record<string, unknown>> = [];
let resets: Array<Record<string, unknown>> = [];
let resetAnswer: () => Promise<{ ok: boolean }> = async () => ({ ok: true });

vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    forgotPassword: async (body: Record<string, unknown>) => {
      asked.push(body);
      return { ok: true };
    },
    resetPassword: async (body: Record<string, unknown>) => {
      resets.push(body);
      return resetAnswer();
    },
  };
});

const { ForgotPasswordView } = await import("./ForgotPassword");

/** Mounted under the REAL path pattern — `usePortalPath` reads `:tenant`, and
 *  a bare mount builds every address as `//portal/…`, which reads as a link
 *  and points at another host (`DEF-CWP-3925`'s fixture lesson). */
function draw(entry = "/pine-hill/portal/forgot-password") {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route
          path="/:tenant/portal/forgot-password"
          element={
            <>
              <ForgotPasswordView />
              <Where />
              <GoTo />
            </>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

/** Lets a case navigate inside the SAME document, as pasting a link that
 *  differs only by its fragment does in a browser (no reload). */
let goTo: (to: string) => void = () => {};
function GoTo() {
  const navigate = useNavigate();
  goTo = (to) => navigate(to);
  return null;
}

/** What the address bar holds now — the link's secret must not stay there. */
function Where() {
  const { pathname, search, hash } = useLocation();
  return <output data-testid="where">{`${pathname}${search}${hash}`}</output>;
}

afterEach(cleanup);
beforeEach(() => {
  asked = [];
  resets = [];
  resetAnswer = async () => ({ ok: true });
});

describe("CWP-019 · forgotten password (US-CWP-020)", () => {
  /**
   * ⚠ **THE LINK IS DESCRIBED BEFORE THEY ASK FOR IT.** `s5`: *"The link's
   * lifetime is stated before they submit, so a link that has expired is not
   * a surprise."* This screen said nothing at all about the link until after
   * a customer had already asked for one.
   */
  it("says what the link is BEFORE the field, not after the ask", () => {
    draw();
    const lead = document.querySelector("[data-reset-lead]");
    expect(lead, "nothing describes the link before the ask").not.toBeNull();
    expect(lead?.textContent ?? "").toContain("works once");
    // Before it, in the document — not in the confirmation panel.
    expect(document.querySelector("[data-reset-answer]")).toBeNull();
  });

  /**
   * ⚠ **NO LIFETIME FIGURE, AND THAT IS A DELIBERATE ABSENCE.** The drawing
   * reads *"lasts an hour"*; this product's link lasts SEVEN DAYS
   * (`RESET_TTL_DAYS = 7`) and the number is on no payload this screen can
   * read. Writing either would put a figure in front of a customer that
   * nothing keeps true. This case is what goes red the day somebody copies
   * the drawing's number in.
   */
  it("states no lifetime, because none is served", () => {
    draw();
    const body = document.body.textContent ?? "";
    expect(body).not.toMatch(/hour/i);
    expect(body).not.toMatch(/seven days|7 days/i);
  });

  /**
   * ⚠ **THE CONFIRMATION SAYS WHAT TO DO NEXT, NOT WHY WE ANSWER AS WE DO.**
   * It led with *"We answer the same either way."* — our disclosure RATIONALE
   * read out to a customer, which B14 rule 33 keeps off the glass entirely.
   */
  it("the confirmation tells them where to look, and does not explain our policy", async () => {
    draw();
    await userEvent.type(screen.getByLabelText(/Email/), "ana@example.test");
    await userEvent.click(screen.getByRole("button", { name: /Send the link/ }));
    await waitFor(() => expect(document.querySelector("[data-reset-answer]")).not.toBeNull());
    const panel = document.querySelector("[data-reset-answer]")?.textContent ?? "";
    expect(panel).toContain("Check your email.");
    expect(panel).toContain("a link is on its way");
    expect(panel).not.toContain("either way");
    expect(asked).toEqual([{ email: "ana@example.test" }]);
  });

  /**
   * `BR-CWP-038` — there is one answer and no branch that could produce a
   * second. The panel is a constant, so this compares the rendered string for
   * two different addresses; it passes only because there is nothing here that
   * could differ.
   */
  it("BR-CWP-038: the same panel, byte for byte, whatever address is typed", async () => {
    async function answerFor(email: string): Promise<string> {
      draw();
      await userEvent.type(screen.getByLabelText(/Email/), email);
      await userEvent.click(screen.getByRole("button", { name: /Send the link/ }));
      await waitFor(() => expect(document.querySelector("[data-reset-answer]")).not.toBeNull());
      const html = document.querySelector("[data-reset-answer]")?.innerHTML ?? "";
      cleanup();
      return html;
    }
    expect(await answerFor("ana@example.test")).toBe(await answerFor("nobody@example.test"));
  });

  /**
   * ⚠ **A DEAD END HERE IS A PHONE CALL.** `s5` draws *← Sign in*; the kit's
   * shape for it is `WhereNext` at the foot. Somebody who typed the wrong
   * address, or who has just remembered the password, had no door out of this
   * screen but the browser's back button.
   */
  it("carries a way back to signing in", () => {
    draw();
    const back = document.querySelector(
      '[data-where-next="reset"] a[href="/pine-hill/portal/sign-in"]',
    );
    expect(back, "no way back from the reset screen").not.toBeNull();
    expect(back?.getAttribute("href")).not.toMatch(/^\/\//);
  });
});

describe("CWP-019 · a box that holds no address never leaves the screen (DEF-CWP-10380)", () => {
  it("empty: shows 'Please enter your email' inline and sends nothing", async () => {
    draw();
    await userEvent.click(screen.getByRole("button", { name: /Send the link/ }));
    const error = document.querySelector('[data-field-error="reset-email"]');
    expect(error?.textContent).toBe("Please enter your email.");
    expect(screen.getByLabelText(/Email/)).toHaveAttribute("aria-invalid", "true");
    expect(asked).toEqual([]);
    expect(document.querySelector("[data-reset-answer]")).toBeNull();
  });

  it("spaces only count as empty", async () => {
    draw();
    await userEvent.type(screen.getByLabelText(/Email/), "   ");
    await userEvent.click(screen.getByRole("button", { name: /Send the link/ }));
    expect(document.querySelector('[data-field-error="reset-email"]')?.textContent).toBe(
      "Please enter your email.",
    );
    expect(asked).toEqual([]);
  });

  /**
   * ⚠ **F-18 (`DEF-CWP-10550`), PO 2026-10-23:** the ruled sentence, before
   * anything is sent, and the summary takes focus (F-04).
   */
  it("malformed: shows the ruled sentence, focuses the summary and sends nothing", async () => {
    draw();
    await userEvent.type(screen.getByLabelText(/Email/), "maria@");
    await userEvent.click(screen.getByRole("button", { name: /Send the link/ }));
    expect(document.querySelector('[data-field-error="reset-email"]')?.textContent).toBe(
      "Enter a full email, like name@example.com.",
    );
    expect(screen.getByLabelText(/Email/)).toHaveAttribute("aria-describedby", "reset-email-error");
    expect(document.activeElement).toBe(document.querySelector("[data-error-summary]"));
    expect(asked).toEqual([]);
  });

  it("valid: calls the API once, trimmed, and shows the one answer", async () => {
    draw();
    await userEvent.type(screen.getByLabelText(/Email/), "  maria@example.test ");
    await userEvent.keyboard("{Enter}");
    await waitFor(() => expect(document.querySelector("[data-reset-answer]")).not.toBeNull());
    expect(asked).toEqual([{ email: "maria@example.test" }]);
    expect(document.querySelector('[data-field-error="reset-email"]')).toBeNull();
  });
});

/**
 * ⚠ **A HOLD WITH ITS EXPIRY TEST (hard-won law 2).** *Update your registered
 * email* points at `/update-email`, a screen `CR-189-BRC10` builds and this
 * branch does not register. The door is asserted BY ADDRESS under the real
 * route pattern, on the form AND on the answer panel; when `CR-189` registers
 * the route, add its screen id assertion here.
 */
describe("CWP-019 · Not getting the email? (CR-189-BRC10)", () => {
  it("the form carries the update-email door by address", () => {
    draw();
    const door = document.querySelector('[data-update-email="form"] a');
    expect(door?.textContent).toBe("Update your registered email");
    expect(door?.getAttribute("href")).toBe("/pine-hill/portal/update-email");
    expect(document.querySelector('[data-update-email="form"]')?.textContent).toContain(
      "Not getting the email?",
    );
  });

  it("the answer panel carries it too, the same for every address", async () => {
    draw();
    await userEvent.type(screen.getByLabelText(/Email/), "nobody@example.test");
    await userEvent.click(screen.getByRole("button", { name: /Send the link/ }));
    await waitFor(() => expect(document.querySelector("[data-reset-answer]")).not.toBeNull());
    const door = document.querySelector('[data-reset-answer] [data-update-email="answer"] a');
    expect(door?.getAttribute("href")).toBe("/pine-hill/portal/update-email");
  });
});

describe("CWP-018 · the emailed link opens a new-password form (DEF-CWP-10381, US-CWP-020 TC-4)", () => {
  // The secret travels in the FRAGMENT (decision log 2026-10-22, MERGE-ACCESS).
  const LINK = "/pine-hill/portal/forgot-password#ref=row-1&token=secret-abc";
  // A link emailed before that change: still valid for its lifetime.
  const LEGACY_LINK = "/pine-hill/portal/forgot-password?ref=row-1&token=secret-abc";

  it("reads the fragment once and takes it off the address bar", async () => {
    draw(LINK);
    expect(document.querySelector('[data-screen="CWP-018"]')).not.toBeNull();
    await waitFor(() =>
      expect(screen.getByTestId("where").textContent).toBe("/pine-hill/portal/forgot-password"),
    );
    // Still the new-password form after the replace, not the ask form.
    expect(document.querySelector('[data-screen="CWP-018"]')).not.toBeNull();
  });

  it("a link pasted into the tab already showing the ask form opens the new-password form", async () => {
    draw();
    expect(document.querySelector('[data-screen="CWP-018"]')).toBeNull();
    act(() => goTo(LINK));
    await waitFor(() => expect(document.querySelector('[data-screen="CWP-018"]')).not.toBeNull());
    await waitFor(() =>
      expect(screen.getByTestId("where").textContent).toBe("/pine-hill/portal/forgot-password"),
    );
  });

  it("still opens a link emailed with the query form, and strips it too", async () => {
    draw(LEGACY_LINK);
    expect(document.querySelector('[data-screen="CWP-018"]')).not.toBeNull();
    await waitFor(() =>
      expect(screen.getByTestId("where").textContent).toBe("/pine-hill/portal/forgot-password"),
    );
    await userEvent.type(screen.getByLabelText(/^New password/), "Harbor-2026-tide");
    await userEvent.type(screen.getByLabelText(/^Type it again/), "Harbor-2026-tide");
    await userEvent.click(screen.getByRole("button", { name: /Save new password/ }));
    await waitFor(() => expect(document.querySelector("[data-reset-done]")).not.toBeNull());
    expect(resets).toEqual([{ ref: "row-1", token: "secret-abc", password: "Harbor-2026-tide" }]);
  });

  it("opens with the password fields empty and spends the link on save", async () => {
    draw(LINK);
    expect(document.querySelector('[data-screen="CWP-018"]')).not.toBeNull();
    const first = screen.getByLabelText(/^New password/) as HTMLInputElement;
    const second = screen.getByLabelText(/^Type it again/) as HTMLInputElement;
    expect(first.value).toBe("");
    expect(second.value).toBe("");
    await userEvent.type(first, "Harbor-2026-tide");
    await userEvent.type(second, "Harbor-2026-tide");
    await userEvent.click(screen.getByRole("button", { name: /Save new password/ }));
    await waitFor(() => expect(document.querySelector("[data-reset-done]")).not.toBeNull());
    expect(resets).toEqual([{ ref: "row-1", token: "secret-abc", password: "Harbor-2026-tide" }]);
    const signIn = document.querySelector('[data-where-next="reset-done"] a');
    expect(signIn?.getAttribute("href")).toBe("/pine-hill/portal/sign-in");
  });

  it("a used or expired link says so and offers a new one", async () => {
    const { ApiError } = await import("@/api/client");
    resetAnswer = async () => {
      throw new ApiError(422, { code: null, message_key: "portal.reset.link.expired" });
    };
    draw(LINK);
    await userEvent.type(screen.getByLabelText(/^New password/), "Harbor-2026-tide");
    await userEvent.type(screen.getByLabelText(/^Type it again/), "Harbor-2026-tide");
    await userEvent.click(screen.getByRole("button", { name: /Save new password/ }));
    await waitFor(() => expect(document.querySelector("[data-reset-dead]")).not.toBeNull());
    expect(document.querySelector("[data-reset-dead]")?.textContent).toContain(
      "This link has expired.",
    );
    const again = document.querySelector('[data-where-next="reset-dead"] a');
    expect(again?.getAttribute("href")).toBe("/pine-hill/portal/forgot-password");
  });

  it("a password the policy refuses names what is missing and keeps the form", async () => {
    const { ApiError } = await import("@/api/client");
    resetAnswer = async () => {
      throw new ApiError(422, {
        code: null,
        message_key: "portal.reset.policy",
        params: { failures: ["needs_digit"], min_length: 8 },
      });
    };
    draw(LINK);
    await userEvent.type(screen.getByLabelText(/^New password/), "Harbortide");
    await userEvent.type(screen.getByLabelText(/^Type it again/), "Harbortide");
    await userEvent.click(screen.getByRole("button", { name: /Save new password/ }));
    await waitFor(() =>
      expect(document.querySelector('[data-field-error="reset-new"]')?.textContent).toBe(
        "Add a number.",
      ),
    );
    expect(document.querySelector("[data-reset-dead]")).toBeNull();
  });
});

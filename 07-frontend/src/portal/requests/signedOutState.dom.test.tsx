// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-062 (CWP-052) · US-CWP-037 (CWP-032)
// Rules:    R-10 (the way out beside the message) · R-22 (three states, three
//           SENTENCES) · `CPB-17` (a signed-out visitor at a signed-in address
//           is offered a sign-in) · BR-CWP-007 (the tenant is read off the
//           address)
// Defect:   DEF-CWP-4931 — signed out, `/stop-or-restart` and `/final-bill`
//           drew the STAFF failure panel: *Failed · We could not open this
//           page · Retry · Download error report · Cancel*, and no sign-in.
//
// ⚠ **WHAT THIS PROVES AND WHAT IT CANNOT (hard-won law 1).** It proves the
// card is built, that its two ways out are real, and that the sign-in address
// is a real portal path rather than `//portal/sign-in`. It CANNOT prove that
// the two pages actually pass it to `Signed`, because that is composition in a
// page wrapper — `10-scripts/render-checks/cr085-lane3-start-and-stop.mjs`
// step 5 opens both addresses signed out at 390 and 1280 and is the only thing
// that can.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import { useSignedOutState } from "./signedOutState";

function Harness(props: { kind: "loading" | "failed"; retry: () => void }) {
  const draw = useSignedOutState();
  return draw(
    { kind: props.kind, sentence: "You're signed out. Sign in again to continue.", retry: props.retry },
    "Opening your account…",
  );
}

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NOT BARE** — hard-won law 2's last
 * clause. A component mounted outside `/:tenant/portal/…` builds every address
 * from an undefined `tenant`, and `//portal/sign-in` reads as a perfectly good
 * string to `toContain` while being a protocol-relative URL to another host.
 */
function draw(kind: "loading" | "failed", retry = () => undefined) {
  return render(
    <MemoryRouter initialEntries={["/brazosbend/portal/stop-or-restart"]}>
      <Routes>
        <Route
          path="/:tenant/portal/stop-or-restart"
          element={<Harness kind={kind} retry={retry} />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(cleanup);

describe("a signed-out customer at a signed-in address (DEF-CWP-4931)", () => {
  it("R-22 — loading and failed are the same card and DIFFERENT sentences", () => {
    const loading = draw("loading");
    expect(loading.container.querySelector("[data-portal-state]")?.getAttribute("data-portal-state")).toBe(
      "loading",
    );
    expect(loading.container.textContent).toContain("Opening your account…");
    cleanup();
    const failed = draw("failed");
    expect(failed.container.querySelector("[data-portal-state]")?.getAttribute("data-portal-state")).toBe(
      "failed",
    );
    expect(failed.container.textContent).toContain("You're signed out.");
    expect(failed.container.textContent).not.toContain("Opening your account");
  });

  it("R-10 — the way out is INSIDE the card, beside the sentence", () => {
    const { container } = draw("failed");
    const card = container.querySelector("[data-portal-state]") as HTMLElement;
    const signIn = card.querySelector('[data-way-out="sign-in"]') as HTMLAnchorElement;
    expect(signIn).not.toBeNull();
    expect(signIn.textContent).toBe("Sign in");
    // ⚠ A REAL ADDRESS, so ⌘-click opens it in a second tab — and it carries
    // the tenant, which is the half `BR-CWP-007` is about.
    expect(signIn.getAttribute("href")).toBe("/brazosbend/portal/sign-in");
    expect(signIn.getAttribute("href")).not.toMatch(/^\/\//);
  });

  it("the retry is wired to something", () => {
    const retry = vi.fn();
    const { container } = draw("failed", retry);
    const button = container.querySelector('[data-way-out="retry"]') as HTMLButtonElement;
    expect(button).not.toBeNull();
    button.click();
    expect(retry).toHaveBeenCalledTimes(1);
  });

  it("the staff's Download error report is gone from a customer's screen", () => {
    const { container } = draw("failed");
    expect(container.textContent).not.toContain("Download error report");
    expect(container.textContent).not.toContain("Cancel");
  });

  it("a loading card offers NO way out — there is nothing yet to do about it", () => {
    const { container } = draw("loading");
    expect(container.querySelector("[data-ways-out]")).toBeNull();
  });
});

// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-058 (EP-CWP-10) · Screen: CWP-056
// Rules:    BR-CWP-089 (the portal never grants a protection) · BR-CWP-090
//           (the certificate hold expires and the copy says so) · BR-CWP-066
//           (a plan is granted by a clerk) · B14 rule 33
// Open:     OQ-CWP-1601 — all three routes stay open past the final notice
// Cases:    three cards · the moratorium is a fact WITH NO CONTROL · the
//           certificate card says the hold expires · no upload anywhere · the
//           plan card absent where plans are off and the other two remain ·
//           past the final notice nothing is closed · the ask creates a request
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalHelpPaying } from "../api/portalClient";

let readHelp: () => Promise<PortalHelpPaying> = async () => {
  throw new Error("no behaviour set");
};
const asked: { route: string }[] = [];
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return {
    ...actual,
    getHelpPaying: () => readHelp(),
    askForHelpPaying: async (_id: string, body: { route: string }) => {
      asked.push(body);
      return {
        reference: "SR-26-0093",
        protection_created: false,
        granted_by: "clerk",
        bring_the_document: true,
      };
    },
  };
});

const { HelpPayingView } = await import("./HelpPaying");

/** `US-CWP-058` §4 — `$412.60` overdue, moratorium 1 Dec 2026 → 1 Mar 2027. */
const HELP: PortalHelpPaying = {
  as_of: "2026-09-02",
  routes: [
    { route: "payment_plan", still_open: true, granted_by: "clerk", asks_for: "service_request" },
    {
      route: "medical_certificate", still_open: true, granted_by: "clerk",
      asks_for: "service_request", hold_expires: true, upload_available: false,
    },
    { route: "level_pay", still_open: true, granted_by: "clerk", asks_for: "service_request" },
  ],
  plans_enabled: true,
  past_final_notice: false,
  moratorium: { from: "2026-12-01", until: "2027-03-01", apply: false, set_by: "regulator" },
};

/** ⚠ **MOUNTED UNDER THE REAL PATH PATTERN — IT WAS NOT, AND THAT IS THE
 *  FIXTURE DEFECT HARD-WON LAW 2 NAMES BY NAME.** A bare `MemoryRouter` with no
 *  `/:tenant/portal` route leaves `useParams().tenant` undefined, so every
 *  address this screen builds comes out `//portal/…` — a protocol-relative URL
 *  to ANOTHER HOST that reads as a perfectly good string to `toContain`. The
 *  one assertion that could catch a broken door could not be written here at
 *  all until this route was added (`CR-085` step 2, lane 7). */
function draw(body: PortalHelpPaying) {
  readHelp = async () => body;
  return render(
    <MemoryRouter initialEntries={["/pine-hill/portal/help-paying"]}>
      <Routes>
        <Route
          path="/:tenant/portal/help-paying"
          element={<HelpPayingView accountId="acc-1" />}
        />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  asked.length = 0;
  cleanup();
});

describe("CWP-056 · help paying (US-CWP-058)", () => {
  it("TC-1 — three cards, in the blueprint's order", async () => {
    const { container } = draw(HELP);
    await screen.findByText("Spread it out");
    expect(container.querySelectorAll("[data-errand]")).toHaveLength(3);
    expect(container.querySelector("[data-errand='payment_plan']")).toBeTruthy();
    expect(container.querySelector("[data-errand='medical_certificate']")).toBeTruthy();
    expect(container.querySelector("[data-errand='level_pay']")).toBeTruthy();
  });

  it("TC-2 · negative — the moratorium is a FACT and there is NO control on it", async () => {
    // ⚠ Nobody applies for a weather moratorium, so the assertion is that no
    // control EXISTS — not that one is disabled.
    const { container } = draw(HELP);
    await screen.findByText("Spread it out");
    const bar = container.querySelector("[data-moratorium]");
    expect(bar?.textContent).toContain("2026-12-01");
    expect(bar?.textContent).toContain("2027-03-01");
    expect(bar?.textContent).toContain("You do not have to ask for that");
    expect(bar?.querySelector("button")).toBeNull();
    expect(bar?.querySelector("a")).toBeNull();
  });

  it("TC-3 · negative — the certificate card says IN WORDS that the hold expires", async () => {
    // ⚠ A customer who believes a hold is permanent stops paying and is
    // disconnected the week it lapses.
    const { container } = draw(HELP);
    const card = await screen.findByText(/A doctor's certificate can hold your supply/);
    expect(card.textContent).toContain("It has an end date and it is not permanent");
    expect(container.textContent).not.toContain("permanently");
  });

  it("TC-5 · negative — there is no file input anywhere on this screen", async () => {
    // ⚠ Consumer upload is a signed deferral; the route ends at the counter.
    const { container } = draw(HELP);
    await screen.findByText("Spread it out");
    expect(container.querySelector("input[type='file']")).toBeNull();
  });

  it("TC-6 · negative — plans off removes ONE card and leaves the other two", async () => {
    // ⚠ **THE ASSERTION THAT MATTERS.** A customer who cannot have a plan can
    // still send a certificate; hiding all three would turn away somebody who
    // could still be helped.
    const { container } = draw({
      ...HELP,
      plans_enabled: false,
      routes: HELP.routes.filter((row) => row.route !== "payment_plan"),
    });
    await screen.findByText("Someone here is unwell");
    expect(container.querySelectorAll("[data-errand]")).toHaveLength(2);
    expect(container.querySelector("[data-errand='payment_plan']")).toBeNull();
    expect(container.querySelector("[data-errand='level_pay']")).toBeTruthy();
  });

  it("TC-8 · negative — past the final notice NOTHING is closed, and time is said to be short", async () => {
    // ⚠ `OQ-CWP-1601`. Nothing in this product closes a hardship route, and
    // closing a door the product would still open turns a frightened customer
    // away from help they can still get.
    const { container } = draw({ ...HELP, past_final_notice: true });
    await screen.findByText("Spread it out");
    expect(container.querySelectorAll("[data-errand]")).toHaveLength(3);
    expect(container.textContent).toContain("Your final notice has already gone out");
    expect(container.textContent).toContain("All three are still open");
  });

  it("TC-4 · negative — asking creates a REQUEST and says no hold is in place", async () => {
    const { container } = draw(HELP);
    const button = await screen.findByRole("button", { name: "Send a certificate" });
    fireEvent.click(button);
    await waitFor(() => expect(container.querySelector("[data-ask-sent]")).toBeTruthy());
    expect(asked).toEqual([{ route: "medical_certificate" }]);
    expect(container.querySelector("[data-ask-sent]")?.textContent).toContain("SR-26-0093");
    expect(container.querySelector("[data-bring-document]")?.textContent).toContain(
      "Nothing is on hold yet",
    );
  });

  it("B14 rule 33 — the refusal on the used-up control is five or six words", async () => {
    const { container } = draw(HELP);
    const button = await screen.findByRole("button", { name: "Send a certificate" });
    fireEvent.click(button);
    await waitFor(() => expect(container.querySelector("[data-ask-sent]")).toBeTruthy());
    const held = container.querySelector("button[disabled]");
    expect(held?.getAttribute("title")).toBe("You have already asked today");
    expect(held?.getAttribute("title")?.split(" ")).toHaveLength(5);
  });

  it("R-10 — a failed read on the HELP screen still names a way to get help", async () => {
    // ⚠ **THE SCREEN SOMEBODY OPENS BECAUSE THEY CANNOT PAY** ended in a full
    // stop: *we could not read this* and no control of any kind.
    let calls = 0;
    readHelp = async () => {
      calls += 1;
      if (calls === 1) throw new Error("down");
      return HELP;
    };
    const { container } = render(
      <MemoryRouter initialEntries={["/pine-hill/portal/help-paying"]}>
        <Routes>
          <Route
            path="/:tenant/portal/help-paying"
            element={<HelpPayingView accountId="acc-1" />}
          />
        </Routes>
      </MemoryRouter>,
    );
    await screen.findByText("We could not read this right now. Try again in a moment.");
    // ⚠ **THE WHOLE ADDRESS.** A bare `/ask-for-a-plan` resolves to
    // `//portal/ask-for-a-plan`, which is another host.
    expect(
      container
        .querySelector('[data-portal-state="failed"] [data-way-out="ask-for-a-plan"]')
        ?.getAttribute("href"),
    ).toBe("/pine-hill/portal/ask-for-a-plan");
    fireEvent.click(container.querySelector('[data-way-out="try-again"]') as HTMLElement);
    expect(await screen.findByText("Spread it out")).toBeInTheDocument();
    expect(calls).toBe(2);
  });

});

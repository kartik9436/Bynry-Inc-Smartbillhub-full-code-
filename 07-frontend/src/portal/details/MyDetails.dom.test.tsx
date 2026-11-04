// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-028 (EP-CWP-06) · Screen: CWP-024
// Rules:    BR-CWP-026 (the legal name and the account holder are SHOWN and
//           refused, with a route) · BR-CWP-086 (returned post ABOVE the
//           address field) · BR-CWP-103 (no second password prompt) · B14
//           rule 31 (no database id on screen) · rule 33 (a refusal is five or
//           six words)
// Cases:    the three editable fields · the two refused ones, present and
//           read-only · how far the save reaches, said BEFORE the button ·
//           the returned-post banner and its position · the disagreement
//           helper · the failed read
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/i18n";

import type { PortalMyDetails } from "../api/portalClient";

// A plain function, not `vi.fn()` — a recording stand-in reaches a rejected
// promise before the screen's own `.catch` does.
let readDetails: () => Promise<PortalMyDetails> = async () => {
  throw new Error("no behaviour set");
};
vi.mock("../api/portalClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/portalClient");
  return { ...actual, getMyDetails: () => readDetails(), saveMyDetails: async () => ({ accounts_updated: 4, account_ids: [] }) };
});

const { MyDetailsView } = await import("./MyDetails");

const BASE: PortalMyDetails = {
  as_of: "2026-09-04",
  email: "m.alvarez@example.com",
  email_varies: false,
  phone: "(512) 555-4218",
  phone_varies: false,
  postal: {
    line1: "1408 Elm St",
    line2: null,
    city: "Austin",
    state: "TX",
    postal_code: "78704",
    country: null,
  },
  postal_varies: false,
  legal_name: "Maria Alvarez",
  returned_post_accounts: 0,
  account_count: 4,
  refused: ["legal_name", "account_holder"],
  locales: ["en", "es", "es-MX", "de", "hi", "fr-FR", "id-ID", "it-IT", "ja-JP", "ko-KR", "pt-BR"],
  locale: "es-MX",
  security: { password_changed_on: "2026-03-04", code_channel: "sms", devices_signed_in: 2 },
};

function inRouter(node: JSX.Element) {
  return (
    <MemoryRouter initialEntries={["/pine-hill/portal/my-details"]}>
      <Routes>
        <Route path="/:tenant/portal/my-details" element={node} />
      </Routes>
    </MemoryRouter>
  );
}

function draw(details: Partial<PortalMyDetails> = {}) {
  readDetails = async () => ({ ...BASE, ...details });
  return render(inRouter(<MyDetailsView />));
}

afterEach(cleanup);

describe("CWP-024 · my details (US-CWP-028)", () => {
  it("says how far a save reaches BEFORE the button, not in a toast after it", async () => {
    // ⚠ Four accounts, one contact row each. A customer who did not know that
    // would have no reason to expect the other three to change.
    const { container } = draw();
    await screen.findByDisplayValue("m.alvarez@example.com");
    expect(container.querySelector("[data-my-details-reach]")?.textContent).toContain("4");
  });

  it("the three editable fields hold what the server sent", async () => {
    draw();
    expect(await screen.findByDisplayValue("m.alvarez@example.com")).toBeTruthy();
    expect(screen.getByDisplayValue("(512) 555-4218")).toBeTruthy();
    expect(screen.getByDisplayValue("1408 Elm St")).toBeTruthy();
  });

  it("BR-CWP-026 — the legal name is SHOWN, and it is not an input", async () => {
    // ⚠ A field left out reads as an oversight and sends somebody hunting.
    // Shown, read-only, with *Ask us to change this*, it reads as a rule.
    const { container } = draw();
    await screen.findByDisplayValue("m.alvarez@example.com");
    const shown = container.querySelector("[data-legal-name]");
    expect(shown?.textContent).toBe("Maria Alvarez");
    expect(shown?.querySelector("input")).toBeNull();
    expect(screen.getByText("Ask us to change this")).toBeTruthy();
  });

  it("BR-CWP-086 — the returned-post line sits ABOVE the address field", async () => {
    // ⚠ POSITION IS THE ASSERTION. A banner under the field it is about is a
    // banner somebody corrects the address without ever reading.
    const { container } = draw({ returned_post_accounts: 2 });
    await screen.findByDisplayValue("m.alvarez@example.com");
    const banner = container.querySelector("[data-returned-post]");
    const address = container.querySelector("[data-field='my-postal-line1']");
    expect(banner).toBeTruthy();
    expect(address).toBeTruthy();
    expect(banner!.compareDocumentPosition(address!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(banner!.textContent).toContain("2");
  });

  it("no banner at all when no post has come back (BR-CWP-093)", async () => {
    const { container } = draw();
    await screen.findByDisplayValue("m.alvarez@example.com");
    expect(container.querySelector("[data-returned-post]")).toBeNull();
  });

  it("says so when the login's accounts DISAGREE, rather than showing one silently", async () => {
    const { container } = draw({ email_varies: true });
    await screen.findByDisplayValue("m.alvarez@example.com");
    const field = container.querySelector("[data-field='my-email']");
    expect(field?.textContent).toContain("do not all hold the same value");
  });

  it("the save control is held until something has actually changed", async () => {
    // B14 rule 33 — five words, on the control.
    const { container } = draw();
    await screen.findByDisplayValue("m.alvarez@example.com");
    const button = container.querySelector("button[disabled]");
    expect(button).toBeTruthy();
    expect(button?.getAttribute("title")).toContain("Nothing has changed");
  });

  it("BR-CWP-103 — there is no second password prompt on this screen", async () => {
    // ⚠ The PO's ruling put the defence at the door. A password box here would
    // be the friction that ruling removed, so its ABSENCE is asserted.
    const { container } = draw();
    await screen.findByDisplayValue("m.alvarez@example.com");
    expect(container.querySelector("input[type='password']")).toBeNull();
  });

  it("B14 rule 31 — no database id reaches the page", async () => {
    const { container } = draw();
    await screen.findByDisplayValue("m.alvarez@example.com");
    expect(container.textContent).not.toMatch(/[0-9a-f]{8}-[0-9a-f]{4}-/);
  });

  it("hard-won law 2 — the door to CWP-025 is on this screen", async () => {
    // ⚠ **`/my-details/preferences` HAS A ROUTE AND THE SHELL'S SIX TABS ARE
    // FIXED**, so without this link the preferences screen renders nothing a
    // person can get to: *built is not wired*, and every test would still pass.
    const { container } = draw();
    await screen.findByDisplayValue("m.alvarez@example.com");
    expect(
      container.querySelector('a[href="/pine-hill/portal/my-details/preferences"]'),
    ).not.toBeNull();
  });

  it("T4 — two EQUAL panels, and the right column spaces its two cards (CWP-024)", async () => {
    // ⚠ **`DEF-CWP-4016`.** `08-screen-layouts.md` writes this screen's shape
    // in the kit's own words — *"→ `TwoEqual`: `Panel` **CONTACT** … ·
    // `Panel` **SIGN-IN** … with a `Panel.Warning` beneath it"* — and the
    // screen composed `TwoCol`, which is 62/35 and puts a peer panel in a
    // rail slot. It NAMES the component and got the other one.
    //
    // ⚠ **THE SECOND ASSERTION IS THE ONE THAT MATTERS AND IT IS WHY THE KIT
    // MOVED FIRST.** This column holds TWO `Card`s, and `Card` carries no
    // margin of its own — so before `TwoEqual` gained `flex flex-col gap-4`
    // (the fix `DEF-CWP-3984` made to `TwoCol` one component along), moving
    // this screen would have drawn them FLUSH. A screen that renders and
    // looks wrong passes every check in this repo.
    const { container } = draw();
    await screen.findByDisplayValue("m.alvarez@example.com");
    const right = container.querySelector("[data-screen='CWP-024'] [data-two-equal-right]");
    expect(right).not.toBeNull();
    expect(right?.className).toContain("gap-4");
    expect(right?.querySelectorAll("section").length ?? 0).toBeGreaterThanOrEqual(2);
    expect(container.querySelector("[data-screen='CWP-024'] [data-twocol-rail]")).toBeNull();
  });

  it("says so when the read fails, rather than drawing empty inputs", async () => {
    readDetails = async () => {
      throw new Error("read failed");
    };
    const { container } = render(inRouter(<MyDetailsView />));
    expect(await screen.findByText("We could not read your details.")).toBeTruthy();
    expect(container.querySelector("input")).toBeNull();
  });
});

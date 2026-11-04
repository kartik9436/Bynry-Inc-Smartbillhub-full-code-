// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Defects:  DEF-CWP-10552 (F-04, focus drops to the body) · DEF-CWP-10553
//           (F-17, the selectors) · DEF-CWP-10548 (F-03)
// Rulings:  PO/QA 2026-10-23 — "It still switches instantly. Focus stays on the
//           selector, and a screen reader hears 'Showing account
//           AC-2026-00057'… Each selector's label says it changes the page";
//           "Arrow keys will switch only" (read as: the arrow keys DO switch).
// Cases:    KEYBOARD-ONLY runs that fail when focus lands on the body:
//           an Ask card opens its form (focus on the form's heading), Back
//           returns to the card that opened it, a refused Send lands on the
//           summary; the account selector keeps focus and is announced.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import type { ApiClient } from "@/api/client";

import type { PortalAccount } from "../api/portalClient";
import { forgetLastPortalPath, PortalA11y } from "../components/a11y";
import { QuickServiceBody } from "../guest/QuickService";
import { AccountSwitcher } from "./PortalShell";

afterEach(() => {
  cleanup();
  forgetLastPortalPath();
});

const notBody = () => expect(document.activeElement, "focus fell to the body").not.toBe(document.body);

const CATEGORIES = [
  { code: "leak", label: "Report a leak", hint: null, needs_bill_number: false },
  { code: "billing", label: "A billing question", hint: null, needs_bill_number: false },
];

const client = {
  get: async () => ({ status: 200, data: { categories: CATEGORIES } }),
  post: async () => {
    throw new Error("not in this test");
  },
} as unknown as ApiClient;

function drawAsk() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <MemoryRouter initialEntries={["/pine-hill/portal/ask"]}>
        <PortalA11y>
          <main>
            <Routes>
              <Route path="/:tenant/portal/ask" element={<QuickServiceBody client={client} />} />
            </Routes>
          </main>
        </PortalA11y>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Press a control the way a keyboard user does: focus it, then Enter/Space
 *  (a `<button>` turns that into a click). */
function pressKey(element: Element) {
  (element as HTMLElement).focus();
  fireEvent.keyDown(element, { key: "Enter" });
  fireEvent.click(element);
}

describe("F-04 · the Ask cards, keyboard only", () => {
  it("Ask → moves focus to the form's heading; Back returns it to the card that opened it", async () => {
    drawAsk();
    const card = await screen.findByText("Ask →", { selector: '[data-action="ask-billing"]' });
    pressKey(card);
    await waitFor(() => expect(document.activeElement?.tagName).toBe("H1"));
    expect(document.activeElement?.textContent).toContain("A billing question");
    notBody();

    pressKey(document.querySelector('[data-action="cancel-ask"]')!);
    await waitFor(() =>
      expect(document.activeElement).toBe(document.querySelector('[data-action="ask-billing"]')),
    );
    notBody();
  });

  it("Send with the required boxes empty lands on the summary and sends nothing", async () => {
    drawAsk();
    pressKey(await screen.findByText("Ask →", { selector: '[data-action="ask-leak"]' }));
    await waitFor(() => expect(document.querySelector('[data-action="send-ask"]')).not.toBeNull());
    pressKey(document.querySelector('[data-action="send-ask"]')!);
    await waitFor(() => expect(document.activeElement).toBe(document.querySelector("[data-error-summary]")));
    expect(document.getElementById("quick-name")).toHaveAttribute("aria-invalid", "true");
    expect(document.querySelector("[data-portal-alert]")?.textContent).toContain("Fill this in.");
  });
});

const ACCOUNTS = [
  { id: "a1", account_no: "AC-2026-00012", label: "14 Oak St", is_master: false },
  { id: "a2", account_no: "AC-2026-00057", label: "9 Elm Ave", is_master: false },
] as unknown as PortalAccount[];

describe("F-17 · the account selector", () => {
  function Bar() {
    const [current, setCurrent] = useState("a1");
    // The page re-renders under the selector, as a real account switch does.
    return (
      <PortalA11y>
        <main>
          <h1>Bills</h1>
          <AccountSwitcher key={current} accounts={ACCOUNTS} current={current} onChange={setCurrent} />
        </main>
      </PortalA11y>
    );
  }

  it("says it changes the page, switches on an arrow key, keeps focus and is announced", async () => {
    render(
      <MemoryRouter>
        <Bar />
      </MemoryRouter>,
    );
    const select = screen.getByLabelText("Account (changes the page)");
    select.focus();
    // An arrow key changes a <select>'s value at once; that is the pick.
    fireEvent.keyDown(select, { key: "ArrowDown" });
    fireEvent.change(select, { target: { value: "a2" } });
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 600));
    });
    const now = document.querySelector('select[data-account-switcher="select"]');
    expect(document.activeElement).toBe(now);
    expect((now as HTMLSelectElement).value).toBe("a2");
    expect(document.querySelector("[data-portal-status]")?.textContent).toBe("Showing account AC-2026-00057");
  });
});

// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-088 follow-on — the product name in two sizes and two colours
//          (decision log 2026-10-02, "THE PRODUCT NAME IS SET IN TWO SIZES AND
//          TWO COLOURS"). PO: "A · Two sizes, as in the example. On the pricing
//          and sign-in help pages it would be 16px and 12px. and two differnt
//          colors".
// Rules:   B14 rule 43 (one component, three callers) · rule 44 (type-scale
//          steps only) · WCAG 1.4.3 (the accent step that passes on each surface)
// ───────────────────────────────────────────────────────
// ⚠ THIS FILE TESTS THE THREE PLACES THE NAME IS DRAWN, NOT THE COMPONENT ON
// ITS OWN. A component test passes the day the component exists, whether or not
// anybody renders it (hard-won law 2). Asserting on the side menu, the pricing
// page and the sign-in help page is what makes this go red on the old code —
// where each drew `t("app.name")` as one run of text at one size.
//
// **RED PROVED FIRST**, on the pre-change tree (all six cases failed):
//
//     Error: no [data-product-name] inside the side menu's brand
//
// The sizes are asserted as the type-scale UTILITY CLASSES, not computed pixels:
// jsdom has no stylesheet, so a computed font-size would be "" and the case
// incapable of failing. The pixels are proved in Chromium (see the lane report).
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { queryKeys } from "@/api/queryClient";
import { PricingPage } from "@/features/public/PricingPage";
import { SignInHelpPage } from "@/features/identity/SignInHelpPage";

import { AppShell } from "./AppShell";

afterEach(cleanup);

function lockup(scope: ParentNode, where: string): HTMLElement {
  const el = scope.querySelector<HTMLElement>("[data-product-name]");
  if (el === null) {
    throw new Error(`no [data-product-name] inside ${where}`);
  }
  return el;
}

function part(el: HTMLElement, which: "family" | "edition"): HTMLElement {
  const p = el.querySelector<HTMLElement>(`[data-product-name-part="${which}"]`);
  if (p === null) {
    throw new Error(`no ${which} part`);
  }
  return p;
}

/** Every class of `expected` is on the element. */
function hasClasses(el: HTMLElement, expected: string) {
  for (const c of expected.split(" ")) {
    expect(el.classList.contains(c), `${c} on ${el.outerHTML}`).toBe(true);
  }
}

/** Screen readers hear the full name ONCE: the two visual parts are hidden
 *  from them and one visually-hidden run carries "SMART360 Next". */
function readsOnce(el: HTMLElement) {
  expect(part(el, "family")).toHaveAttribute("aria-hidden", "true");
  expect(part(el, "edition")).toHaveAttribute("aria-hidden", "true");
  const spoken = Array.from(el.querySelectorAll<HTMLElement>(":not([aria-hidden='true'])"))
    .filter((n) => n.children.length === 0 && n.closest("[aria-hidden='true']") === null)
    .map((n) => n.textContent);
  expect(spoken).toEqual(["SMART360 Next"]);
}

describe("the side menu draws SMART360 at 18px and Next at 14px in the accent", () => {
  function brand(): HTMLElement {
    render(
      <MemoryRouter initialEntries={["/brazosbend/accounts"]}>
        <Routes>
          <Route path="/:tenant" element={<AppShell onSignOut={() => undefined} />}>
            <Route path="accounts" element={<p>body</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    const b = document.querySelector<HTMLElement>(".sidebar .brand");
    if (b === null) throw new Error("no sidebar brand");
    return lockup(b, "the side menu's brand");
  }

  it("two parts, the right sizes and colours", () => {
    const el = brand();
    expect(part(el, "family").textContent).toBe("SMART360");
    expect(part(el, "edition").textContent).toBe("Next");
    // 18px extra-bold, colour inherited unchanged from the ink panel.
    hasClasses(part(el, "family"), "text-brand font-extrabold");
    // 14px, lighter, the accent's step that passes AA on ink (5.26:1).
    hasClasses(part(el, "edition"), "text-md font-semibold text-accent-500");
    // Still hidden on the collapsed rail by the shell's own rule.
    expect(el.classList.contains("brand-name")).toBe(true);
  });

  it("reads 'SMART360 Next' once to a screen reader", () => {
    readsOnce(brand());
  });
});

describe("the pricing page draws SMART360 at 16px and Next at 12px in the accent", () => {
  function brand(): HTMLElement {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    qc.setQueryData(queryKeys.pricingPlans, []);
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <PricingPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    const b = document.querySelector<HTMLElement>("[data-public-brand]");
    if (b === null) throw new Error("no public brand");
    return lockup(b, "the pricing page's brand");
  }

  it("two parts, the right sizes and colours", () => {
    const el = brand();
    hasClasses(part(el, "family"), "text-lead font-extrabold text-text");
    // 12px, lighter, the accent's step that passes AA on the page (6.41:1).
    hasClasses(part(el, "edition"), "text-sm font-semibold text-accent-700");
  });

  it("reads 'SMART360 Next' once to a screen reader", () => {
    readsOnce(brand());
  });
});

describe("the sign-in help page draws SMART360 at 16px and Next at 12px in the accent", () => {
  function mount() {
    render(
      <MemoryRouter initialEntries={["/signin-help"]}>
        <SignInHelpPage appHost="utilities.example.test" />
      </MemoryRouter>,
    );
  }

  it("two parts, the right sizes and colours", () => {
    mount();
    const b = document.querySelector<HTMLElement>("[data-public-brand]");
    if (b === null) throw new Error("no public brand");
    const el = lockup(b, "the sign-in help page's brand");
    hasClasses(part(el, "family"), "text-lead font-extrabold text-text");
    hasClasses(part(el, "edition"), "text-sm font-semibold text-accent-700");
  });

  it("the home link's accessible name is 'SMART360 Next'", () => {
    mount();
    const link = screen.getByRole("link", { name: "SMART360 Next" });
    expect(link).toHaveAttribute("data-public-brand");
    readsOnce(lockup(link, "the home link"));
  });
});

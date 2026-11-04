// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-012 (EP-CWP-04) · US-CWP-015 — Screens: CWP-008 · CWP-010 ·
//           wireframes/CWP-008.png · CWP-010.png
// Rules:    US-CWP-012 TC-1 (the four rows and their figures) · TC-2 (an
//           unknown address is not a refusal) · TC-4 (NOT HERE, never $0.00) ·
//           BR-CWP-021 (no person, no id) · B14 rule 31 · rule 36 / r10 rule 6
//           (the danger tier is for destructive commits and nothing here is
//           one) · hard rule 2 (the screen renders `display`, never `amount`)
// Cases:    at the first paint, in a real renderer
// ─────────────────────────────────────────────────────────────────────────
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";

import type { QuickServiceCategory } from "../api/guestClient";

import { QuickServiceBody } from "./QuickService";
import { StartServiceBody } from "./StartService";

/**
 * ⚠ **`PALM_CT` AND ITS THREE `MoneyCell` HELPERS LIVED HERE AND HAVE MOVED TO
 * `StartService.dom.test.tsx` (`DEF-CWP-3941`, closed).** They sat unused
 * behind an `eslint-disable` for exactly as long as CWP-008's priced answer had
 * no test — `US-CWP-012`'s own signed figures, `$185.00` to connect and
 * `$150.00` on the first bill, kept rather than deleted so that something in
 * the repo still said the assertion was owed.
 *
 * **This file could never have made it.** It renders with
 * `renderToStaticMarkup` and seeds the react-query cache, and the availability
 * read is a `useMutation` driven by local `useState` — there is no query key to
 * seed, and a priced row is reachable only by typing an address and pressing a
 * button. The cases below therefore assert the screen BEFORE anything is
 * typed, including that no priced table is drawn yet, and that is all they can
 * assert. The DOM file next door owns what happens after.
 */

/** A client that answers the two reads these bodies make, and nothing else. */
function clientFor(over: Record<string, unknown> = {}): ApiClient {
  const answers: Record<string, unknown> = {
    "/portal/public/front": {
      tenant: { slug: "pine-hill", name: "Pine Hill Water & Power", brand_primary_hex: "#EC3013", brand_accent_hex: "#E15B47" },
      is_live: true,
      // `PORTAL_LOCALES` — the two the portal OFFERS (`BR-CWP-106`). This body
      // is typed `unknown`, so nothing but this line keeps it honest.
      locales: ["en", "es"],
      cards: [],
      links: { help: false, visit: false },
      services: [],
      strapline: null,
      office_hours_text: null,
      emergency_phone: null,
    },
    ...over,
  };
  const find = (path: string) => {
    const key = Object.keys(answers).find((one) => path.startsWith(one));
    return { data: key === undefined ? undefined : answers[key], status: 200 };
  };
  return {
    get: async (path: string) => find(path),
    post: async () => ({ data: undefined, status: 200 }),
    put: async () => ({ data: undefined, status: 200 }),
    patch: async () => ({ data: undefined, status: 200 }),
    delete: async () => ({ data: undefined, status: 200 }),
  } as unknown as ApiClient;
}

/**
 * ⚠ **A STATIC RENDER DOES NOT WAIT FOR A QUERY**, so anything the screen
 * fetches is SEEDED into the cache first — the shape `FrontPage.test.tsx`
 * already uses. Without it every one of these assertions would be made against
 * a loading skeleton and would fail for a reason that has nothing to do with
 * the screen.
 */
function render(node: React.ReactElement, seed: [readonly unknown[], unknown][] = []): string {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  for (const [key, value] of seed) queryClient.setQueryData(key, value);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/pine-hill/portal/start-service"]}>{node}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CWP-008 · can I get service here (US-CWP-012)", () => {
  it("draws the address box and the two rail panels before anything is typed", () => {
    const html = render(<StartServiceBody client={clientFor()} />);
    expect(html).toContain('data-screen="CWP-008"');
    expect(html).toContain('data-field="availability-address"');
    // ⊕ `DEF-CWP-9817` — the blueprint's p31 draws FOUR boxes, in this order:
    // Street address · Town · ZIP code · *Is there a unit or apartment number?*
    const order = ["availability-address", "availability-town", "availability-zip", "availability-unit"].map(
      (id) => html.indexOf(`data-field="${id}"`),
    );
    expect(order.every((at) => at >= 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
    for (const label of ["Street address", "Town", "ZIP code", "Is there a unit or apartment number?"]) {
      expect(html).toContain(label);
    }
    // WCAG 1.3.5 — the browser may fill each part.
    expect(html).toContain('autoComplete="address-line1"');
    expect(html).toContain('autoComplete="postal-code"');
    expect(html).toContain('autoComplete="address-line2"');
    // The rail says an unknown address is not a refusal — BEFORE anybody has
    // typed one, which is when a person is deciding whether to bother.
    expect(html).toContain("not a refusal");
    // ⚠ NOTHING IS DRAWN UNTIL THE SERVER HAS ANSWERED. An empty table would
    // be a screen inventing a fact it does not have.
    expect(html).not.toContain("data-minitable");
  });

  it("uses no danger-tier control: nothing here is a destructive commit (r10 rule 6)", () => {
    const html = render(<StartServiceBody client={clientFor()} />);
    expect(html).toContain('data-variant="primary"');
    expect(html).not.toContain('data-variant="danger"');
    // r10 rule 5: two sizes only, and both of them come from the kit.
    for (const match of html.matchAll(/data-size="([a-z]+)"/g)) {
      expect(["default", "sm"]).toContain(match[1]);
    }
  });

  /**
   * `DEF-CWP-<no-reason>` — **every disabled control says why it is disabled**
   * (`BR-SHL-025`, the rule `CommitButton`'s docstring states in those words;
   * `BR-CWP-056`). *Check →* was greyed with nothing on it at all — no visible
   * sentence and no `title` — on one of only four working doors the public
   * front page has, while every other refusal in this portal carries a
   * sentence: *"Fill in both boxes first."*, *"Choose a topic and write
   * something."*, *"We cannot take card payments yet."*
   *
   * ⚠ **THE ASSERTION IS OVER EVERY DISABLED BUTTON ON THE SCREEN, NOT OVER
   * THIS ONE.** A bare `<Button disabled>` is valid TSX that renders, `tsc` has
   * nothing to say about it and no gate counts them — which is exactly how one
   * shipped. Written this way, the NEXT one fails here on the day it is added.
   */
  it("no disabled control is greyed without saying why (BR-SHL-025)", () => {
    const html = render(<StartServiceBody client={clientFor()} />);
    const disabled = [...html.matchAll(/<button\b[^>]*>/g)]
      .map((m) => m[0])
      .filter((tag) => tag.includes("disabled"));
    expect(disabled.length).toBeGreaterThan(0);
    for (const tag of disabled) {
      expect(tag).toMatch(/title="[^"]+"/);
    }
    // And the words are the ones a person can act on — B14 rule 33's five or
    // six, naming the box above it, with no rule id in sight (rule 32).
    expect(html).toContain('title="Fill in street, town and ZIP."');
  });

  it("renders no wireframe style: nothing dashed, monospaced or annotated (B14 rule 36)", () => {
    const html = render(<StartServiceBody client={clientFor()} />);
    for (const banned of ["border-dashed", "font-mono", "tracking-wider"]) {
      expect(html).not.toContain(banned);
    }
  });
});

describe("CWP-010 · ask for a quick service (US-CWP-015)", () => {
  const categories: QuickServiceCategory[] = [
    { code: "re_read", label: "portal.quick.re_read.title", hint: "portal.quick.re_read.hint", needs_bill_number: false },
    { code: "standpipe_permit", label: "Standpipe permit", hint: null, needs_bill_number: false },
  ];

  it("draws one card per category the SERVER sent, and the boundary sentence", () => {
    const html = render(<QuickServiceBody client={clientFor()} />, [
      [["portal", "quick-services"], { categories }],
    ]);
    expect(html).toContain('data-errand="re_read"');
    expect(html).toContain('data-errand="standpipe_permit"');
    expect(html).toContain("A meter reading looks wrong");
    // TC-7 — a utility's OWN wording shows verbatim, because `t()` returns an
    // unknown key unchanged. This is what makes a renamed category work.
    expect(html).toContain("Standpipe permit");
    expect(html).toContain("needs you to sign in or call us");
  });

  it("draws NOTHING when the utility has switched requests off (TC-4, BR-CWP-093)", () => {
    const html = render(<QuickServiceBody client={clientFor()} />, [
      [["portal", "quick-services"], { categories: [] }],
    ]);
    // Absent, not greyed, and no heading over an empty grid.
    expect(html).not.toContain("data-errand");
    expect(html).not.toContain("needs you to sign in or call us");
  });
});

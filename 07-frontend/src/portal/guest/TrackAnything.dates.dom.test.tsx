// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-010 (EP-CWP-03) · Screen: CWP-012
// Change:   CR-085 (2026-09-08) — the drawing's own headline for this screen:
//           *"The status has a time attached — 'expected fixed today, by 4 PM'
//           — because 'in progress' with no date is what makes somebody
//           phone."* and, for a finished report, *"Fixed — green, with what was
//           done and when — a report that ends silently reads as ignored."*
// Rules:    BR-CWP-024 (progress and never data) · BR-CWP-093 (absent, never
//           an empty row) · B14 rule 31 · rule 35
// Cases:    a found report draws `expected_back_on` · a closed one draws
//           `resolved_at` · neither row exists when the server sent no date ·
//           no figure and no person reaches the panel either way
//
// ⚠ **WHY THIS FILE EXISTS AT ALL, AND IT IS THE UNCOMFORTABLE PART.** The
// FOUND panel — the whole point of `CWP-012` — had never been rendered by any
// test. `TrackAnything.test.tsx` renders the empty form; the payment file
// renders the empty form and asserts two pure functions. So the branch that
// draws what somebody actually came here to read was reachable only by a real
// lookup, which is why two dates the server has always sent could sit undrawn
// for weeks with a green suite over them (hard-won law 2, read the other way
// round: a FACT with no control in front of it).
//
// ⚠ **ITS OWN FILE, hard-won law 11**, for the reason the payment file next to
// it gives verbatim: several lanes are in this tree, a pathspec commit takes
// the whole working-tree content of every path it names, and a new path
// collides with nobody.
// ─────────────────────────────────────────────────────────────────────────
import "@testing-library/jest-dom/vitest";

import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import type { PortalFront, TrackView } from "../api/guestClient";
import { PortalRegionalProvider } from "../components/regional";

import { TrackAnything } from "./TrackAnything";

/** A live report: a crew is on the way and a date has been promised. */
const IN_PROGRESS: TrackView = {
  series: "report",
  reference: "SR-26-0049",
  status: "crew_on_site",
  reported_at: "2026-09-02T14:52:00Z",
  kind: "leak_or_burst",
  location_text: "near 1412 Elm St",
  expected_back_on: "2026-09-08",
  resolved_at: null,
};

/** The same report, finished. */
const FINISHED: TrackView = {
  ...IN_PROGRESS,
  status: "resolved",
  expected_back_on: null,
  resolved_at: "2026-09-08T16:04:00Z",
};

/** A report nobody has put a date against yet — the third state, and the one
 *  that must draw NEITHER row rather than two dashes. */
const NO_DATES: TrackView = {
  ...IN_PROGRESS,
  status: "looking_into_it",
  expected_back_on: null,
  resolved_at: null,
};

function clientAnswering(body: TrackView): ApiClient {
  return {
    get: async () => ({ data: undefined, status: 200 }),
    post: async () => ({ data: body, status: 200 }),
    put: async () => ({ data: undefined, status: 200 }),
    patch: async () => ({ data: undefined, status: 200 }),
    del: async () => ({ data: undefined, status: 200 }),
  } as unknown as ApiClient;
}

/** A Texas utility: `MM/DD/YYYY` and `America/Chicago`, which is what the real
 *  `GET /public/front` answers for the demo tenant. */
const FRONT = {
  tenant: { slug: "pine-hill", name: "Pine Hill Water & Power", brand_primary_hex: null, brand_accent_hex: null },
  is_live: true,
  regional: { timezone: "America/Chicago", date_format: "MM/DD/YYYY", language: null },
  locales: ["en", "es"],
  cards: [],
  links: { help: true, visit: true },
  services: [],
  strapline: null,
  office_hours_text: null,
  emergency_phone: null,
} as unknown as PortalFront;

/** ⚠ **MOUNTED UNDER THE REAL PATH PATTERN** (`DEF-CWP-3925`) — a bare
 *  `MemoryRouter` leaves `useParams().tenant` undefined and every address the
 *  page builds comes out `//portal/…`, which reads as a perfectly good string
 *  to `toContain`. */
async function lookUp(body: TrackView, front?: PortalFront): Promise<HTMLElement> {
  const screen = <TrackAnything client={clientAnswering(body)} />;
  const { container } = render(
    <MemoryRouter initialEntries={["/pine-hill/portal/track"]}>
      <Routes>
        <Route
          path="/:tenant/portal/track"
          element={
            front === undefined ? (
              screen
            ) : (
              // The real screen's frame publishes this; the frame is not under
              // test here, only what the screen does with what it publishes.
              <PortalRegionalProvider front={front}>{screen}</PortalRegionalProvider>
            )
          }
        />
      </Routes>
    </MemoryRouter>,
  );
  const reference = container.querySelector("#cwp012-reference") as HTMLInputElement;
  const second = container.querySelector("#cwp012-second-fact") as HTMLInputElement;
  fireEvent.change(reference, { target: { value: body.reference } });
  fireEvent.change(second, { target: { value: "78702" } });
  fireEvent.click(container.querySelector("button:not([disabled])") as HTMLButtonElement);
  // The found panel replaces the *what you would see* note.
  await waitFor(() => expect(container.querySelector("[data-reference]")).not.toBeNull());
  return container as HTMLElement;
}

afterEach(cleanup);

describe("CWP-012 · the dates on a found report (CR-085)", () => {
  it("draws the date it is expected fixed, which is what stops the phone call", async () => {
    const container = await lookUp(IN_PROGRESS);
    const row = container.querySelector("[data-expected-fixed]");
    expect(row).not.toBeNull();
    // The value is the server's own date; outside a frame no tenant format is
    // published, so `usePortalDate` hands it back unchanged — which is the
    // documented behaviour and not a gap (`DEF-SHL-3964`: a default here would
    // be a plausible wrong answer).
    expect(row?.textContent).toBe("2026-09-08");
    // The catalogue's word, never the key (B14 rule 35 · `DEF-CWP-3952`).
    expect(container.textContent).toContain("Expected fixed");
    expect(container.textContent).not.toContain("portal.track.");
  });

  it("draws WHEN it was fixed once it is, so a finished report does not end silently", async () => {
    const container = await lookUp(FINISHED);
    expect(container.querySelector("[data-fixed]")).not.toBeNull();
    expect(container.textContent).toContain("Fixed");
    // The two are alternatives on a report, not a pair: nothing is expected any
    // more once it is done.
    expect(container.querySelector("[data-expected-fixed]")).toBeNull();
  });

  it("draws NEITHER row when the server sent no date (BR-CWP-093)", async () => {
    const container = await lookUp(NO_DATES);
    // ⚠ A row reading *Expected fixed —* tells somebody an estimate exists and
    // has been withheld. No row says the true thing: nobody has set one.
    expect(container.querySelector("[data-expected-fixed]")).toBeNull();
    expect(container.querySelector("[data-fixed]")).toBeNull();
    expect(container.textContent).not.toContain("Expected fixed");
  });

  // ⚠ **EVERY DATE ON THIS PANEL GOES THROUGH THE TENANT'S OWN FORMAT AND
  // ZONE** (`BR-SHL-023`, `DEF-CWP-4197`). *Reported* used to be drawn by
  // `reportedAtText`, which reads the BROWSER's locale and the BROWSER's zone:
  // a report rung in at 9:52am in Texas printed *Sep 2, 2026, 2:52 PM*. The
  // receipt screen was fixed for exactly this a fortnight earlier and this
  // screen kept the fault, one directory away.
  //
  // ⚠ It also gave the panel two date formats side by side the moment the rows
  // above landed, which is how it was noticed at all — by looking (law 6).
  it("draws every date in the tenant's zone and format, not the browser's (CR-085)", async () => {
    const container = await lookUp(IN_PROGRESS, FRONT);
    const text = container.textContent ?? "";
    // 14:52 UTC is 9:52 in Chicago. The old rendering said 2:52 PM.
    expect(text).toContain("09/02/2026");
    expect(text).toContain("9:52");
    expect(text).not.toContain("2:52 PM");
    // And the date-only row carries no invented time.
    expect(container.querySelector("[data-expected-fixed]")?.textContent).toBe("09/08/2026");
  });

  it("BR-CWP-024 — the found panel still carries no figure and no person", async () => {
    const container = await lookUp(IN_PROGRESS);
    expect(container.innerHTML).not.toMatch(/\$\d/);
    expect(container.innerHTML).not.toMatch(
      /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
    );
  });
});

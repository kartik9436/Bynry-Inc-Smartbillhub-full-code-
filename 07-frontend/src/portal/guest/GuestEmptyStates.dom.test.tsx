// @vitest-environment jsdom
//
// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-072 (help, and one answer) · US-CWP-074 (where you can walk
//           in, and one centre). Screens: CWP-013 · CWP-014 · CWP-060
// Rules:    R-22 (PO 2026-09-11, verbatim: *"differntiate it using text
//           message"* — loading, empty and failed are told apart by their
//           SENTENCE) · R-10 (PO 2026-09-11 — *"when a screen tells a customer
//           something bad, the thing they can do about it must be on that same
//           screen, next to the message"*) · BR-CWP-093 · B14 rule 31 (nothing
//           internal is ever a visible value)
// Defects:  DEF-CWP-4853 — a member of the public whose utility shows no
//           counter was handed the STAFF failure panel: a red *Failed* chip,
//           *"We could not find that. It may have been removed, or the address
//           may be wrong."* and a **Download error report** button, rendered
//           OUTSIDE the guest frame so with no utility name, no phone number
//           and no way back.
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **WHY A `.dom` FILE AND NOT A CASE IN `HelpAndCentres.test.tsx`.** That
// suite seeds the query cache and renders to a string, which can express
// *the data arrived* and cannot express *the read was REFUSED* — a cache entry
// has data or it is pending, and an error state is neither. These four cases
// are entirely about what a refusal draws, so the refusal has to be real: the
// reader is mocked, it throws the `ApiError` the server actually sends, and
// the assertion waits for the render that follows.
//
// ⚠ **AND A 404 HERE IS NOT A FAILURE, WHICH IS THE WHOLE DEFECT.**
// `GET portal/public/service-centres` answers 404 ON PURPOSE when the utility
// shows no counter (`BR-CWP-093`, `US-CWP-074` TC-5) — the server refuses the
// page rather than serving a heading with nothing under it. Correct on the
// wire, and the screen read it as *something went wrong*.
import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/i18n";
import { ApiError } from "@/api/client";
import { queryKeys } from "@/api/queryClient";

import type { PortalFront } from "../api/guestClient";

const NOT_FOUND = new ApiError(404, { code: null, message_key: "errors.not-found" });
const BROKEN = new ApiError(503, { code: null, message_key: "errors.unavailable" });

let centresError: unknown = NOT_FOUND;
let centreError: unknown = NOT_FOUND;
let answerError: unknown = NOT_FOUND;

/** Six published answers, so `/help` is in its ordinary state and the visitor
 *  is the one who narrows it. */
const SIX = {
  answers: [
    { slug: "why-is-my-bill-higher-than-last-month", question: "Why is my bill higher than last month?", topic: "billing" },
    { slug: "how-do-i-check-for-a-leak", question: "How do I check for a leak?", topic: "water" },
  ],
  topics: ["billing", "water"],
  visit_link: false,
};

vi.mock("../api/guestClient", async () => {
  const actual = await vi.importActual<Record<string, unknown>>("../api/guestClient");
  return {
    ...actual,
    getPortalCentres: async () => {
      throw centresError;
    },
    getPortalCentre: async () => {
      throw centreError;
    },
    getPortalHelpAnswer: async () => {
      throw answerError;
    },
    getPortalHelp: async () => SIX,
    sendHelpFeedback: async () => undefined,
  };
});

const { CentrePage, CentresPage } = await import("./CentresPage");
const { AnswerPage, HelpPage } = await import("./HelpPage");

const FRONT: PortalFront = {
  tenant: {
    slug: "brazosbend",
    name: "Brazos Bend Utilities",
    brand_primary_hex: "#1B5E9E",
    brand_accent_hex: "#201E1D",
  },
  is_live: true,
  regional: { timezone: "America/Chicago", date_format: "MM/DD/YYYY", language: "en-US" },
  locales: ["en", "es"],
  cards: [],
  links: { help: false, visit: false },
  services: [],
  strapline: null,
  office_hours_text: null,
  emergency_phone: "(281) 555-0164",
};

/** ⚠ MOUNTED UNDER THE REAL PATH PATTERN — hard-won law 2. A bare
 *  `MemoryRouter` leaves `useParams().tenant` undefined and every address the
 *  page builds comes out `//portal/…`, a protocol-relative URL to another host
 *  that reads as a perfectly good string to `toContain`. */
function draw(node: React.ReactElement, path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.portalFront, FRONT);
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/:tenant/portal/visit" element={node} />
          <Route path="/:tenant/portal/visit/:slug" element={node} />
          <Route path="/:tenant/portal/help" element={node} />
          <Route path="/:tenant/portal/help/:slug" element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  centresError = NOT_FOUND;
  centreError = NOT_FOUND;
  answerError = NOT_FOUND;
});
afterEach(cleanup);

describe("DEF-CWP-4853 · a refused public page is not a staff error panel", () => {
  it("CWP-013 · no counters: an EMPTY state, inside the frame, with the phone beside it", async () => {
    const { container } = draw(<CentresPage />, "/brazosbend/portal/visit");
    await waitFor(() =>
      expect(container.querySelector('[data-portal-state="empty"]')).not.toBeNull(),
    );

    // ⚠ **NOT A FAILURE.** R-22: the sentence is what tells the three apart,
    // and this one says what is ABSENT rather than that something broke.
    expect(screen.getByText("No counters are listed here yet.")).toBeInTheDocument();
    expect(container.querySelector('[data-portal-state="failed"]')).toBeNull();

    // ⚠ **NOTHING INTERNAL REACHES A MEMBER OF THE PUBLIC** (B14 rule 31). The
    // staff panel's three tells: the word *Failed*, the sentence that blames
    // the visitor for an address they did not type, and a control offering a
    // customer an error report they have nowhere to send.
    expect(screen.queryByText(/download error report/i)).toBeNull();
    expect(screen.queryByText(/the address may be wrong/i)).toBeNull();

    // ⚠ **AND IT IS INSIDE THE FRAME**, so the utility's name, its nav and its
    // footer are all still there. The old panel replaced the whole page.
    expect(container.querySelector('[data-portal-frame="guest"]')).not.toBeNull();
    expect(container.querySelector('[data-screen="CWP-013"]')).not.toBeNull();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);

    // ⚠ **R-10 — the way out, beside the message.** The drawing's whole
    // `NONE CONFIGURED` state is one sentence: *"Falls back to the phone
    // number rather than an empty page."*
    expect(screen.getByText("Call (281) 555-0164")).toHaveAttribute(
      "href",
      "tel:2815550164",
    );
    expect(container.querySelector('[data-way-out="front_page"]')).toHaveAttribute(
      "href",
      "/brazosbend/portal",
    );
  });

  it("CWP-013 · a read that really did fail says SO, and offers the retry an empty state must not", async () => {
    // ⚠ **THE MIRROR CASE, AND IT IS WHAT STOPS THE FIX BECOMING ITS OWN
    // DEFECT** (hard-won law 7: ask what would make this check pass wrongly).
    // Reading every refusal as *nothing here* would be the same collapse in
    // the other direction — a customer told the utility has no offices when
    // the truth is that the page did not load.
    centresError = BROKEN;
    const { container } = draw(<CentresPage />, "/brazosbend/portal/visit");
    await waitFor(() =>
      expect(container.querySelector('[data-portal-state="failed"]')).not.toBeNull(),
    );
    expect(screen.getByText("We could not load these places.")).toBeInTheDocument();
    expect(screen.queryByText("No counters are listed here yet.")).toBeNull();
    expect(container.querySelector('[data-way-out="retry"]')).not.toBeNull();
    expect(screen.queryByText(/download error report/i)).toBeNull();
  });

  it("CWP-014 · an address that names no place keeps its back link and offers the list", async () => {
    const { container } = draw(<CentrePage />, "/brazosbend/portal/visit/gone-away");
    await waitFor(() =>
      expect(container.querySelector('[data-portal-state="empty"]')).not.toBeNull(),
    );
    expect(screen.getByText("We cannot find that place.")).toBeInTheDocument();
    expect(screen.queryByText(/download error report/i)).toBeNull();
    // The head — and therefore the ONE door off this address — survives the
    // refused read (`DEF-CWP-4926`, `PortalScreen`).
    expect(container.querySelector('[data-back="visit"]')).not.toBeNull();
    expect(container.querySelector('[data-way-out="all_centres"]')).toHaveAttribute(
      "href",
      "/brazosbend/portal/visit",
    );
  });

  it("CWP-060 · an answer that has moved offers the list, not an error report", async () => {
    const { container } = draw(<AnswerPage />, "/brazosbend/portal/help/gone-away");
    await waitFor(() =>
      expect(container.querySelector('[data-portal-state="empty"]')).not.toBeNull(),
    );
    expect(screen.getByText("We cannot find that answer.")).toBeInTheDocument();
    expect(screen.queryByText(/download error report/i)).toBeNull();
    expect(container.querySelector('[data-back="help"]')).not.toBeNull();
    expect(container.querySelector('[data-way-out="all_answers"]')).toHaveAttribute(
      "href",
      "/brazosbend/portal/help",
    );
  });
});

/**
 * ⚠ **R-22's THIRD SENTENCE ON `CWP-011`, AND IT LIVES HERE BECAUSE IT CANNOT
 * LIVE IN A STATIC RENDER.** *Nothing is published* and *your search matched
 * none of what is* are different facts and the screen now says them
 * differently — but which one renders turns on whether the VISITOR narrowed
 * the list, and the needle is the component's own state. A seeded cache can
 * reach the first; only typing reaches the second.
 */
describe("DEF-CWP-4854 · CWP-011 tells an empty utility from an empty search", () => {
  it("says NOTHING MATCHES only once the visitor has typed, and offers the way back (R-10)", async () => {
    const { container } = draw(<HelpPage />, "/brazosbend/portal/help");
    await waitFor(() => expect(container.querySelector("#cwp011-search")).not.toBeNull());
    // Before anything is typed: two published answers, no state card at all.
    expect(screen.getByText("How do I check for a leak?")).toBeInTheDocument();
    expect(container.querySelector('[data-testid="cwp011-no-match"]')).toBeNull();

    await userEvent
      .setup()
      .type(container.querySelector("#cwp011-search") as HTMLElement, "zzzzqqq");

    await waitFor(() =>
      expect(container.querySelector('[data-testid="cwp011-no-match"]')).not.toBeNull(),
    );
    expect(screen.getByText("Nothing here matches what you typed.")).toBeInTheDocument();
    // ⚠ The OTHER sentence must not be the one on screen — that is the whole
    // of R-22 here, and saying it in one assertion is the point.
    expect(screen.queryByText("No answers are published here yet.")).toBeNull();
    // ⚠ **R-10.** Saying *nothing matches* and leaving the visitor holding the
    // filter that produced it is bad news with no way out.
    expect(container.querySelector('[data-way-out="show_every"]')).not.toBeNull();
    expect(screen.getByText("Show every answer")).toBeInTheDocument();

    // And the search box and the chips STAY, because a control on this screen
    // can undo this emptiness — which is exactly what the published-nothing
    // state must not draw.
    expect(container.querySelector("#cwp011-search")).not.toBeNull();
    expect(container.querySelector("[data-topic-chip]")).not.toBeNull();
  });
});

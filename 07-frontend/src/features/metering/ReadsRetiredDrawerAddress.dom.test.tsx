// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Drawn:    Meter Reads blueprint **entry 19 — "The retired drawer address"**,
//           page 60-61, read as an image (B14 rule 42). Its chips are
//           `EXISTS BEHIND` and `NO COMMITMENT`, and the entry says in its own
//           words why it is listed at all: *"Not a screen — an address. It is
//           listed as its own entry so that nobody later finds a URL nothing in
//           this document describes."*
// Screens:  S25 (`/:tenant/reads`) → S29 (`/:tenant/reads/{id}`)
// Rules:    hard-won law 2 and its MIRROR — a live screen behind a dead
//           control, and the habit that closes it: *"assert the destination by
//           ADDRESS and by the screen id it opens"*
// ───────────────────────────────────────────────────────
//
// ══════════════════════════════════════════════════════════════════════════
// WHY A TEST FOR AN ENTRY WITH NO COMMITMENT CARD
// ══════════════════════════════════════════════════════════════════════════
// Nothing is built here and nothing should be: the blueprint's own rule is that
// *"if a thing is not in a commitment card, nobody has undertaken to build
// it"*, and entry 19 is the one screen in the document that carries
// `NO COMMITMENT` — **the absence is the finding.** The forward already exists
// and is already right.
//
// What did NOT exist is any assertion that it does. `?read=<id>` is the only
// inbound address in this module that no person inside the product ever writes:
// it arrives from a ticket, an email or a bookmark, which was the parameter's
// whole point before the drawer was retired. So the one thing that would notice
// it breaking is a stranger opening a link from August — and by then the
// evidence is gone.
//
// ⚠ **A STRING TEST CANNOT ASK THIS QUESTION.** The forward is a `navigate` in
// an effect, so its destination is not in the markup at all and
// `renderToStaticMarkup` — which every other test of this screen uses — renders
// the LIST perfectly happily while the redirect does nothing. That is the exact
// shape hard-won law 7 calls *looking at the wrong thing*, and it is why this
// file is `jsdom` and asserts the address the browser ends on.
//
// ⚠ **AND IT MOUNTS UNDER THE REAL PATH PATTERN.** A bare `MemoryRouter` with
// no `/:tenant/…` route leaves `useParams().tenant` undefined and every URL the
// page builds comes out `//reads/…` — a protocol-relative URL to another host,
// which reads as a perfectly good string to `toContain`.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ReadsListPage } from "./ReadsListPage";
import { READ_PARAM, readDetailPath } from "./readsShared";

const TEST_TENANT = "brazosbend";
const READ_ID = "3f2a9c41-0000-4000-8000-000000000001";

afterEach(cleanup);

/** The address the browser ended on, printed where a test can read it. */
function WhereAmI() {
  const location = useLocation();
  return <output data-testid="where">{`${location.pathname}${location.search}`}</output>;
}

/**
 * A client that answers nothing.
 *
 * The forward is an effect on the URL and must not depend on a list arriving —
 * a ticket's link has to land on the reading whether or not the page behind it
 * could fetch anything. Leaving the query pending is therefore the harder case,
 * not a shortcut.
 */
const NEVER_ANSWERS = {
  get: () => new Promise<never>(() => undefined),
  post: () => new Promise<never>(() => undefined),
  patch: () => new Promise<never>(() => undefined),
  put: () => new Promise<never>(() => undefined),
  delete: () => new Promise<never>(() => undefined),
} as unknown as ApiClient;

function mountAt(search: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/reads${search}`]}>
          <Routes>
            <Route path="/:tenant/reads" element={<ReadsListPage client={NEVER_ANSWERS} />} />
            <Route path="/:tenant/reads/:readId" element={<WhereAmI />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("Meter Reads entry 19 — the retired drawer address still forwards", () => {
  it("`?read=<id>` lands on the READING, at the address S29 is mounted on", async () => {
    // Entry 19, verbatim: "/:tenant/reads?read=<id> → forwards to entry 03".
    // The assertion is the ADDRESS and not the fact that a navigate happened,
    // because a forward to an address nothing is mounted on opens the router's
    // error boundary and every other check in this repo stays green over it.
    mountAt(`?${READ_PARAM}=${READ_ID}`);
    expect(await screen.findByTestId("where")).toHaveTextContent(
      `/${TEST_TENANT}${readDetailPath(READ_ID)}`,
    );
  });

  it("the parameter is not a general redirect — the plain list still renders", async () => {
    // The other direction, and it is the half that stops this test passing on a
    // screen that forwarded EVERY visit to a reading. A one-directional
    // assertion would be green on exactly that.
    mountAt("");
    expect(screen.queryByTestId("where")).toBeNull();
  });

  it("an EMPTY `?read=` is not an id and must not forward", async () => {
    // `?read=` with nothing after it is what a truncated link in an email looks
    // like. Forwarding it builds `/reads/` — a different route, or none — so the
    // guard is `!== null && !== ""` and this is the case that holds it there.
    mountAt(`?${READ_PARAM}=`);
    expect(screen.queryByTestId("where")).toBeNull();
  });
});

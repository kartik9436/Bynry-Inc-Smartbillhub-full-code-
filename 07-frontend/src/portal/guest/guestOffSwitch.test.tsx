// ── Trace ────────────────────────────────────────────────────────────────
// Story:    US-CWP-001 TC-3 (the portal is off: a holding page, no cards) and
//           every guest story behind it. Screens: CWP-001 · 015 · 016 · 019 ·
//           012 · 006 · 013 · 014 · 011 · 060
// Rules:    CR-068 R8 (a portal that is OFF shows the holding page and nothing
//           else, on EVERY route) · CLAUDE.md hard-won law 3 (defaults fail
//           closed — `PortalSettings.is_live` is False until a person turns it
//           on) · BR-CWP-005
// Defects:  DEF-CWP-4851 — NINE of the ten guest routes ignored the switch.
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **WHY THIS FILE EXISTS SEPARATELY FROM THE TEN SCREENS' OWN SUITES, AND IT
// IS THE WHOLE POINT OF IT.**
//
// Every one of these screens was already tested — 71 files and 960 cases were
// green on the morning this was written. Each suite mounts ITS OWN screen at
// ITS OWN address against a fixture whose `is_live` is **true**, because that
// is the state the screen is interesting in. So the question *does this screen
// respect the switch* belonged to no suite at all, and the answer was **no**
// on nine of the ten: measured in a browser at 390 and at 1280 with
// `is_live:false` on the wire, `/sign-in` served a live sign-in box, `/enrol`
// the whole three-step enrolment wizard, `/forgot-password` a live
// password-reset mailer, and `/track`, `/report`, `/help`, `/visit` and the
// two detail screens their full screens — at a utility that had not opened its
// portal. Only `/` held.
//
// That is `DEF-CWP-3925`'s shape one layer down — a rule each wave was correct
// about locally and nobody owned globally — and the cure is the same: **one
// case that walks the WHOLE SET**, so a route added later either appears in
// this table or is visibly missing from it.
//
// ⚠ **IT IS THE CLIENT'S HALF AND IT SAYS SO (hard-won law 1).** What is
// asserted here is exactly one thing: **no screen RENDERS behind the switch.**
// Two things are NOT asserted here and each is proved somewhere else or not at
// all. That no content READ is issued behind it is a browser fact and lives in
// `10-scripts/cr085_lane2_guest_walkthrough.mjs` — see `renderAt` below for why
// this file cannot make that claim. And that the SERVER refuses is not this
// layer's to assert at all: `guest_api.py` guards
// `is_live` on quick pay and on requests and on nothing else, so
// `POST portal/public/reports` and `GET portal/public/help` still answer on a
// switched-off tenant. That half is filed (`DEF-CWP-4938`) rather than implied
// green by a passing client test.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import { queryKeys } from "@/api/queryClient";

import type { ErrandCardKey, ErrandCardOffer, PortalFront } from "../api/guestClient";
import { EnrolPage, ForgotPasswordPage, SignInPage } from "../signin/SignInPages";

import { CentrePage, CentresPage } from "./CentresPage";
import { FrontPage } from "./FrontPage";
import { AnswerPage, HelpPage } from "./HelpPage";
import { ReportPage } from "./ReportPage";
import { TrackPage } from "./TrackPage";

const CARD_KEYS: ErrandCardKey[] = [
  "pay_bill",
  "report_problem",
  "check_my_area",
  "start_service",
  "what_things_cost",
  "help_answers",
];

/** What `GET public/front` answers for a utility that has not opened its
 *  portal: the name and the colours so the page is still theirs, `is_live`
 *  false, and no cards (`selectors.py` — the holding page's data). */
const OFF: PortalFront = {
  tenant: {
    slug: "pine-hill",
    name: "Pine Hill Water & Power",
    brand_primary_hex: "#EC3013",
    brand_accent_hex: "#E15B47",
  },
  is_live: false,
  regional: { timezone: "America/Chicago", date_format: "MM/DD/YYYY", language: "en-US" },
  locales: ["en", "es"],
  cards: [],
  links: { help: false, visit: false },
  services: [],
  strapline: null,
  office_hours_text: null,
  emergency_phone: null,
};

const ON: PortalFront = {
  ...OFF,
  is_live: true,
  cards: CARD_KEYS.map(
    (key): ErrandCardOffer => ({ key, available: true as const, reason_code: null }),
  ),
  links: { help: true, visit: true },
  emergency_phone: "(512) 555-0100",
};

/**
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NEVER A BARE `MemoryRouter`**
 * (hard-won law 2). Without a `/:tenant/portal/...` route, `useParams().tenant`
 * is `undefined` and every address the page builds comes out `//portal/…` — a
 * protocol-relative URL to another host, which reads as a perfectly good string
 * to `toContain`.
 *
 * ⚠ **`queryFn` THROWS ON PURPOSE, AND HERE IS WHAT THAT DOES AND DOES NOT
 * PROVE (hard-won law 1).** Nothing is seeded but the front payload, so a
 * screen that reached for its content with a real client would fail loudly
 * rather than quietly render a skeleton. **What it does NOT prove is the
 * second half of `DEF-CWP-4851` — that a switched-off portal issues no content
 * READ.** `renderToStaticMarkup` runs no effects, so react-query never starts
 * a fetch here whatever `enabled` says; a version of these screens with the
 * flag taken back out would pass this file unchanged. The no-read half is
 * proved where it can be — in a browser, by
 * `10-scripts/cr085_lane2_guest_walkthrough.mjs`. This is a tripwire, not the
 * guarantee, and it is written down as one.
 */
function renderAt(node: React.ReactElement, path: string, front: PortalFront): string {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        queryFn: () => {
          throw new Error("a switched-off portal must not read anything");
        },
      },
    },
  });
  queryClient.setQueryData(queryKeys.portalFront, front);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/:tenant/portal" element={node} />
          <Route path="/:tenant/portal/sign-in" element={node} />
          <Route path="/:tenant/portal/enrol" element={node} />
          <Route path="/:tenant/portal/forgot-password" element={node} />
          <Route path="/:tenant/portal/track" element={node} />
          <Route path="/:tenant/portal/report" element={node} />
          <Route path="/:tenant/portal/visit" element={node} />
          <Route path="/:tenant/portal/visit/:slug" element={node} />
          <Route path="/:tenant/portal/help" element={node} />
          <Route path="/:tenant/portal/help/:slug" element={node} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** The ten addresses of the guest entrance, each with the screen id it opens
 *  and the element a person would have used if the switch had been ignored. */
const ROUTES: Array<{
  name: string;
  path: string;
  screen: string;
  node: React.ReactElement;
  /** A string that appears ONLY when this screen actually rendered. */
  tell: string;
}> = [
  // ⚠ **NOT `data-screen="CWP-001"` FOR THIS ONE.** The holding page carries
  // that mark too — it IS `CWP-001`, in its off state — so a `tell` of the
  // screen id is a check that cannot pass on the one route the whole rule
  // started on. `data-door="enrol"` is the sign-in bar's *Set up your login*,
  // which only the live front page draws.
  { name: "the landing page", path: "/pine-hill/portal", screen: "CWP-001", node: <FrontPage />, tell: "data-door=\"enrol\"" },
  { name: "sign in", path: "/pine-hill/portal/sign-in", screen: "CWP-015", node: <SignInPage />, tell: "portal-password" },
  { name: "enrol", path: "/pine-hill/portal/enrol", screen: "CWP-016", node: <EnrolPage />, tell: "enrol-account" },
  { name: "forgotten password", path: "/pine-hill/portal/forgot-password", screen: "CWP-019", node: <ForgotPasswordPage />, tell: "reset-email" },
  { name: "track", path: "/pine-hill/portal/track", screen: "CWP-012", node: <TrackPage />, tell: "cwp012-reference" },
  { name: "report a problem", path: "/pine-hill/portal/report", screen: "CWP-006", node: <ReportPage />, tell: "cwp006-where" },
  { name: "where to find us", path: "/pine-hill/portal/visit", screen: "CWP-013", node: <CentresPage />, tell: "data-screen=\"CWP-013\"" },
  { name: "one service centre", path: "/pine-hill/portal/visit/main-office", screen: "CWP-014", node: <CentrePage />, tell: "data-screen=\"CWP-014\"" },
  { name: "help", path: "/pine-hill/portal/help", screen: "CWP-011", node: <HelpPage />, tell: "cwp011-search" },
  { name: "one answer", path: "/pine-hill/portal/help/how-do-i-check-for-a-leak", screen: "CWP-060", node: <AnswerPage />, tell: "data-answer-body" },
];

describe("CR-068 R8 · the portal's on/off switch reaches every guest route (DEF-CWP-4851)", () => {
  for (const route of ROUTES) {
    it(`${route.name} (${route.screen}) shows the holding page when the portal is off`, () => {
      const html = renderAt(route.node, route.path, OFF);
      // The holding notice, and the utility's own name on it.
      expect(html).toContain('data-holding="true"');
      expect(html).toContain("We are not open online yet.");
      expect(html).toContain("Pine Hill Water &amp; Power");
      // And NOT the screen behind it. `tell` is a string this screen renders
      // and the holding page never does, so this is the assertion that fails
      // the day somebody draws the frame directly again.
      expect(html).not.toContain(route.tell);
      // ⚠ **NO NAV, NO LANGUAGE CONTROL, NO BRAND LINK** — `US-CWP-001` TC-3:
      // a clickable brand on a switched-off portal is still a door.
      expect(html).toContain('data-live="false"');
      expect(html).not.toContain('data-link="brand_home"');
    });
  }

  // ⚠ **THE MIRROR CASE, AND IT IS NOT OPTIONAL** (hard-won law 7: ask what
  // would make this check pass WRONGLY). Every assertion above also passes on
  // a portal that never renders anything at all, so without this case a
  // catastrophically broken guest surface would read as ten green ticks.
  it("and the same ten routes DO render once the utility switches it on", () => {
    for (const route of ROUTES) {
      const html = renderAt(route.node, route.path, ON);
      expect(html, `${route.name} with the portal ON`).not.toContain('data-holding="true"');
      expect(html, `${route.name} with the portal ON`).toContain('data-live="true"');
    }
  });
});

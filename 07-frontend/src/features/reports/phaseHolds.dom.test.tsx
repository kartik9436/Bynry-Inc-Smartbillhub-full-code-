// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  PO ruling 2026-09-26, verbatim — *"go as per phases - tasks"*
//          (12-governance/02-decision-log.md, commit 76be101a3). Screen 1·1
//          ships in Phase 1 WITHOUT the four-tab strip and WITHOUT
//          `+ Build your own`; the strip is Phases 3-4 and the builder is
//          Phase 5.  Screens: S44
// Rules:   CLAUDE.md hard-won law 2, THE MIRROR — *"G13 asks whether a prop is
//          passed; nothing asks whether a REFUSAL is still true"* — and its
//          own prescription: **WHEN YOU WRITE A HOLD, WRITE THE TEST THAT
//          FIRES WHEN THE HOLD EXPIRES, IN THE SAME COMMIT, and assert the
//          destination BY ADDRESS AND BY THE SCREEN ID IT OPENS.**
//          B14 rule 33 (rationale is zero words on screen).
// ───────────────────────────────────────────────────────
//
// THE TWO HOLDS ON SCREEN 1·1, AND WHAT MAKES EACH OF THEM GO RED.
//
// ── WHY THIS FILE EXISTS AT ALL ─────────────────────────────────────────────
//
// On 2026-09-05 the customer portal's front page had **two working doors out of
// eight**. Five cards, the sign-in bar and three of the frame's four nav words
// were all still refusing over `CWP-002`, `CWP-008`, `CWP-011`, `CWP-013` and
// `CWP-015` — every one of those screens shipped days earlier. 42 portal test
// files, 391 cases, `tsc` and every gate were green over it, because each wave
// tested ITS OWN screen at ITS OWN address and the question *has the door
// started pointing at it* belonged to nobody.
//
// The mechanism is **a rule with a clock in it**: a control held *until its
// screen lands* is correct the day it is written and rots silently on the day
// the screen arrives, because landing a screen and releasing the thing that
// pointed at it are two acts and only the first one feels like the work.
//
// ── SO EACH HOLD IS ASSERTED FROM BOTH ENDS ────────────────────────────────
//
//   1 · THE CONTROL IS ABSENT FROM THE CATALOGUE TODAY. That half alone is
//       worthless: it passes for ever, including long after it should not.
//   2 · THE DESTINATION IS STILL A RESERVED PLACEHOLDER, BY ADDRESS AND BY THE
//       SCREEN ID IT OPENS. **That is the half with the clock in it.** The day
//       Phase 3 mounts the History tab at `/{tenant}/reports/history`, the
//       element behind that address stops being `ReportsTabRoute`, this file
//       goes RED, and its message names the tab that now needs a strip.
//
// ⚠ **BY ADDRESS *AND* BY SCREEN ID, BECAUSE EITHER ALONE PASSES ON THE BUG.**
// `DEF-REP-6812` is the worked case from this very screen: `/settings/audit-log`
// MATCHED a route perfectly well — `settings/:tab` — and opened Settings →
// Company. An address assertion with no screen assertion would have been green
// on it. And a hold-expiry test in this repo has already failed the other way
// round: one asserted a screen was REGISTERED at an address while the router
// was mounting it somewhere else, and both addresses opened onto *"not built
// yet"*, so every check passed.
//
// ⚠ **AND THE MOUNT IS THE REAL ROUTER, NOT A BARE `MemoryRouter`.** The portal
// fixture that hid all of this mounted its component with no `/:tenant/portal`
// pattern, so `useParams().tenant` was `undefined` and every address came out
// `//portal/…` — a protocol-relative URL to another host, which reads as a
// perfectly good string to `toContain`.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider, createMemoryRouter, matchRoutes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import type { ApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import type { ReportLibraryResponse } from "@/api/reportsEndpoints";
import { shellBootSeed } from "@/components/shellBootSeed";
import { resolveScreen } from "@/routing/screenIds";

import { ReportsTabRoute } from "./ReportsTabRoute";
import { ReportEditorPage } from "./ReportEditorPage";
import { ReportLibraryPage } from "./ReportLibraryPage";
import { REPORTS_ROUTE, REPORT_BUILDER_NEW_ROUTE } from "./reportsShared";

afterEach(cleanup);

const TENANT = "brazosbend";

/**
 * The four tabs p19 draws, with the phase that lands each and the screen id
 * its address opens today.
 *
 * `Catalogue` is not here: it is the screen this file is about and it is built.
 * The other three are what the strip would point AT, and every one of them is
 * still `ReportsTabRoute` — the reserved-segment placeholder `P0.8` mounted so
 * `/reports/:reportKey` could never swallow four ordinary English words.
 */
/**
 * ⚠ **TWO OF THE THREE ARE GONE, AND THEIR REMOVAL IS THE MECHANISM WORKING
 * RATHER THAN A TEST BEING WEAKENED (lane REP-P4, `P4.5`, 2026-09-27).**
 *
 * This list held `History`, `Dashboard` and `Scheduled`. `History` stopped
 * being a placeholder in `007510e95` (`P3.1`–`P3.6`, 2026-09-27) and
 * `Scheduled` in `P4.5`, and each expiry case went RED and said in its own
 * failure message what to do: draw the tab and delete the case. The tabs are
 * drawn in `ReportsTabs.LIVE_REPORT_TABS`; the cases are deleted here.
 *
 * ⚠ **THE `History` ONE WAS RED FOR THREE COMMITS BEFORE THIS LANE READ IT.**
 * `007510e95` mounted `ReportRunsPage` at `/reports/history` and touched
 * neither this file nor `routing/reportsReservedSegments.test.tsx`, so three
 * true reds sat in the suite unattributed — hard-won law 7's *proved red, then
 * never read*, which is the shape CLAUDE.md names as the one this project
 * actually fails in. It was found by reading a failure this lane did not cause
 * and dating it with `git log -S`, which is the habit the law prescribes and
 * the only thing that would have found it.
 *
 * ⚠ **AND `Dashboard` WENT THE SAME WAY THE SAME DAY — `P4.11`–`P4.13`, lane
 * REP-P4-DASH — SO `HELD_TABS` IS EMPTY AND THE STRIP IS NO LONGER OWED.** Its
 * expiry case went RED with the sentence it was written to say — *"no longer
 * opens the reserved placeholder, so Phase 4 has landed. DRAW THE FOUR-TAB
 * STRIP … and delete this case"* — and was READ before anything was edited.
 * The strip draws all four words in `ReportsTabs.LIVE_REPORT_TABS`.
 *
 * ⚠ **THE LIST IS KEPT AT ZERO RATHER THAN DELETED, AND SO IS THE LOOP.** The
 * next tab this product adds is held the same way, and an empty list with the
 * mechanism intact is one line to fill; a deleted one has to be rediscovered
 * from a PDF. Both cases below iterate it and pass vacuously, which is honest
 * — there is nothing held.
 */
const HELD_TABS: readonly {
  tab: string;
  segment: string;
  phase: string;
  a1: string | null;
}[] = [];


const USER: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@sample.test",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "reports", label: "Reports", access: "Full" }],
};

const LIBRARY: ReportLibraryResponse = {
  groups: [
    {
      code: "receivables",
      name: "Receivables",
      sub_groups: [{ code: "receivables_arrears", name: "Arrears" }],
    },
  ],
  group_total: 1,
  sub_group_total: 1,
  group_options: [{ code: "receivables", name: "Receivables" }],
  cards: [
    {
      key: "ar_aging",
      name: "AR Ageing",
      name_overridden: false,
      group: "receivables",
      group_name: "Receivables",
      sub_group: "receivables_arrears",
      kind: "viewer",
      origin: "built_in",
      badge: "Arrears",
      available: true,
      basis: "posting",
      basis_label: "Posting date",
      reason_code: null,
      reason_detail: null,
      routes_to_screen: null,
      service_codes: [],
      pinned: false,
    },
  ],
  available: 1,
  total: 45,
  count: 1,
  page: 1,
  per: 50,
  pages: 1,
  origin: "standard",
    origin_counts: { standard: 1, custom: 0 },
  q: "",
  group: "",
  service: "",
  vocabularies: {
    services: [],
    bill_types: [],
    purposes: [],
    current_period: null,
    currency: "USD",
    period_unavailable_reason: null,
  },
};

function server(): ApiClient {
  const get = async (path: string) =>
    path === "/reports" ? { data: LIBRARY, status: 200 } : { data: {}, status: 200 };
  const write = async () => ({ data: {}, status: 200 });
  return { request: get, get, post: write, put: write, patch: write, delete: write } as unknown as ApiClient;
}

function openCatalogue() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  queryClient.setQueryData(queryKeys.me, USER);
  queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
  queryClient.setQueryData(
    queryKeys.shellDisplay,
    shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, {
      fy_label: "FY2026",
      period: 9,
      start: "2026-09-01",
      end: "2026-09-30",
      status: "open",
    }),
  );
  const router = createMemoryRouter(
    [{ path: `/:tenant${REPORTS_ROUTE}`, element: <ReportLibraryPage client={server()} /> }],
    { initialEntries: [`/${TENANT}${REPORTS_ROUTE}`] },
  );
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

/** What the ROUTER mounts at an address — the element, not a mirror table. */
function elementAt(address: string): unknown {
  const matches = matchRoutes(APP_ROUTES, address);
  expect(matches, `${address} matches no route at all`).not.toBeNull();
  const leaf = (matches ?? [])[(matches ?? []).length - 1];
  return (leaf?.route as { element?: { type?: unknown } })?.element?.type;
}

// ═══════════════════════════════════════════════════════════════════════════
// HOLD 1 — the four-tab strip (p20 callout ③)
// ═══════════════════════════════════════════════════════════════════════════
describe("HOLD · the four-tab strip is not drawn until the second tab exists", () => {
  it("draws no Dashboard tab on the catalogue today", async () => {
    openCatalogue();
    await screen.findByText("AR Ageing");
    // The SECOND-level strip is built and must stay built — callout ④.
    expect(document.querySelector('[data-sub-tabs="catalogue-origin"]')).not.toBeNull();
    // The first-level one is not.
    for (const held of HELD_TABS) {
      expect(
        screen.queryByRole("tab", { name: held.tab }),
        `${held.tab} is drawn on the catalogue, but it lands in ${held.phase}`,
      ).toBeNull();
    }
  });

  for (const held of HELD_TABS) {
    it(`${held.tab} is still a reserved segment — when it is not, this strip is owed`, () => {
      const address = `/${TENANT}/reports/${held.segment}`;

      // BY ADDRESS: the router still mounts the reserved-segment placeholder.
      expect(
        elementAt(address),
        `${held.tab} → ${address} no longer opens the reserved placeholder, so ` +
          `${held.phase} has landed. DRAW THE FOUR-TAB STRIP on screen 1·1 ` +
          "(05-prototype/09 Reports Build Brief.pdf p19-p20 callout ③) and " +
          "delete this case.",
      ).toBe(ReportsTabRoute);

      // BY THE SCREEN ID IT OPENS: an element assertion alone would pass if a
      // lane mounted a real tab through the same component, and an id
      // assertion alone would pass if the router moved the address.
      expect(
        resolveScreen(address).a1,
        `${held.tab} → ${address} now opens screen id ` +
          `${String(resolveScreen(address).a1)} and not ${String(held.a1)}`,
      ).toBe(held.a1);
    });
  }

  it("the placeholder says three words and explains nothing", () => {
    render(<ReportsTabRoute segment="history" />);
    // B14 rule 33: *why* a tab is not here yet is RATIONALE, and rationale is
    // ZERO words on screen. If this ever grows a sentence, it is the same
    // defect `CorrectionRetentionNote` was deleted for.
    expect(document.body.textContent).not.toMatch(/because|phase|not built yet in/i);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// HOLD 2 — `+ Build your own` — ⚠ **EXPIRED 2026-09-27, CR-142-BRC07 `P5.3`**
// ═══════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE THREE CASES THAT STOOD HERE WERE DELETED, AND DELETING THEM IS HOW
// `DEF-REP-7640` REACHED A PRODUCTION USER (2026-09-28).** The note below is
// kept exactly as it was written, because the reasoning in it is right about
// the cases it names and wrong about what should have replaced them — and
// that difference is the whole lesson. What follows the note is the
// replacement, live, in this file.
//
// ── THE NOTE AS IT WAS WRITTEN ON 2026-09-27 ───────────────────────────────
//
// ⚠ **THE THREE CASES THAT STOOD HERE ARE DELETED, NOT SKIPPED OR COMMENTED
// OUT.** They asserted that `+ Build your own` was NOT drawn, that the Custom
// sub-tab offered no instruction it could not honour, and that
// `/reports/custom` still opened the reserved placeholder. All three were true
// while the builder did not exist and all three are FALSE now:
//
//   · `ReportLibraryPage` draws the action in its page head (p20 callout ②:
//     above the sub-tab strip, not inside Custom — verified against p21's
//     drawing, where 1·2A puts it top right beside the title);
//   · `reports.library.customEmpty.helper` is p22's instruction in all eleven
//     catalogues — *"Open a standard report. Change it. Save it here."*;
//   · `/reports/custom` mounts `ReportLibraryPage` on its second sub-tab.
//
// **This is the same act the lane above performed for `History` and
// `Scheduled`, and for the same reason it gave**: a hold test that outlives its
// hold goes red for the RIGHT reason once and is then ignored, and the next
// reader cannot tell a live assertion from a retired one. The expiry message
// those cases carried is how this lane knew what was owed — law 7 working
// exactly as designed, and the argument for deleting them cleanly rather than
// leaving a monument.
//
// **What replaces them lives where the behaviour does**:
// `reportBuilder.dom.test.tsx` and `10-scripts/rep_p5_builder_walkthrough.mjs`,
// plus `routing/reportsReservedSegments.test.tsx`, which still pins `custom` as
// a RESERVED word even though it now opens a screen — the segment is claimed
// and the save refuses the collision, and both halves are required (`P5.2`,
// `apps/reports/definitions.RESERVED_KEYS`).
//
// ── WHAT WAS WRONG WITH IT (`DEF-REP-7640`, 2026-09-28) ────────────────────
//
// **The last paragraph is a claim about two other files and it was false when
// it was written.** `reportBuilder.dom.test.tsx` mounts `ReportEditPanel` and
// `SaveReportAsModal` DIRECTLY; it never renders `ReportLibraryPage` and has
// no page head in it at all. `rep_p5_builder_walkthrough.mjs` step 0 checks
// the button EXISTS and never presses it. `reportsReservedSegments.test.tsx`
// is about four words, not about a button.
//
// **So after the deletion, `grep -r buildYourOwn` across every test file in
// this repository returned ZERO.** Nothing asserted the control existed, and
// nothing had ever asserted where it LANDS — the destination assertion that
// hard-won law 2's mirror asks for by name (*"assert the destination by
// ADDRESS and by the screen id it opens"*) was the half nobody wrote. The
// control was released in the same commit as `P5.10`, pointing at
// `/reports/custom`, which is the catalogue it is standing on: from
// `/reports/custom` a press did nothing at all, and from `/reports` it
// switched sub-tab to an empty list. The Product Owner found it on deployed
// `v2.388.0`.
//
// ⚠ **THE RULE THIS BUYS: A HOLD-EXPIRY CASE IS AMENDED, NEVER DELETED.** The
// case knows which control it is about and the day the hold expires is the
// only day anybody is looking at it — so that is the moment to turn *this is
// not drawn* into *this is drawn AND it opens X*, in the same commit. A
// deleted case takes the control's name out of the suite with it, and a
// control nothing names is a control nobody can find again.
describe("`+ Build your own` — the hold expired, so the DESTINATION is the assertion", () => {
  /** The catalogue, plus somewhere for the button to go, at the REAL patterns.
   *
   *  ⚠ The target route exists so the router can actually perform the
   *  navigation. Its element is a marker rather than the real editor: this
   *  case is about WHERE the button goes, and the case below is about what
   *  `App.tsx` mounts there. Splitting them is what makes each one fail for
   *  one reason. */
  function openAt(entry: string) {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: Infinity } },
    });
    queryClient.setQueryData(queryKeys.me, USER);
    queryClient.setQueryData(queryKeys.myPermissions, PERMISSIONS);
    queryClient.setQueryData(
      queryKeys.shellDisplay,
      shellBootSeed({ timezone: "America/Chicago", date_format: "MM/DD/YYYY" }, {
        fy_label: "FY2026",
        period: 9,
        start: "2026-09-01",
        end: "2026-09-30",
        status: "open",
      }),
    );
    const router = createMemoryRouter(
      [
        { path: `/:tenant${REPORTS_ROUTE}`, element: <ReportLibraryPage client={server()} /> },
        {
          path: `/:tenant${REPORTS_ROUTE}/custom`,
          element: <ReportLibraryPage initialOrigin="custom" client={server()} />,
        },
        { path: `/:tenant${REPORT_BUILDER_NEW_ROUTE}`, element: <p>the builder</p> },
      ],
      { initialEntries: [entry] },
    );
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );
    return router;
  }

  it("is DRAWN on the catalogue — the half the deleted cases were right about", async () => {
    openAt(`/${TENANT}${REPORTS_ROUTE}`);
    await screen.findByText("AR Ageing");
    expect(
      screen.queryByRole("button", { name: /Build your own/i }),
      "`+ Build your own` is not on screen 1·1 at all — it was released in " +
        "`P5.10` and a control that vanishes is a different defect from a " +
        "control that goes nowhere.",
    ).not.toBeNull();
  });

  it("LANDS on the builder's own address, which is what nobody asserted", async () => {
    // ⚠ **THE ASSERTION `DEF-REP-7640` IS ABOUT.** It reads the address the
    // ROUTER moved to, against the constant `App.tsx` registers — never a
    // literal repeated here, which would compare a mistake with itself.
    const router = openAt(`/${TENANT}${REPORTS_ROUTE}`);
    await screen.findByText("AR Ageing");
    fireEvent.click(screen.getByRole("button", { name: /Build your own/i }));
    expect(
      router.state.location.pathname,
      "pressing `+ Build your own` did not open the builder. It went to " +
        `${router.state.location.pathname}, and /${TENANT}${REPORTS_ROUTE}/custom ` +
        "is the catalogue's own Custom sub-tab — the address this button " +
        "pointed at for a day while every check passed.",
    ).toBe(`/${TENANT}${REPORT_BUILDER_NEW_ROUTE}`);
  });

  it("LANDS there from /reports/custom too — where the old target was the page itself", async () => {
    // ⚠ **THE OTHER DIRECTION, AND IT IS THE WORSE SYMPTOM.** From the
    // catalogue the old target at least MOVED; from `/reports/custom` the
    // press was a complete no-op, which is what the Product Owner saw. A test
    // that only pressed from `/reports` would have gone green on half of it.
    const router = openAt(`/${TENANT}${REPORTS_ROUTE}/custom`);
    await screen.findByRole("button", { name: /Build your own/i });
    fireEvent.click(screen.getByRole("button", { name: /Build your own/i }));
    expect(
      router.state.location.pathname,
      "pressing `+ Build your own` on /reports/custom left the clerk exactly " +
        "where they were — the no-op the defect was reported as.",
    ).not.toBe(`/${TENANT}${REPORTS_ROUTE}/custom`);
    expect(router.state.location.pathname).toBe(`/${TENANT}${REPORT_BUILDER_NEW_ROUTE}`);
  });

  it("and the SCREEN at that address is the builder, by element and by id", () => {
    // ⚠ **BY ADDRESS *AND* BY SCREEN, BECAUSE EITHER ALONE PASSES ON THE BUG**
    // — `DEF-REP-6812` is the worked case from this very screen:
    // `/settings/audit-log` matched a route perfectly well and opened
    // Settings → Company. The case above reads the address the button built;
    // this one reads what `App.tsx` actually mounts there.
    const address = `/${TENANT}${REPORT_BUILDER_NEW_ROUTE}`;
    expect(
      elementAt(address),
      `${address} is answered by something other than the report builder.`,
    ).toBe(ReportEditorPage);
    expect(resolveScreen(address).a1, `${address} opens the wrong screen id`).toBe("S47");
  });

  it("opens it BLANK — the router passes the mode, the screen does not guess", () => {
    // p022 and the PO's own words, *"Opens the editor on a blank definition"*.
    // Without this prop the page resolves `useParams().reportKey`, finds
    // nothing, and waits for a report that is never coming — a permanent
    // skeleton, which is a live address behind a screen that cannot render.
    const matches = matchRoutes(APP_ROUTES, `/${TENANT}${REPORT_BUILDER_NEW_ROUTE}`) ?? [];
    const leaf = matches[matches.length - 1]?.route as
      | { element?: { props?: Record<string, unknown> } }
      | undefined;
    expect(leaf?.element?.props?.blank, "the builder route does not pass `blank`").toBe(true);
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: PO ruling 2026-09-26 "go as per phases - tasks" (12-governance/02-decision-log.md, 76be101a3) · 05-prototype/09 Reports Build Brief.pdf p19-p22 read as IMAGES per B14 rule 42 · AMENDED 2026-09-28 by lane REP-BUILD-YOUR-OWN for DEF-REP-7640 (PO ruling of that date: "Opens the editor on a blank definition, then Save as")
// screens: S44 · 2·2 (A1 S47)
// generated: 2026-09-26 by lane REP-P1
// gates: RED PROVED FIRST — each expiry case was run with `ReportsTabRoute` swapped for `ReportLibraryPage` at one address and failed naming the tab, which is the failure the day Phase 3 lands. [2026-09-28] The five `+ Build your own` cases were each run against the UNFIXED screen first: `LANDS on the builder's own address` failed with `expected '/brazosbend/reports/custom/new', received '/brazosbend/reports/custom'`, `LANDS there from /reports/custom too` failed on the no-op, `the SCREEN at that address` failed with no route matching at all, and `opens it BLANK` failed on an undefined prop. Quoted in the lane report.
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

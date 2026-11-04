/* ── Trace ──────────────────────────────────────────────
 * Story:   US-RBS-003 (EP-RBS-01) — CR-075 wave D task D2.
 * Screens: RBS-001 (the holds) · RBS-002 · RBS-007 · RBS-008 (the screens they
 *          wait on).
 * Rules:   CLAUDE.md hard-won law 2, MIRROR clause — *"when you write a hold,
 *          write the test that fires when the hold expires, in the same commit
 *          — assert the destination by ADDRESS and by the screen id it opens"*
 *          · hard-won law 7 (a check must be able to fail, and somebody must
 *          read it) · BR-SHL-025 (a control that cannot act is disabled WITH
 *          ITS REASON).
 * Defects: DEF-CWP-3925 (a live screen behind a dead control: the portal's
 *          front page had two working doors out of eight, every check green).
 * ─────────────────────────────────────────────────────── */

/**
 * **THE CLOCK ON `RBS-001`'s FOUR HELD CONTROLS — AND THE LATCH ON THE THREE
 * DOORS THAT ARE OPEN.**
 *
 * The Runbooks home draws three page-head actions, two empty-state buttons, one
 * row action and a **Stop** on the in-flight banner. Today:
 *
 *   **OPEN** — *Templates →* and *Browse templates →* onto `RBS-002`, and
 *              `👁 View` onto `RBS-006`.
 *   **HELD** — *History →* (`RBS-008`), *Work list →* (`RBS-007`),
 *              *Run "Can we bill?" ▶* and *Stop* (the acting half's write
 *              routes; every runbooks route today is a `GET`).
 *
 * Each of those is a rule with a CLOCK in it — true the day it is written and
 * false the morning the thing it waits on arrives. `DEF-CWP-3925` is what
 * happens when nobody winds it: five cards, the sign-in bar and three of four
 * nav words on the customer portal's front page were all still refusing over
 * screens that had shipped days earlier, with `tsc`, 42 portal test files, 391
 * cases and every gate green over it. Each wave had tested ITS OWN screen at
 * ITS OWN address, and the question *has the door started pointing at it*
 * belonged to nobody.
 *
 * ⚠ **THIS FILE HAS ALREADY DONE THAT JOB ONCE, WITHIN THE HOUR OF BEING
 * WRITTEN.** `RBS-002` landed in a sibling lane the same afternoon; on the
 * merge the SOURCE half went red — *"RBS-002 exists now, and RBS-001's
 * 'templates' is still a disabled button"* — and the two template doors were
 * opened in the commit that first met it. That is the whole point, and it is
 * why the assertions were turned around rather than deleted.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * TWO ASSERTIONS PER CONTROL, IN BOTH DIRECTIONS
 * ══════════════════════════════════════════════════════════════════════════
 * **For a HELD control:**
 *   1. **BY ADDRESS.** The REAL route table is asked what it renders at the
 *      address the button will point at, and the screen id must be absent.
 *   2. **BY SCREEN ID, IN THE SOURCE.** No file under `src/` declares
 *      `data-screen="RBS-008"` (or `-007`). This is the half law 7 says an
 *      address check cannot cover: it records a hold-expiry test that asserted
 *      a screen was REGISTERED at an address while the router mounted it
 *      somewhere else, with every check green over both. A sibling mounting the
 *      screen at an address this file did not predict still turns it red.
 *
 * **For an OPEN door, the mirror** — because a door that silently stops working
 * is just as invisible as a hold that outlives its screen, and a `<Link>` to
 * nowhere is a perfectly good string:
 *   1. some source file still declares the screen id;
 *   2. the address resolves to a route rather than to the catch-all;
 *   3. the `href` is built from the tenant, so nothing is `//host/…`.
 *
 * ⚠ **WHAT (2) CANNOT SEE, SAID RATHER THAN ASSUMED.** Every query is disabled
 * in this fixture and `TemplateLibraryPage` returns a loading skeleton while
 * its read is pending, so `RBS-002`'s own `data-screen` never reaches the
 * markup here. Asserting on it would be a check incapable of passing. (1) and
 * (2) together are the id half and the address half; neither alone is enough.
 *
 * ⚠ **AND THE HELD ADDRESS HALF IS NOT SIMPLY *"THE CATCH-ALL"*.** `App.tsx`
 * mounts `runbooks/:key` for `RBS-004`, and React Router matches
 * `/{tenant}/runbooks/runs` against it — so that address opens **the setup
 * screen for the runbook whose key is `runs`**, not the catch-all. That is
 * `integrations/subprocessors` exactly, which shipped and answered 405 under a
 * comment asserting the collision away, and it is why *History →* is HELD
 * rather than linked: a live one today would open a broken `RBS-004`.
 *
 * ══════════════════════════════════════════════════════════════════════════
 * PROVED RED FIRST, IN THE HARNESS THAT RUNS IT (law 7, both halves)
 * ══════════════════════════════════════════════════════════════════════════
 * Run through `./node_modules/.bin/vitest` — the runner CI uses, never `npx`.
 * Every assertion here has been watched to fail:
 *
 *   · the HELD **source** half — a temporary `data-screen="RBS-002"` planted in
 *     `RunbookSetup.tsx` turned it red naming *Templates →*;
 *   · the HELD **address** half — a temporary `runbooks/templates` route in
 *     `App.tsx` turned it red;
 *   · the **write-route** half — see its own note below: it fired on the WRONG
 *     event first (wave E's `POST /runbooks` and `PUT /runbooks/{key}`, neither
 *     of which starts or stops a run) and then on a comment, and both faults
 *     were found by running it rather than by reading it;
 *   · the OPEN halves — proved by the real event: they were RED before the
 *     Templates door was opened, because `RBS-002` was not yet declared and
 *     `/runbooks/templates` still fell to `runbooks/:key`.
  */
import { renderToStaticMarkup } from "react-dom/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { matchRoutes, MemoryRouter, useRoutes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { FIRST_RUN_PATH } from "./RunbooksHome";
import { HEAD_DESTINATIONS, HELD_DESTINATIONS, OPEN_DESTINATIONS } from "./runbooksHomeModel";

// ⚠ NODE'S OWN MODULES, REACHED THE WAY `routeBLedger.test.ts` NEXT DOOR DOES.
// `import fs from "node:fs"` type-checks against `@types/node`, which this app's
// tsconfig does not include — its `lib` is `ES2022 · DOM · DOM.Iterable` — so
// `tsc --noEmit` answers TS2307 while **vitest stays green over it**, because
// vitest transpiles and does not type-check. That is `DEF-RBS-4256`, filed by
// this module's own wave A lane against itself.
const nodeFs = (await import(/* @vite-ignore */ ["node", "fs"].join(":"))) as {
  readFileSync(p: string, enc: string): string;
  readdirSync(p: string, o: { withFileTypes: true }): { name: string; isDirectory(): boolean }[];
  existsSync(p: string): boolean;
};
const nodePath = (await import(/* @vite-ignore */ ["node", "path"].join(":"))) as {
  join(...p: string[]): string;
  dirname(p: string): string;
  resolve(...p: string[]): string;
};
const nodeUrl = (await import(/* @vite-ignore */ ["node", "url"].join(":"))) as {
  fileURLToPath(url: URL | string): string;
};

const HERE = nodePath.dirname(nodeUrl.fileURLToPath(import.meta.url));
const SRC = nodePath.resolve(HERE, "..", "..", "..");
const REPO = nodePath.resolve(SRC, "..", "..");
const RUNBOOKS_API = nodePath.join(REPO, "06-backend", "apps", "runbooks", "api.py");

const TENANT = "brazosbend";


/** Every `.ts`/`.tsx` under `src/`, tests excluded — a test may NAME a screen
 *  id (this file does) and only a real screen DECLARES one. */
function sourceFiles(dir: string, out: string[] = []): string[] {
  for (const entry of nodeFs.readdirSync(dir, { withFileTypes: true })) {
    const full = nodePath.join(dir, entry.name);
    if (entry.isDirectory()) {
      sourceFiles(full, out);
    } else if (/\.tsx?$/.test(entry.name) && !/\.test\./.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

const SOURCES = sourceFiles(SRC);

/**
 * A file's CODE, with its comments removed.
 *
 * ⚠ **THIS EXISTS BECAUSE THE CHECK BELOW PASSED ON ITS OWN DOCSTRING.** The
 * first draft searched the raw file text for `data-screen="RBS-002"`, and
 * `runbooksHomeModel.ts` NAMES that string in a comment explaining why the
 * Templates door was opened. So "some source file declares RBS-002" was true of
 * a sentence about RBS-002, and the assertion stayed green through a red proof
 * that deliberately deleted the screen. Law 7's *looking at the wrong thing*,
 * found by doing what law 7 says: watching it fail.
 *
 * The same fault bit the write-route check two cases down, on the same day, for
 * the same reason. Two occurrences, one cause: **a guard that reads prose as
 * code.**
 */
function codeOf(file: string): string {
  return nodeFs
    .readFileSync(file, "utf8")
    .replace(/\/\*[\s\S]*?\*\//g, " ")
    .replace(/(^|[^:])\/\/[^\n]*/g, "$1 ");
}

const DANA: SessionUser = {
  id: "u1",
  full_name: "Dana Whitfield",
  email: "dana@brazosbend.example",
  phone: null,
  role: "system_admin",
  role_name: "System Admin",
  must_change_password: false,
};

const ADMIN_PERMISSIONS: MyPermissions = {
  role: "system_admin",
  role_name: "System Admin",
  permissions: [{ code: "reports", label: "reports", access: "Full" as const }],
};

const REGIONAL = { timezone: "America/Chicago", date_format: "MM/DD/YYYY" };

function RoutedApp() {
  return useRoutes(APP_ROUTES);
}

/** The REAL route table at a REAL tenant address — never a bare MemoryRouter,
 *  which gives `useParams()` undefined and builds `//host/…` (DEF-CWP-3925). */
function renderAt(relativePath: string): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, enabled: false } },
  });
  queryClient.setQueryData(queryKeys.me, DANA);
  queryClient.setQueryData(queryKeys.myPermissions, ADMIN_PERMISSIONS);
  queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(REGIONAL));
  queryClient.setQueryData(queryKeys.regionalSettings, REGIONAL);
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TENANT}${relativePath}`]}>
          <RoutedApp />
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function release(labelHint: string, screen: string): string {
  return (
    `${screen} exists now, and RBS-001's "${labelHint}" is still a disabled button. Release it ` +
    `in the SAME COMMIT: give the entry in HELD_DESTINATIONS (features/runbooks/home/` +
    `runbooksHomeModel.ts) a live address and turn this assertion around. A hold nobody ` +
    `releases is DEF-CWP-3925 — eight doors shut over live screens, every check green.`
  );
}

describe("RBS-001's page-head doors — the clock on each one", () => {
  it("the screen draws all three, each in the tier its destination has earned", () => {
    // The assertion that proves the assertions. Without it, a screen that
    // stopped drawing the buttons would leave every case in this file green
    // over holds that no longer exist — the empty-loop shape law 7 names.
    const markup = renderAt("/runbooks");
    for (const held of HELD_DESTINATIONS) {
      expect(markup, `RBS-001 no longer draws the held ${held.id} button`).toContain(
        `data-held="${held.id}"`,
      );
    }
    for (const open of OPEN_DESTINATIONS) {
      expect(markup, `RBS-001 no longer draws the live ${open.id} link`).toContain(
        `data-open="${open.id}"`,
      );
    }
    expect(HEAD_DESTINATIONS).toHaveLength(3);
    expect(
      new Set(HEAD_DESTINATIONS.map((d) => d.id)).size,
      "a head action is in BOTH lists — it would draw twice, once live and once dead",
    ).toBe(3);
  });

  it.each(HELD_DESTINATIONS.map((held) => [held.id, held.screen, held.path] as const))(
    "BY SCREEN ID — %s: no source file declares %s yet",
    (id, screen) => {
      const declaring = SOURCES.filter((file) =>
        codeOf(file).includes(`data-screen="${screen}"`),
      ).map((file) => file.slice(SRC.length + 1));
      expect(declaring, release(id, screen)).toEqual([]);
    },
  );

  it.each(HELD_DESTINATIONS.map((held) => [held.id, held.screen, held.path] as const))(
    "BY ADDRESS — %s: %s does not render at %s",
    (id, screen, path) => {
      // ⚠ The expected answer here is NOT the catch-all for `history`:
      // `runbooks/:key` matches `runbooks/runs`, so that address opens
      // RBS-004's setup screen today. The assertion is therefore about the
      // SCREEN ID rather than about the catch-all marker — the only form that
      // stays true whichever way the router resolves it.
      expect(renderAt(path), release(id, screen)).not.toContain(`data-screen="${screen}"`);
    },
  );

  // ══════════════════════════════════════════════════════════════════════════
  // AND THE OTHER DIRECTION — A DOOR THAT WAS OPENED MUST STAY OPEN
  // ══════════════════════════════════════════════════════════════════════════
  // `DEF-CWP-3925` is a hold that outlived its screen. The mirror is a door
  // that silently stops working — a route renamed, a screen moved — and it is
  // just as invisible, because a `<Link>` to nowhere is a perfectly good
  // string. So every RELEASED destination is asserted the same two ways the
  // held ones are, in reverse.
  it.each(OPEN_DESTINATIONS.map((open) => [open.id, open.screen, open.path] as const))(
    "STAYS OPEN — %s: some source file still declares %s",
    (id, screen) => {
      const declaring = SOURCES.filter((file) =>
        codeOf(file).includes(`data-screen="${screen}"`),
      );
      expect(
        declaring.length,
        `RBS-001's "${id}" is a live link and NO file under src/ declares ${screen} any more. ` +
          `The screen was deleted or renamed and the door now opens onto nothing — which reads ` +
          `as a perfectly good string to every other check we own.`,
      ).toBeGreaterThan(0);
    },
  );

  it.each(OPEN_DESTINATIONS.map((open) => [open.id, open.screen, open.path] as const))(
    "STAYS OPEN — %s: the route table matches %s with its OWN pattern",
    (id, _screen, path) => {
      // ⚠ **WHAT THIS CAN AND CANNOT SEE, SAID RATHER THAN ASSUMED (law 7's
      // *reporting zero over a scope it silently excludes*).** Every query is
      // disabled in this fixture and `TemplateLibraryPage` returns a loading
      // skeleton while its read is pending, so the screen's own `data-screen`
      // never reaches the markup here; asserting on it would be a check
      // incapable of passing. The case above proves the screen still exists.
      // This one proves the ADDRESS reaches it.
      //
      // ⚠ **AND IT ASKS THE ROUTER FOR THE MATCHED PATTERN RATHER THAN LOOKING
      // FOR THE CATCH-ALL, BECAUSE THE CATCH-ALL FORM CANNOT FAIL HERE.** Delete
      // the `runbooks/templates` route and this address does NOT fall through:
      // `runbooks/:key` catches it and renders `RBS-004`'s setup screen for the
      // runbook whose key is `templates`. So "it is not the catch-all" stays
      // true over a completely broken door. That draft was written, proved by
      // deleting the route, and stayed green — law 7's *structurally incapable
      // of failing*, caught by doing the red proof rather than by reasoning.
      const matched = matchRoutes(APP_ROUTES, `/${TENANT}${path}`) ?? [];
      const leaf = matched[matched.length - 1]?.route?.path ?? "";
      expect(
        leaf,
        `RBS-001's "${id}" link points at ${path} and the router matches it with ` +
          `"${leaf}" instead of a route of its own. Either the destination's route was ` +
          `removed — in which case runbooks/:key silently swallows the address — or it moved.`,
      ).toBe(path.replace(/^\//, ""));
    },
  );

  it("STAYS OPEN — the live link is built from the tenant, so nothing is //host/…", () => {
    // DEF-CWP-3925's fixture bug, asserted rather than assumed: an address
    // built without the tenant comes out protocol-relative and points at
    // another host, which `toContain` cannot tell from a working link.
    const markup = renderAt("/runbooks");
    for (const open of OPEN_DESTINATIONS) {
      expect(markup).toContain(`href="/${TENANT}${open.path}"`);
      expect(markup, `${open.id} built a protocol-relative address`).not.toContain(
        `href="/${open.path}"`,
      );
    }
  });
});

describe("RBS-001's two write-route holds — Run “Can we bill?” (RELEASED) and Stop (held)", () => {
  // ⚠ **THIS CHECK WAS `verbs === ["GET"]` FOR ONE HOUR AND THAT WAS TOO
  // COARSE.** Wave E landed `POST /runbooks`, `POST /runbooks/{key}/clone` and
  // `PUT /runbooks/{key}` — real write routes, none of which starts or stops a
  // RUN, and none of which releases either of these two buttons. A guard that
  // fires on the wrong event is a guard that gets muted, so it names the two
  // ADDRESSES its holds actually wait on instead of asking about verbs.
  const STARTS_A_RUN = 'runbooks/<str:key>/runs"';
  const STOPS_A_RUN = "/stop";

  it("apps/runbooks/api.py still mounts no route that STARTS or STOPS a run", () => {
    expect(
      nodeFs.existsSync(RUNBOOKS_API),
      "apps/runbooks/api.py has moved. This check reads it as the expiry condition for two " +
        "holds on RBS-001; re-point it rather than deleting it.",
    ).toBe(true);
    const source = nodeFs.readFileSync(RUNBOOKS_API, "utf8");
    // ⚠ **THE ASSIGNMENT, NOT THE FIRST MENTION OF THE WORD.** Slicing from
    // `indexOf("urlpatterns")` starts inside the module docstring, which names
    // the wave-L routes it does NOT have — *"`…/approve`, `…/stop`,
    // `…/decide`"* — so this check fired on prose the first time it ran. A
    // guard that reads a comment as code is law 7's *looking at the wrong
    // thing*, and it found itself.
    const at = source.search(/^urlpatterns = \[/m);
    expect(at, "no `urlpatterns = [` found — has the file's shape changed?").toBeGreaterThan(-1);
    const patterns = source.slice(at);
    // ⚠ **THE START HALF EXPIRED AND IS TURNED AROUND, NOT DELETED (2026-10-13,
    // `DEF-WRK-10120`).** `runbooks/<str:key>/runs` landed in `54583c831`
    // (CR-173-BRC10, 2026-10-07 — found with `git log -S`), this assertion
    // went red exactly as written, and it stayed red for six days because
    // nobody read it (law 7's *proved red, then never read*). The button is
    // released in the same commit as this turn: it now asserts the route
    // EXISTS, and the case below asserts where the released button goes.
    expect(
      patterns.includes(STARTS_A_RUN),
      "The route that starts a run is gone from apps/runbooks/api.py, and RBS-001's " +
        '"Run “Can we bill?” ▶" is a LIVE link onto the Check wizard that would now start ' +
        "nothing. Hold it again in the same commit (DEF-CWP-3925's mirror, run backwards).",
    ).toBe(true);
    expect(
      patterns.includes(STOPS_A_RUN),
      'A route that stops a run exists. Release RBS-001\'s "Stop" on the in-flight banner in ' +
        'the SAME COMMIT — RBS-001.3\'s own note is *"Stop is always reachable … a running ' +
        'batch a clerk cannot halt is the thing that makes people afraid of automation"*.',
    ).toBe(false);
  });

  it("the released Run “Can we bill?” ▶ points at the Check wizard, BY ADDRESS and BY ROUTE", () => {
    // Law 2's mirror, the OPEN half: a `<Link>` to nowhere is a perfectly good
    // string, so the address is asked of the REAL route table — which must
    // match it with the wizard's own pattern, never `runbooks/:key`'s.
    //
    // ⚠ **WHAT THIS CANNOT SEE, SAID RATHER THAN ASSUMED.** Every query is
    // disabled in `renderAt`, so the home draws its loading skeleton and the
    // empty state carrying the button never reaches this markup. That the
    // button CARRIES `FIRST_RUN_PATH` is asserted where the empty state is
    // seeded — `RunbooksHome.dom.test.tsx`, *"opens the Check wizard by
    // address"*. This case proves the address reaches the wizard.
    const matched = matchRoutes(APP_ROUTES, `/${TENANT}${FIRST_RUN_PATH}`) ?? [];
    expect(matched[matched.length - 1]?.route?.path).toBe("runbooks/:key/run");
    // …and some source file still declares the screen that address opens.
    expect(
      SOURCES.some((file) => codeOf(file).includes('data-screen="RBS-005"')),
      "no file under src/ declares RBS-005 any more — the wizard the button opens is gone",
    ).toBe(true);
  });
});

/* ── Lifecycle ─────────────────────────────────────────────
 * packet: US-RBS-003 (CR-075 wave D task D2) + CLAUDE.md hard-won law 2 mirror clause
 * generated: 2026-09-06 by the CR-075 wave D task D2 build lane
 * checklist: A✔ B✔ C✔ D=n/a(no API call — this measures routing and source) E✔ F✔ G✔ H=n/a
 * gates: ./node_modules/.bin/vitest run src/features/runbooks/home/homeHoldExpiry.test.tsx — each of the three halves proved RED first (see this file's header)
 * exceptions: G103 does not cover these holds — it reads only portal/ files and CWP screen ids. It covers 36 portal holds and 0 staff-app holds; this file is the staff app's cover for RBS-001's six.
 * status: VERIFIED-UNRATIFIED
 * ────────────────────────────────────────────────────────── */

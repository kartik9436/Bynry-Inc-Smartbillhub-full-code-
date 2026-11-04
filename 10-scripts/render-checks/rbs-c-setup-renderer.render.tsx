/**
 * Renders `RBS-004`'s SEVEN TABS to a static HTML fragment, so
 * `rbs-c-setup-renderer.mjs` can open them in a REAL browser with the REAL
 * built stylesheet and measure what a person would see.
 *
 * ⚠ THE SCREEN IS IMPORTED, NOT RE-TYPED, AND SO IS ITS FIXTURE.
 * `column-chooser-geometry.mjs` next door copies its markup hunk-for-hunk from
 * `DataTable.tsx` and says in its own comment that a copy which drifts measures
 * nothing. `cr075-c-runbook-kit.render.tsx` — this file's shape — records the
 * same. So `RunbookSetup` and `COLLECTIONS_LADDER` come from the product: if
 * either changes, this measures the change.
 *
 * ⚠ EACH TAB IS ITS OWN ROUTER AT ITS OWN REAL ADDRESS. The screen reads its
 * active tab from `useLocation().hash`, so seven hashes means seven mounts —
 * and each is mounted under the REAL path pattern `/:tenant/runbooks/:key`,
 * never bare. `DEF-CWP-3925`: a component mounted with no `/:tenant/…` route
 * gets `undefined` from `useParams()` and builds every address against another
 * host, which reads as a perfectly good string to `toContain`. A fixture that
 * cannot tell a working link from a broken one is how that defect hid.
 *
 * RUN (from 07-frontend, which owns the alias and the deps):
 *   npx vite-node ../10-scripts/render-checks/rbs-c-setup-renderer.render.tsx -- /tmp/rbs004.html
 */
import { writeFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
// ⚠ `MemoryRouter`, NOT `StaticRouter`. Under vite-node `react-router-dom` and
// `react-router-dom/server` resolve to two module instances, so the server
// router's context is invisible to the `Link`s inside it and every render dies
// on `Cannot destructure property 'basename' of null`. One module, one context.
// (`cr075-c-runbook-kit.render.tsx` records the same, from the same bite.)
import { MemoryRouter, Route, Routes } from "react-router-dom";

import "../../07-frontend/src/i18n";

import {
  RunbookSetup,
  RUNBOOK_SETUP_TABS,
} from "../../07-frontend/src/features/runbooks/RunbookSetup";
import {
  COLLECTIONS_LADDER,
  CONFIGURATION_CHECK,
} from "../../07-frontend/src/features/runbooks/setupFixture";
import type { RunbookSetupView } from "../../07-frontend/src/features/runbooks/setupTypes";

const TENANT = "silvercreek";
const noop = () => undefined;

function screenAt(view: RunbookSetupView, tab: string) {
  return (
    <MemoryRouter initialEntries={[`/${TENANT}/runbooks/${view.key}#${tab}`]}>
      <Routes>
        <Route
          path="/:tenant/runbooks/:key"
          element={
            <RunbookSetup
              view={view}
              onRun={noop}
              onPauseToggle={noop}
              onChangeScope={noop}
              onChangeLimits={noop}
              onRunsPage={noop}
              onRunsPer={noop}
            />
          }
        />
      </Routes>
    </MemoryRouter>
  );
}

/** One labelled slab per tab, so a screenshot and a measurement name the same
 *  region the build sheet does. */
function slab(id: string, caption: string, body: React.ReactNode) {
  return (
    <section key={id} data-shot={id} style={{ marginBottom: "32px" }}>
      <h2
        style={{
          font: "700 12px/1.4 system-ui",
          letterSpacing: ".08em",
          textTransform: "uppercase",
          color: "#7d7979",
          margin: "0 0 8px",
        }}
      >
        {caption}
      </h2>
      <div style={{ background: "#fff", padding: "16px" }}>{body}</div>
    </section>
  );
}

const SHEET: Record<string, string> = {
  overview: "RBS-004.1 · Overview · figure 9",
  steps: "RBS-004.2 · Steps · figure 10",
  scope: "RBS-004.3 · Scope · figure 11",
  guards: "RBS-004.4 · Guards · figure 12",
  limits: "RBS-004.5 · Limits · figure 13",
  runs: "RBS-004.6 · Runs · figure 14",
  activity: "RBS-004.7 · Activity · figure 15",
};

const body = renderToStaticMarkup(
  <div style={{ padding: "24px", maxWidth: "1180px" }}>
    {RUNBOOK_SETUP_TABS.map((tab) =>
      slab(tab, SHEET[tab], screenAt(COLLECTIONS_LADDER, tab)),
    )}
    {/* The Check — `BR-RBS-002` on screen. A runbook that holds no ports says
        so in a sentence rather than drawing an empty block, and an absent
        why-line draws nothing at all (`DEF-RBS-4285`). Both are measured. */}
    {slab(
      "check-overview",
      "A CHECK · BR-RBS-002 · nothing is written",
      screenAt(CONFIGURATION_CHECK, "overview"),
    )}
    {slab(
      "check-steps",
      "A CHECK · a step whose why-line the contract cannot carry",
      screenAt(CONFIGURATION_CHECK, "steps"),
    )}
  </div>,
);

const out = process.argv[2];
if (out === undefined) throw new Error("usage: rbs-c-setup-renderer.render.tsx <out.html>");
writeFileSync(out, body);
console.log(`wrote ${body.length} bytes of markup to ${out}`);

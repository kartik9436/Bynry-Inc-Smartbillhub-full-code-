/**
 * Renders RBS-005's four Check-path states to a static HTML fragment, so
 * `rbs-c-run-wizard.mjs` can open them in a REAL browser with the REAL built
 * stylesheet and measure what a clerk would see.
 *
 * ⚠ THE COMPONENT IS IMPORTED, NOT RE-TYPED. `column-chooser-geometry.mjs` next
 * door copies its markup hunk-for-hunk from `DataTable.tsx` and says in its own
 * comment that a copy which drifts measures nothing. Importing removes that
 * failure mode: if the screen changes, this measures the change.
 *
 * ⚠ **MOUNTED UNDER THE REAL PATH PATTERN.** `DEF-CWP-3925`: a component
 * rendered inside a bare `MemoryRouter` with no `/:tenant/…` route builds every
 * address as `//…` — a protocol-relative URL to another host that reads as a
 * perfectly good string. So the harness uses `<Routes><Route path="/:tenant/
 * runbooks/:key/run">` and the measurement script asserts every href starts
 * `/silvercreek/`.
 *
 * ⚠ `MemoryRouter`, NOT `StaticRouter`. Under vite-node, `react-router-dom` and
 * `react-router-dom/server` resolve to two module instances, so the server
 * router's context is invisible to the `Link`s inside it and every render dies
 * on `Cannot destructure property 'basename' of null`. One module, one context.
 *
 * RUN (from 07-frontend, which owns the alias and the deps):
 *   npx vite-node ../10-scripts/render-checks/rbs-c-run-wizard.render.tsx -- /tmp/body.html
 */
import { writeFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import "../../07-frontend/src/i18n";
import { RunWizard } from "../../07-frontend/src/features/runbooks/run/RunWizard";
import type { RunWizardProps } from "../../07-frontend/src/features/runbooks/run/RunWizard";
import type { RunPhase, StepCatalogueEntry } from "../../07-frontend/src/features/runbooks/run/runWizardModel";

const TENANT = "silvercreek";
const HERE = `/${TENANT}/runbooks/configuration-check/run`;

/** Runbook 1's ten, from `configuration_check.py`'s own `STEP_LABELS`. */
const TEN: StepCatalogueEntry[] = [
  { key: "services_and_units", label: "Services and units" },
  { key: "reference_data", label: "Reference data" },
  { key: "tax", label: "Tax" },
  { key: "plans_in_force", label: "Plans in force" },
  { key: "rate_coverage", label: "Rate coverage" },
  { key: "account_chain", label: "Account chain" },
  { key: "meters", label: "Meters" },
  { key: "reads_and_windows", label: "Reads and windows" },
  { key: "documents", label: "Documents" },
  { key: "books", label: "Books" },
];

const BASE: RunWizardProps = {
  runbookName: "Can we bill?",
  runbookTo: `/${TENANT}/runbooks/configuration-check`,
  phase: "scoping",
  // `BR-RBS-042` — runbook 1's four DECLARED INPUTS, in the definition's order.
  inputs: [
    { id: "report", label: "Report", value: "Blockers and warnings" },
    { id: "usage_to_cover", label: "Usage to cover", value: "Ladder is unbounded" },
    { id: "include_held_accounts", label: "Include held accounts", value: "No" },
    { id: "raise_work_items", label: "Raise work items", value: "Yes" },
  ],
  matches: 1,
  matchesValue: "This utility",
  steps: TEN,
  outcomes: {},
  doneTiles: [
    { id: "blockers", label: "Blockers", value: <span className="text-danger-700">3</span> },
    { id: "warnings", label: "Warnings", value: <span className="text-warning-700">6</span> },
    { id: "clear", label: "Steps clear", value: <span className="text-success-700">7 of 10</span> },
  ],
  doneHeadline: "3 things stop billing",
  needsYou: [],
  // The ENGINE's own word for this column — configuration_check.py's records
  // block declares "Affects" — rather than the ladder sheet's "Account", which
  // would be false over a finding about a tax region.
  needsYouSubjectLabel: "Affects",
  downloads: [
    { id: "findings", label: "Findings", href: `/api/${TENANT}/runbooks/runs/r1/results/done.csv` },
  ],
  workListTo: `/${TENANT}/runbooks/work-list`,
  review: <div data-probe="review-slot">RBS-006 draws the frozen report here (task C2)</div>,
  onStart: () => undefined,
  onSaveDraft: () => undefined,
  onCancel: () => undefined,
  onStop: () => undefined,
  onRetry: () => undefined,
  onTellSupport: () => undefined,
  onStepSelect: () => undefined,
};

/** Two steps in, eight to go — `RBS-005.2`'s own shape at a Check's numbers. */
const RUNNING: Partial<RunWizardProps> = {
  outcomes: {
    services_and_units: { state: "done", detail: "11 services · 2s" },
    reference_data: { state: "done", detail: "2 series · 1s" },
  },
};

/** `RBS-005.8` — a check itself failed, and the rest read *Never reached*. */
const FAILED: Partial<RunWizardProps> = {
  outcomes: {
    services_and_units: { state: "done", detail: "11 services · 2s" },
    reference_data: {
      state: "failed",
      reason: "Could not read the number series. Nothing was changed.",
      detail: "stopped",
    },
  },
};

/** `RBS-005.6` — the blockers fixture's own three findings, each with a fix. */
const DONE: Partial<RunWizardProps> = {
  needsYou: [
    {
      id: "tax",
      subject: "Every account",
      outcome: { label: "Blocker", tone: "danger" },
      detail: "No tax region set",
      fix: { label: "Set a tax region", to: `/${TENANT}/settings/taxes` },
    },
    {
      id: "rates",
      subject: "Residential water",
      outcome: { label: "Blocker", tone: "danger" },
      detail: "No rate above 20,000 gallons",
      fix: { label: "Add a block", to: `/${TENANT}/rating/plans` },
    },
    {
      id: "chain",
      subject: "Nunes, R.",
      outcome: { label: "Blocker", tone: "danger" },
      detail: "4 accounts have no unit",
      fix: { label: "Set a unit", to: `/${TENANT}/premises/units` },
    },
  ],
};

function panel(id: string, title: string, phase: RunPhase, extra: Partial<RunWizardProps>) {
  return (
    <section data-probe={id} style={{ marginBottom: "36px" }}>
      <h2
        style={{
          font: "700 12px/1.4 system-ui",
          letterSpacing: ".08em",
          textTransform: "uppercase",
          color: "#7d7979",
          margin: "0 0 8px",
        }}
      >
        {title}
      </h2>
      <MemoryRouter initialEntries={[HERE]}>
        <Routes>
          <Route
            path="/:tenant/runbooks/:key/run"
            element={<RunWizard {...BASE} {...extra} phase={phase} />}
          />
        </Routes>
      </MemoryRouter>
    </section>
  );
}

const body = renderToStaticMarkup(
  <div style={{ padding: "24px", maxWidth: "1180px" }}>
    {panel("scope", "RBS-005.1 · 1 Scope", "scoping", {})}
    {panel("checking", "RBS-005.2 · 2 Checking", "checking", RUNNING)}
    {panel("failed", "RBS-005.8 · a check itself failed", "checkFailed", FAILED)}
    {panel("done", "RBS-005.6 · 6 Done", "done", DONE)}
  </div>,
);

const out = process.argv[2] ?? "/tmp/rbs-c-run-wizard.html";
writeFileSync(out, body);
console.log(`wrote ${body.length} bytes to ${out}`);

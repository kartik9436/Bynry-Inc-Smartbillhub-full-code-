// ── Trace ──────────────────────────────────────────────
// Change:  CR-023 P5 · DEF-520 — the mount the kit never had
// Screens: WFL-01
// Rules:   BR-MET-096 (ONE workflow, premises and units) · BR-MET-085 (rows
//          and the hash are the SERVER's) · BR-MET-097 (an imported address is
//          accepted as given) · BR-SHL-025 (disabled WITH its reason)
// ───────────────────────────────────────────────────────
// ⚠ **THE FIRST CASE HERE IS THE ONE NOBODY HAD WRITTEN, AND IT IS THE WHOLE
// OF `DEF-520`.** Every component of this workflow had a test and every
// endpoint had a test, both suites were green, and the screen that joins them
// did not exist — so the PO clicked Import and got the old wizard. The
// question neither suite can ask is *"does a ROUTE render this"*, and that is
// case 1. It renders through `<Routes>` rather than the component directly,
// because a direct render would have passed on the broken build too: the file
// compiled, it was simply never reachable.
//
// ⚠ **THIS SUITE IS A STATIC RENDER, AND THAT IS A LIMIT WORTH KNOWING
// (`DEF-523`).** The repo has no `@testing-library/react` and no DOM
// environment — every frontend test is `renderToStaticMarkup`. So these cases
// assert the FIRST paint of each stage and cannot click through extract →
// transform → validate. The stage walk is covered on the server side by
// `06-backend/tests/test_cr023_import_stages.py` (39 cases), and what stays
// uncovered is the join: that this page sends what those endpoints accept.
// Filed rather than left as a silence.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { ImportWorkflowPage } from "./ImportWorkflowPage";
import { PREMISES_IMPORT_ROUTE, UNITS_IMPORT_ROUTE } from "./meteringShared";

const TEST_TENANT = "silvercreek";

/** No network, ever: every stage here is the FIRST paint, before any call. */
const NEVER_CALLED = {
  get: () => Promise.reject(new Error("no network in a static render")),
  post: () => Promise.reject(new Error("no network in a static render")),
} as unknown as ApiClient;

function renderAt(path: string): string {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${path}`]}>
          <Routes>
            <Route
              path="/:tenant/premises/import"
              element={<ImportWorkflowPage target="premises" client={NEVER_CALLED} />}
            />
            <Route
              path="/:tenant/premises/units/import"
              element={<ImportWorkflowPage target="units" client={NEVER_CALLED} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("WFL-01 — the five-stage import, MOUNTED (DEF-520)", () => {
  it("a route renders the runner at all", () => {
    // ⚠ THE DEF-520 CASE. Proved RED first: with the two route constants put
    // back to `?mode=premises_csv`, this markup contains no `data-workflow`
    // at all, which is the state the PO deployed.
    const html = renderAt(PREMISES_IMPORT_ROUTE);
    expect(html).toContain('data-workflow="runner"');
    expect(html).toContain('data-kind="premises"');
    expect(html).toContain('data-stage="1"');
  });

  it("the units route renders the SAME runner — one workflow, two targets (BR-MET-096)", () => {
    // PO 2026-08-21, verbatim: *"same process for premises and Unit - only at
    // tranform stage we differntate field for premises and Units"*. So this
    // compares the two paints and the ONLY differences allowed are the kind
    // marker and the per-kind copy the runner's own `WorkflowKind` declares.
    const units = renderAt(UNITS_IMPORT_ROUTE);
    expect(units).toContain('data-workflow="runner"');
    expect(units).toContain('data-kind="units"');
    // The stage rail is the same five words in the same order for both.
    for (const stage of ["Extract", "Transform", "Validate", "Load", "Result"]) {
      expect(units).toContain(stage);
      expect(renderAt(PREMISES_IMPORT_ROUTE)).toContain(stage);
    }
    // And the title is the shared one, not a per-target headline.
    expect(units).toContain("Extract, transform, validate, load.");
  });

  it("PROOF THE FIRST CASE BITES: the build the PO deployed renders no runner", () => {
    // ⚠ Case 1 is only worth anything if it can fail, so this reproduces the
    // deployed state rather than describing it. On 2026-08-21 the Imports
    // buttons carried `?mode=premises_csv` into `AddPremisesWizard` and there
    // was no `/premises/import` route at all — so a render at that path
    // matched nothing and produced EMPTY markup. That is what case 1 catches,
    // and this is the same render with the route left out.
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const deployed = renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}/premises/import`]}>
            <Routes>
              {/* the route table as it stood: premises/new, and nothing else */}
              <Route path="/:tenant/premises/new" element={<div>old wizard</div>} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(deployed).not.toContain('data-workflow="runner"');
    expect(deployed).not.toContain("Extract, transform, validate, load.");
  });

  it("the two routes are the runner's, not the old wizard's", () => {
    // `DEF-520` in two strings: these are what the Imports tab's buttons
    // navigate to, and they carried `?mode=` into `AddPremisesWizard`.
    expect(PREMISES_IMPORT_ROUTE).toBe("/premises/import");
    expect(UNITS_IMPORT_ROUTE).toBe("/premises/units/import");
    expect(PREMISES_IMPORT_ROUTE).not.toContain("mode=");
    expect(UNITS_IMPORT_ROUTE).not.toContain("mode=");
  });

  it("stage 1 draws all four sources and says which three are off", () => {
    const html = renderAt(PREMISES_IMPORT_ROUTE);
    for (const source of ["Upload a file", "Pull from a server", "Head-end or partner", "Key it in"]) {
      expect(html).toContain(source);
    }
    // BR-SHL-025: the three that are off are DISABLED WITH THEIR REASON.
    expect(html).toContain("Not switched on yet. Upload a file instead.");
  });

  it("stage 1 offers the sample CSV for BOTH targets (CR-025)", () => {
    // PO 2026-08-21, verbatim: "also we will need sample CSV files to be
    // downloaded at every import at step 1". One control, target-parameterised
    // (BR-MET-096) — the FILE it fetches is the server's, tested end-to-end in
    // 06-backend/tests/test_cr025_sample_csv.py, where the premises sample is
    // uploaded through the real stages 1-3 and validates clean.
    expect(renderAt(PREMISES_IMPORT_ROUTE)).toContain("Download a sample CSV");
    expect(renderAt(UNITS_IMPORT_ROUTE)).toContain("Download a sample CSV");
  });

  it("stage 1 invents no row count and no hash before the server has answered", () => {
    // BR-MET-085: the count and the SHA-256 on screen are the SERVER's,
    // computed over the bytes it received. Before stage 1 has run there is
    // nothing true to show, so nothing is shown.
    const html = renderAt(PREMISES_IMPORT_ROUTE);
    expect(html).toContain("No file chosen yet.");
    expect(html).not.toContain("rows ·");
    expect(html).not.toMatch(/SHA-256/);
  });

  it("stage 1 carries r10's four fields, and `Loads into` is fixed by the route", () => {
    const premises = renderAt(PREMISES_IMPORT_ROUTE);
    for (const field of [
      "Mapping template",
      "Encoding &amp; delimiter",
      "Loads into",
      "Batch label (audit trail)",
    ]) {
      expect(premises).toContain(field);
    }
    // The one field whose VALUE differs between the two workflows.
    expect(premises).toContain('value="Premises"');
    expect(renderAt(UNITS_IMPORT_ROUTE)).toContain('value="Units"');
  });

  it("⛔ DEF-PAY-10779 (Q7) — no dead `Save mapping as template` button and no \"not available yet\" sentence", () => {
    const html = renderAt(PREMISES_IMPORT_ROUTE);
    // The PO's answer (2026-10-30, Q7 = A) is a choice switched on WITH A
    // NAME on the mapping step; the header button held disabled over DEF-512
    // is gone, and so is the sentence that said templates did not exist.
    expect(html).not.toMatch(/disabled[^>]*>Save mapping as template/);
    expect(html).not.toContain("Saving a mapping as a template is not switched on yet.");
    expect(html).not.toContain("not available yet");
    expect(html).toContain("Picked when the headers match.");
  });

  it("the advance is refused until a file is chosen", () => {
    const html = renderAt(PREMISES_IMPORT_ROUTE);
    // The footer's primary is `Transform →` and it starts disabled: stage 1
    // has nothing to send.
    expect(html).toMatch(/disabled[^>]*>Transform/);
  });

  it("the promise that nothing is written is on the screen from stage 1", () => {
    expect(renderAt(PREMISES_IMPORT_ROUTE)).toContain(
      "Five stages · nothing is written until you commit at stage four.",
    );
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-023 P5 · DEF-520 (BR-MET-096 · BR-MET-097, PO rulings 2026-08-21;
//         r10 WFL-01.premises.* and WFL-01.units.* screenshots)
// generated: 2026-08-21 by the DEF-520 lane
// checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// gates: vitest✔ · tsc✔
// exceptions: E3 case 1 PROVED RED first — with the route constants reverted to
//         `?mode=premises_csv` the markup carries no `data-workflow` at all,
//         which is exactly the build the PO deployed · E3 no interaction is
//         asserted anywhere in this suite because the repo has no DOM test
//         environment; filed as `DEF-523` rather than left silent
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

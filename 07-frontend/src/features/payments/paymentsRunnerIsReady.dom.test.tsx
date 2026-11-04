// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:   CR-135 phase 1 · `P1.17` — "Mount the runner, not a copy of it".
//           Blueprint `05-prototype/06 Payments Page Blueprint.pdf` p067:
//           *"The screen exists and works for seven targets. Payments is not
//           one of them."* This file is what makes it eight.
// Screens:  4·3a Import (the runner's Extract stage) on the payments target
// Rules:    BR-MET-096 (ONE ETL runner, `target` parameterised) · B14 rule 21
//           (`ImportWorkflowPage` carries ZERO stylesheet classes) · rule 36
//           (the shared component kit is how you comply) · rule 43
// Tests:    this file
// ───────────────────────────────────────────────────────
//
// ⚠ **`P1.17`'s TASK IS A CONSTRAINT ON HOW THE SCREEN IS MOUNTED, NOT A SCREEN
// OF ITS OWN**, and its outcome sentence is the whole of it: *"No hand-rolled
// stage, rail or reject table. The kit's own header records what happened the
// last time a screen took half of it."* That header is
// `components/workflow/index.ts`: *"ONE IMPORT PATH FOR THE WHOLE KIT, so a
// screen that needs the runner cannot reach half of it and hand-roll the other
// half — which is how `ImportAccountsWizard.tsx` ended up drawing a customers
// screen out of metering's stylesheet."*
//
// ⚠ **THE DOOR IS `P1.5`'s AND IT IS NOT MINE.** The blueprint gives the
// Extract stage exactly one: *"Import → on 4·1. 1 door."* — the Imports tab's
// own toolbar. That tab landed on 2026-09-22 HELD, with
// `PAYMENTS_TABS_AWAITING_A_SCREEN[imports] = "P1.5"` naming the task that
// releases it. So this file deliberately mounts NO ROUTE: a route reachable
// only by typing its address is a doorless screen, which is the defect
// `G100` exists for and the opposite of what this lane has spent the day
// removing.
//
// **What it proves instead is the thing `P1.5` needs to know before it starts:
// that the ONE runner already renders correctly for `target="payments"`.** If
// it did not, `P1.5`'s lane would find out by hand-rolling — which is exactly
// the outcome `P1.17` exists to prevent.

import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { ToastProvider } from "@/components/Toast";
import { WORKFLOW_KINDS, workflowSourcesFor } from "@/components/workflow";
import { ImportWorkflowPage } from "@/features/metering/ImportWorkflowPage";

const t = (key: string): string => i18n.t(key);

/** A client that answers nothing. Stage 1 makes no request — the blueprint's
 *  own note: *"Nothing is written until Load"* — so every assertion below is
 *  about what the screen DRAWS before it has asked the server anything. */
const SILENT_CLIENT = {
  get: () => new Promise(() => {}),
  post: () => new Promise(() => {}),
  patch: () => new Promise(() => {}),
  put: () => new Promise(() => {}),
  delete: () => new Promise(() => {}),
} as never;

function mountPaymentsRunner() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* ⚠ MOUNTED UNDER THE REAL PATH PATTERN. CLAUDE.md law 2 records why:
            a bare MemoryRouter with no `/:tenant/…` route leaves
            `useParams().tenant` undefined and every address the screen builds
            comes out `//…`, a protocol-relative URL to another host that reads
            as a perfectly good string to `toContain`. */}
        <MemoryRouter initialEntries={["/brazos-bend/payments/import"]}>
          <Routes>
            <Route
              path="/:tenant/payments/import"
              element={<ImportWorkflowPage target="payments" client={SILENT_CLIENT} />}
            />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("P1.17 · the ONE runner already runs on the payments target", () => {
  it("renders at all — the eighth target needs no eighth implementation", () => {
    const { container } = mountPaymentsRunner();
    expect(container.querySelector('[data-workflow="runner"]')).not.toBeNull();
    expect(container.querySelector('[data-workflow="runner"]')?.getAttribute("data-stage")).toBe(
      "1",
    );
  });

  it("it is the KIT's rail and reject table, never a copy — zero hand-rolled stages", () => {
    // `P1.17`'s outcome sentence, made checkable. Every one of these hooks is
    // written by a component in `components/workflow/`, so their presence IS
    // the proof that the page mounted the kit rather than drawing its own.
    const { container } = mountPaymentsRunner();
    expect(container.querySelector('[data-workflow="stagebar"]')).not.toBeNull();
    expect(container.querySelector('[data-workflow="source-cards"]')).not.toBeNull();
    expect(container.querySelector('[data-workflow="write-mode"]')).not.toBeNull();
  });

  it("the screen carries no stylesheet class of its own (B14 rule 21)", () => {
    // `ImportWorkflowPage` is on `route-b-migrated.txt` and the blueprint names
    // it as the reference BECAUSE it "carries zero stylesheet classes". The
    // three prefixes below are the per-feature stylesheets a hand-rolled copy
    // would reach for — `met-`, `pay-` and `cus-` each have a .css file.
    const { container } = mountPaymentsRunner();
    const classes = [...container.querySelectorAll<HTMLElement>("[class]")].flatMap((node) =>
      node.className.split(/\s+/),
    );
    for (const prefix of ["met-", "pay-", "cus-"]) {
      expect(
        classes.filter((name) => name.startsWith(prefix)),
        `the runner reached into a feature stylesheet with a "${prefix}" class`,
      ).toEqual([]);
    }
  });

  it("it draws payments' OWN kicker and exit, not premises' (the DEF-623 shape)", () => {
    // In a kit parameterised by target, an UNparameterised string is a claim
    // about one target that every other target repeats — which is what put
    // "rolling back reverses every premise and unit" over an accounts load.
    mountPaymentsRunner();
    expect(screen.getAllByText(t("workflow.payments.kicker")).length).toBeGreaterThan(0);
    expect(WORKFLOW_KINDS.payments.returnTo).toBe("/payments");
  });

  it("stage 1 offers the FIVE source cards payments has, Scan paper last (P1.19)", () => {
    const { container } = mountPaymentsRunner();
    const cards = container.querySelectorAll("[data-workflow-source]");
    expect(cards.length).toBe(workflowSourcesFor("payments").length);
    expect(cards[cards.length - 1]?.getAttribute("data-workflow-source")).toBe("scan");
  });

  it("stage 1 draws BOTH write modes and refuses one, with its reason (P1.18)", () => {
    const { container } = mountPaymentsRunner();
    const modes = container.querySelectorAll("[data-write-mode]");
    expect(modes.length).toBe(2);
    expect(container.querySelector('[data-write-mode="upsert"][data-refused="true"]')).not.toBeNull();
    expect(container.querySelector('[data-write-mode="insert"][data-refused="false"]')).not.toBeNull();
    // ⚠ COUNTED OFF THE REFUSAL HOOK, NOT off `getAllByText`. The runner draws
    // the write-mode control on more than one stage, so a text search answers
    // "how many nodes contain this sentence" — a different question, and one
    // whose answer moves whenever the page grows a stage.
    expect(container.querySelectorAll('[data-workflow="write-mode-refused"]').length).toBe(1);
  });

  it("and the premises runner is untouched by all of it — four cards, both modes live", () => {
    // The regression half. Everything above is per-target, and the way a
    // per-target rule goes wrong is by leaking onto the other seven.
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazos-bend/premises/import"]}>
            <Routes>
              <Route
                path="/:tenant/premises/import"
                element={<ImportWorkflowPage target="premises" client={SILENT_CLIENT} />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    expect(container.querySelectorAll("[data-workflow-source]").length).toBe(4);
    expect(container.querySelector("[data-workflow-source='scan']")).toBeNull();
    expect(container.querySelector('[data-refused="true"]')).toBeNull();
  });
});

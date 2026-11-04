// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1. `vite.config.ts` keeps
// the default environment at `node` deliberately (`DEF-523`), and a suite that
// mounts a page with hooks, a query client and a router opts in per file.
/* ══════════════════════════════════════════════════════════════════════════
 * THE SERVER'S ACTUAL SETUP PAYLOAD, DRAWN BY THE ACTUAL SCREEN.
 *
 * Story: US-RBS-016 · US-RBS-001 — CR-075, `RBS-004`.
 * Rules: `07-endpoints.md` rows 2 and 8 · `NFR-3` · B14 rules 31, 32 and 35 ·
 *        `BR-RBS-002` (a Check writes nothing, and that is the promise) ·
 *        `BR-RBS-038` (every edit mints a version).
 *
 * ⚠ **THIS FILE EXISTS BECAUSE OF `DEF-RBS-4308`, AND IT IS THE THIRD TIME THE
 * SAME SHAPE COST A SCREEN IN ONE DAY.** `DEF-RBS-4284`: the engine and the
 * twelve report blocks disagreed on all six payloads, both suites green,
 * because only the block NAMES were checked. `DEF-RBS-4285`: the same thing one
 * level up on the definition. Then this — the client cast
 * `GET /runbooks/{key}`'s body straight to `RunbookSetupView` with no mapper
 * and **`RBS-004` threw in a real browser from 16:23 UTC on 2026-09-06**:
 *
 *     TypeError: Cannot read properties of undefined (reading 'length')
 *
 * on `view.capabilities.length`. `tsc` was green (the cast is unchecked at
 * runtime), 49 unit cases were green (they pass a hand-built view model as a
 * prop), every gate was green. **The pattern each time is two declarations of
 * one thing and nothing checking them against each other.**
 *
 * ══════════════════════════════════════════════════════════════════════════
 * WHAT MAKES THIS DIFFERENT FROM THE 49 CASES THAT PASSED OVER THE DEFECT
 * ══════════════════════════════════════════════════════════════════════════
 * `RunbookSetup.dom.test.tsx` hands the screen a hand-built `RunbookSetupView`.
 * That is the right test for the RENDERER and it is structurally incapable of
 * seeing this class: the prop it builds is correct by construction, so the
 * question *does the server send this* is never asked.
 *
 * This file starts one layer earlier. It feeds `getRunbookSetup` — the real
 * client, through the real `readListPage` envelope reader — a stub transport
 * that answers with a REAL RECORDED RESPONSE BODY, maps it with the real
 * `toSetupView`, and renders the real `RunbookSetupPage` at the real
 * route. The fixture is written by
 * `06-backend/tests/test_rbs004_setup_payload_conformance.py` from a live
 * endpoint, and that test asserts the committed bytes still match. **So the
 * endpoint cannot drift without failing there and the screen cannot drift
 * without failing here. Neither side can move alone.**
 *
 * ⚠ **WHAT WOULD MAKE THIS CHECK PASS WRONGLY** — asked because a check you
 * cannot describe a false pass for is one you do not understand. Asserting only
 * that the page rendered SOMETHING: a screen fed a payload it cannot read still
 * returns a `<main>`, and the pre-mapper build did exactly that for the head
 * before throwing on a tab. So every assertion below names a VALUE OUT OF THE
 * FIXTURE and requires it on screen. A shape that drifts makes the value
 * disappear, not the markup.
 * ══════════════════════════════════════════════════════════════════════════ */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import type { ApiClient, ApiResponse, RequestOptions } from "@/api/client";
import { TenantRegionalProvider } from "@/components/TenantRegional";
import { ToastProvider } from "@/components/Toast";

import fixture from "./__fixtures__/rbs004-setup.json";
import type { WireActivity } from "./setupWire";
import { RunbookSetupPage } from "./RunbookSetupPage";

const TENANT = "brazosbend";
const KEY: string = fixture.detail.key;

// ⚠ **THERE IS NO AUTO-CLEANUP IN THIS REPO.** `vite.config.ts` sets no
// `setupFiles`, so `@testing-library/react` never registers its own `afterEach`
// and every render is ADDED to the same document — which silently breaks every
// "exactly N" count. `RunbookSetup.dom.test.tsx` carries this line for the same
// reason and records what it cost to find.
afterEach(cleanup);

/**
 * A transport that answers the two paths `getRunbookSetup` asks for, with the
 * recorded bodies, and REFUSES anything else BY NAME.
 *
 * ⚠ **THE REFUSAL IS THE POINT OF THE STUB.** A permissive stub that answered
 * `{}` to an unexpected path would let the page draw an empty screen and this
 * file would report a pass over it — the exact failure mode being cured. A
 * throw names the path in the test output instead.
 */
function stubClient(): ApiClient {
  const answer = <T,>(body: unknown): Promise<ApiResponse<T>> =>
    Promise.resolve({ status: 200, data: body as T, headers: new Headers() } as ApiResponse<T>);

  const get = <T,>(path: string, options?: Omit<RequestOptions, "method" | "body">) => {
    if (path === `/runbooks/${KEY}`) {
      return answer<T>(fixture.detail);
    }
    if (path === "/runbooks/runs") {
      const filter = (options?.query ?? {})["f.runbook"];
      expect(filter, "the runs tab must ask the server for THIS runbook").toBe(KEY);
      return answer<T>(fixture.runs);
    }
    throw new Error(`the screen asked for ${path}, which this fixture does not record`);
  };

  const refuse = () => {
    throw new Error("this conformance render performs no writes");
  };

  return {
    request: get,
    get,
    post: refuse,
    put: refuse,
    patch: refuse,
    del: refuse,
  } as unknown as ApiClient;
}

/** The page, at the REAL path pattern, with the tab named by the hash.
 *
 *  ⚠ **NEVER A BARE `MemoryRouter` (`DEF-CWP-3925`).** Mounted without a
 *  `/:tenant/runbooks/:key` route, `useParams()` gives `undefined`, the page
 *  fetches `/runbooks/` and every address it builds comes out `//host/…` — a
 *  protocol-relative URL that reads as a perfectly good string to `toContain`.
 *  That is how eight dead doors hid behind 391 green cases. */
function mount(hash = "") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <TenantRegionalProvider value={{ timeZone: "America/Chicago", dateFormat: "MM/DD/YYYY" }}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TENANT}/runbooks/${KEY}${hash}`]}>
            <Routes>
              <Route
                path="/:tenant/runbooks/:key"
                element={<RunbookSetupPage client={stubClient()} />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </TenantRegionalProvider>
    </QueryClientProvider>,
  );
}

/** Wait for the payload to have been mapped and painted. */
async function paint(hash = "") {
  const rendered = mount(hash);
  await waitFor(() => expect(screen.getByRole("heading", { level: 1 })).toBeDefined());
  return rendered;
}

describe("RBS-004 · the recorded payload, through the real client and the real screen", () => {
  it("draws the runbook's own name as the H1, over the server's body", async () => {
    await paint();
    // The value comes OUT OF THE FIXTURE rather than being typed here, so a
    // renamed field makes the assertion fail rather than making it stale.
    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain(fixture.detail.name);
  });

  it("renders every one of the seven tabs without throwing", async () => {
    // ⚠ **THIS IS THE CASE THAT WOULD HAVE CAUGHT `DEF-RBS-4308`, AND IT IS
    // WORTH SAYING WHY IT IS NOT VACUOUS.** The pre-mapper build threw inside
    // `OverviewTab` on `view.capabilities.length`; React unmounts the whole
    // tree on an uncaught render error, so `getByRole("tablist")` is what
    // disappears. Seven tab strips is therefore seven successful renders.
    for (const tab of ["overview", "steps", "scope", "guards", "limits", "runs", "activity"]) {
      const { unmount } = await paint(`#${tab}`);
      const strip = screen.getByRole("tablist");
      expect(within(strip).getAllByRole("tab"), `the ${tab} tab did not draw`).toHaveLength(7);
      unmount();
    }
  });

  it("Overview draws the schedule, the last run and BR-RBS-002's safety promise", async () => {
    const { container } = await paint("#overview");
    const text = container.textContent ?? "";
    // The time zone is the server's own value, translated by nobody.
    expect(text).toContain(fixture.detail.schedule.timezone);
    // A Check holds no ports at all, so *nothing* is not an empty list — it is
    // the promise a two-person utility relies on. `BR-RBS-002`.
    expect(fixture.detail.kind).toBe("check");
    expect(container.querySelector('[data-absent="capabilities"]')?.textContent).toContain(
      "Nothing is written",
    );
    // The run the fixture stored, drawn as a WORD rather than as the code.
    expect(text).toContain("Done");
    expect(text).not.toContain("approve_each_run");
  });

  it("Steps draws every step the stored definition holds, with its read/writes marker", async () => {
    const { container } = await paint("#steps");
    const steps = fixture.detail.definition.steps;
    expect(steps.length).toBeGreaterThan(0);
    expect(container.querySelectorAll("[data-step]")).toHaveLength(steps.length);
    for (const step of steps) {
      expect(container.textContent, `the step "${step.label}" drew nothing`).toContain(step.label);
    }
    // Every step of a Check reads; `writes` drives the marker and nothing else.
    expect(container.querySelectorAll('[data-step-writes="read"]')).toHaveLength(steps.length);
  });

  it("Scope draws the runbook's own parameter labels — BR-RBS-042's inputs", async () => {
    const { container } = await paint("#scope");
    const parameters = fixture.detail.definition.parameters;
    expect(parameters.length).toBeGreaterThan(0);
    for (const parameter of parameters) {
      expect(container.textContent, `the input "${parameter.label}" drew nothing`).toContain(
        parameter.label,
      );
    }
  });

  it("Limits draws the cap the server stores and the approval as a WORD", async () => {
    const { container } = await paint("#limits");
    const text = container.textContent ?? "";
    expect(text).toContain(String(fixture.detail.cap));
    // `approve_each_run` is a code. B14 rule 31's spirit and rule 35's letter:
    // the word comes from the catalogue, in the reader's language.
    expect(text).toContain("A person approves each run");
    expect(text).not.toContain(fixture.detail.gate_mode);
  });

  it("Runs draws the server's page and asks the server for it", async () => {
    const { container } = await paint("#runs");
    // The stub asserts `f.runbook` on the way in; this asserts the rows came
    // back out. `NFR-3`: the page travels, nothing here slices an array.
    expect(fixture.runs.count).toBeGreaterThan(0);
    expect(container.textContent).toContain("Done");
  });

  it("Activity composes a SENTENCE from the server's facts, in the reader's language", async () => {
    const { container } = await paint("#activity");
    const text = container.textContent ?? "";
    // ⚠ **THE FACT AND THE SENTENCE ARE DIFFERENT THINGS AND THIS IS WHERE THE
    // SEAM IS.** The server sends `{"field": "cap", "from": null, "to": 400}`
    // and the screen says *Cap raised to 400* — because eleven catalogues each
    // have to phrase it (B14 rule 35), and a server that sent the English would
    // put screen copy in Python.
    // ⚠ **AN ANNOTATION, NEVER `as`.** `reportConformance.test.tsx` records why:
    // `as` is an ASSERTION and it SILENCES exactly the error a conformance test
    // exists to raise. `WireActivity["changes"]` is `setupWire.ts`'s own declared
    // shape, so a fact whose fields moved fails the typecheck here rather than
    // passing quietly. (The `unknown` hop is JSON's — `resolveJsonModule` infers
    // one literal type per array, not the union.)
    const changes: WireActivity["changes"] = fixture.detail.activity.flatMap(
      (row) => row.changes as unknown as WireActivity["changes"],
    );
    const capChange = changes.find((change) => change.field === "cap");
    expect(capChange, "the fixture records no cap change — this case checks nothing").toBeDefined();
    // ⚠ **`Cap SET to 400`, NOT `raised`, AND THE DIFFERENCE IS THE FACT.** The
    // recorded change is `{from: null, to: 400}` — a cap where there was none —
    // and `setupModel.phrase` says *set* for that and reserves *raised* for a
    // number that actually went up. Asserting *raised* here would pin a
    // sentence the data does not support.
    expect(text).toContain(`Cap set to ${String(capChange!.to)}`);
    expect(text).toContain("Paused");
    expect(text).toContain("Added from templates");
    // Never the raw field name, and never a version's database id.
    expect(text).not.toContain("gate_mode");
    expect(text).toContain(`v${String(fixture.detail.activity[0].version)}`);
  });

  it("prints no database id and no rule id anywhere in the seven tabs", async () => {
    // B14 rules 31 and 32, over the whole payload rather than over a fixture
    // somebody trimmed. `RunbookSetupView` has no uuid field at all, so this
    // asserts the mapper did not smuggle one in from the wire.
    for (const tab of ["overview", "steps", "scope", "guards", "limits", "runs", "activity"]) {
      const { container, unmount } = await paint(`#${tab}`);
      const text = container.textContent ?? "";
      expect(text, `a uuid reached the ${tab} tab`).not.toMatch(
        /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/,
      );
      expect(text).not.toMatch(/\bBR-[A-Z]{3}-\d/);
      expect(text).not.toMatch(/\bRBS-\d/);
      unmount();
    }
  });
});

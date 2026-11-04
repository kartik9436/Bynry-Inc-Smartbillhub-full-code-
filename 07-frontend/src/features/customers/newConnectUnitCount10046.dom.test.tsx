// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect:  DEF-CUS-10046 — New Connect step 3 (SR-26-0027): step 2's unit `2`
//          was carried into Common selection as *Units from 2 To 2*, which
//          makes ONE unit labelled `2`; the PO expected two units, and the
//          screen did not say how many the range creates.
// Judgment (coordinator, recorded, not asked — hard-won law 13): step 2's box
//          is a unit LABEL (its own help: *"Part of the mailing address. Units
//          are named on step 3."*), so it stays a label, and the range now
//          states the count beside it so the clerk can see and correct it.
// Rules:   B14 rule 33 (a fact ≤ 6 words) · rule 43 (the kit field's `help`)
// ───────────────────────────────────────────────────────
//
// WHAT WOULD MAKE THESE PASS WRONGLY (law 7, habit 2): a count read from the
// boxes rather than from the units the commit makes. The host here derives the
// units with `draftUnits` — the function the commit uses — so the line and
// the commit cannot disagree; and the common area, which is its own tick box,
// is asserted NOT counted as a dwelling.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { cleanup, fireEvent, render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18next from "i18next";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { draftFromRaisedBuild, draftUnits, emptyDraft } from "./newConnectDraft";
import type { NewConnectDraft } from "./newConnectDraft";
import type { ConnectionDetail } from "./newConnectEndpoints";
import { UnitsStep, rangeCountLine } from "./NewConnectUnitsStep";

afterEach(cleanup);

const t = (key: string, options?: Record<string, unknown>) => String(i18next.t(key, options));

/** The draft SR-26-0027 leaves behind: unit line `2`, so the range 2 to 2. */
function fromRequest(): NewConnectDraft {
  return draftFromRaisedBuild(emptyDraft(), {
    id: "b-27",
    connection_no: "CON-26-0227",
    premises: null,
    request_no: "SR-26-0027",
    mode: null,
    target_activation: null,
    prefill: { request_id: "r-27", address_unit_as_given: "2" },
  } as unknown as ConnectionDetail);
}

function mount(start: NewConnectDraft) {
  const client = createApiClient({
    tenant: "brazosbend",
    fetchImpl: async () =>
      new Response(JSON.stringify({ count: 0, results: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  });
  function Host() {
    const [draft, setDraft] = useState(start);
    return (
      <UnitsStep
        draft={draft}
        units={draftUnits(draft)}
        labelsAlreadyHere={[]}
        breaches={[]}
        sewerGaps={[]}
        proposed={[]}
        proposalsUnavailable={false}
        onPatch={(patch) => setDraft((now) => ({ ...now, ...patch }))}
        client={client}
        t={t}
        dateFormat="MM/DD/YYYY"
      />
    );
  }
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/connections/new?step=3"]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={<Host />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function helpOfTo(): string {
  return document.getElementById("nc_to-help")?.textContent ?? "";
}

describe("DEF-CUS-10046 · the range says how many units it creates", () => {
  it("the request's unit 2 is seeded as 2 to 2 and the screen says ONE unit", () => {
    const draft = fromRequest();
    expect([draft.pattern.from, draft.pattern.to]).toEqual(["2", "2"]);
    mount(draft);
    expect(helpOfTo()).toBe("Creates 1 unit");
  });

  it("widening the range moves the count: 1 to 2 creates 2 units", () => {
    mount(fromRequest());
    fireEvent.change(document.getElementById("nc_from") as HTMLInputElement, {
      target: { value: "1" },
    });
    expect(helpOfTo()).toBe("Creates 2 units");
  });

  it("the common area is not counted as a dwelling", () => {
    const base = emptyDraft();
    const line = rangeCountLine(
      { ...base.pattern, from: "101", to: "105", includeCommonArea: true },
      draftUnits({ ...base, pattern: { ...base.pattern, from: "101", to: "105", includeCommonArea: true } }),
      t,
    );
    expect(line).toBe("Creates 5 units");
  });

  it("an empty range says nothing", () => {
    const base = emptyDraft();
    expect(rangeCountLine(base.pattern, draftUnits(base), t)).toBeUndefined();
  });
});

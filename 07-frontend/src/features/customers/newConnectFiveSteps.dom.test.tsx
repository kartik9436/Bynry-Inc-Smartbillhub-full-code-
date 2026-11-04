// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-150-BRC09 — New Connect's EIGHT steps become FIVE. PO ruling
//          2026-09-28, verbatim: *"these steps are good - we need 1 word - for
//          every step"* and *"we dont want any information to be reduced or
//          lost - 8 steps → 5"*.
// Drawing: `05-prototype/new-connect-redesign-2026-09-28/` — `step1-customer.png`
//          · `step2-premise.png` · `step3-units.png` · `step4-charges.png` ·
//          `step5-review.png`, opened with the Read tool and LOOKED AT as
//          IMAGES before a line of this file (B14 rule 42). Every word
//          asserted below was read off a PNG, not off the change request.
// Rules:   BR-SHL-046 (ONE declared step list) · BR-SHL-011 (an out-of-range
//          `?step=` clamps, it never errors) · B14 rule 37 (a drawn figure is
//          an ILLUSTRATION — the COUNT comes from the declared list, which is
//          why `Step N of 5` is asserted against the list and not a literal) ·
//          B14 rule 42 · CLAUDE.md hard-won law 6 (no gate reads rendered
//          output) · law 7 (know what would make this pass wrongly)
// Screens: S87, all five steps
// ───────────────────────────────────────────────────────
//
// ⚠ **A NEW FILE RATHER THAN CASES ADDED TO `NewConnectWizard.test.tsx`.** That
// file is 1,400 lines and three lanes are inside this wizard at once; in a
// shared tree the second lane to commit a shared file reverts the first, with
// a correct file count and nothing in the diff to notice (CLAUDE.md law 11).
//
// ⚠ **EVERY CASE READS RENDERED OUTPUT, NEVER A PROP OR A CONSTANT.** The two
// ways this change can be wrong are both invisible to a constant: a rail that
// draws the right list under the wrong H1, and a merged step that keeps the
// list entry and loses the fields. Both need the DOM, so the wizard is mounted
// under the real `/:tenant/connections/new` route — a bare `MemoryRouter`
// leaves `useParams().tenant` undefined and every address the page builds
// comes out `//connections/…`, which reads as a perfectly good string to
// `toContain` (law 2's fixture note).
//
// ⚠ **WHAT WOULD MAKE THESE PASS WRONGLY, named rather than left to a reader.**
// Asserting the H1 by `getByText` alone would pass on a heading rendered
// anywhere, so each title is read off the `<h1>`. Asserting the rail by count
// alone would pass on five cells reading the wrong words, so the words are
// read in order. And a step that renders its absorbed fields but drops the
// absorbed step's `validate` would pass every case here — which is why
// `the merged step keeps the guard` exists below.
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { createApiClient } from "@/api/client";
import { ToastProvider } from "@/components/Toast";

import { NewConnectWizard, stepOwningRefusal } from "./NewConnectWizard";
import {
  NEW_CONNECT_STEPS,
  NEW_CONNECT_STORED_STEP,
  newConnectStepNumber,
  newConnectStoredStep,
} from "./newConnectShared";
import { stepOf } from "./parkedDrafts";
import { ApiError } from "@/api/client";

const TEST_TENANT = "brazosbend";

afterEach(cleanup);

/** Every read this wizard makes answers EMPTY — in the shape its own caller
 *  expects, which is not one shape.
 *
 *  ⚠ **A SINGLE `{count, results}` BODY IS NOT A NEUTRAL FIXTURE.**
 *  `GET /settings/services` serves a bare ARRAY and `enabledServiceRows`
 *  calls `.filter` on it, so one body for every URL crashes step 3 — and a
 *  crashed render leaves the previous step's DOM standing, which is how a
 *  title assertion passes against the wrong screen. The dispatch below is the
 *  difference between an empty fixture and a broken one. */
function mountAt(query: string) {
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL) => {
      const url = String(input);
      const body = /\/settings\/services/.test(url) ? [] : { count: 0, results: [] };
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}/connections/new${query}`]}>
          <Routes>
            <Route path="/:tenant/connections/new" element={<NewConnectWizard client={client} />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/** The `<h1>` the page head draws — read off the heading, never off the page. */
function pageTitle(): string {
  return (screen.getAllByRole("heading", { level: 1 })[0].textContent ?? "").trim();
}

// ════════════════════════════════════════════════════════════════════════════
// 1 · THE FIVE, AND THE ONE WORD EACH
// ════════════════════════════════════════════════════════════════════════════
describe("CR-150 · the declared list", () => {
  it("is five steps, in the drawn order, with the drawn ids", () => {
    expect(NEW_CONNECT_STEPS.map((step) => step.id)).toEqual([
      "customer",
      "premise",
      "units",
      "charges",
      "review",
    ]);
  });

  it("names each step in ONE word, which is the ruling", () => {
    // PO: *"we need 1 word - for every step"*. A two-word label is not a
    // style slip here, it is the ruling unmet — *Review & confirm* and
    // *Owner & scope* are exactly what this replaced.
    for (const step of NEW_CONNECT_STEPS) {
      expect(step.en.trim().split(/\s+/)).toHaveLength(1);
    }
    expect(NEW_CONNECT_STEPS.map((step) => step.en)).toEqual([
      "Customer",
      "Premise",
      "Units",
      "Charges",
      "Review",
    ]);
  });

  it("gives every step a LITERAL catalogue key G18 can see", () => {
    for (const step of NEW_CONNECT_STEPS) {
      expect(step.labelKey).toBe(`customers.newConnect.step.${step.id}`);
    }
  });

  it("resolves a step's number from its id, so nobody types one", () => {
    expect(newConnectStepNumber("customer")).toBe(1);
    expect(newConnectStepNumber("premise")).toBe(2);
    expect(newConnectStepNumber("units")).toBe(3);
    expect(newConnectStepNumber("charges")).toBe(4);
    expect(newConnectStepNumber("review")).toBe(5);
    // A step that no longer exists answers null rather than a position.
    expect(newConnectStepNumber("services")).toBeNull();
    expect(newConnectStepNumber("plans")).toBeNull();
    expect(newConnectStepNumber("communication")).toBeNull();
    expect(newConnectStepNumber("owner")).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 2 · THE RAIL AND THE PAGE HEAD, AS RENDERED
// ════════════════════════════════════════════════════════════════════════════
describe("CR-150 · the frame, in the DOM", () => {
  it("draws FIVE cells in the rail, reading the ruled words in order", () => {
    mountAt("?step=1");
    const cells = Array.from(document.querySelectorAll("[data-wizard-step]"));
    expect(cells).toHaveLength(5);
    expect(cells.map((cell) => cell.getAttribute("data-wizard-step"))).toEqual([
      "1",
      "2",
      "3",
      "4",
      "5",
    ]);
    // ⚠ **THE WORD IS READ EXACTLY, NOT WITH `toContain`, AND THAT IS THIS
    // CHANGE'S OWN SCAR.** A rail cell renders the CATALOGUE value; the `en`
    // on the list is only a `defaultValue` fallback. `en.json` still held
    // *Review & confirm* after the list said *Review* — and
    // `toContain("Review")` is TRUE of *Review & confirm*, so the suite was
    // green, `tsc` was green, and the BROWSER WALK is what read the rail and
    // saw two words under a one-word ruling (hard-won law 6). The cell
    // carries its number too, so the number is stripped rather than the
    // match loosened.
    for (const [at, step] of NEW_CONNECT_STEPS.entries()) {
      const word = (cells[at].textContent ?? "").replace(String(at + 1), "").trim();
      expect(word).toBe(step.en);
      expect(word.split(/\s+/)).toHaveLength(1);
    }
    // And the words that LEFT are not still in the rail.
    const rail = cells.map((cell) => cell.textContent ?? "").join(" ");
    expect(rail).not.toMatch(/Map services|Work orders|Communication|Owner/);
  });

  it.each([
    [1, "Who is asking, and what for?", "Customer"],
    [2, "The premise", "Premise"],
    [3, "The units", "Units"],
    [4, "Charges", "Charges"],
    [5, "What will be created", "Review"],
  ])("step %i draws its drawn H1 and `Step N of 5`", (at, title, word) => {
    mountAt(`?step=${at}`);
    expect(pageTitle()).toBe(title);
    expect(screen.getByText(new RegExp(`Step ${at} of 5`))).toBeInTheDocument();
    // Exactly the ruled word, for the reason above — the step line renders
    // the same catalogue value the rail does.
    expect(screen.getByText(new RegExp(`Step ${at} of 5`)).textContent).toBe(
      `Step ${at} of 5 · ${word}`,
    );
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 3 · AN OLD STEP NUMBER — A BOOKMARK, A TICKET, AN ERROR REPORT
// ════════════════════════════════════════════════════════════════════════════
describe("CR-150 · a number off the eight-step list", () => {
  it("maps exactly as the PO ruled — 1→1, 2→2, 3/4/5→3, 6→4, 7/8→5", () => {
    expect(NEW_CONNECT_STORED_STEP).toEqual({ 1: 1, 2: 2, 3: 3, 4: 3, 5: 3, 6: 4, 7: 5, 8: 5 });
  });

  it("hands a number it does not know straight through, for the clamp to catch", () => {
    // The map decides WHICH step; the clamp still decides IN RANGE. A map
    // that clamped as well would be a second opinion about the bounds.
    expect(newConnectStoredStep(0)).toBe(0);
    expect(newConnectStoredStep(99)).toBe(99);
    expect(newConnectStoredStep(2.5)).toBe(2.5);
  });

  it.each([
    [6, "Charges"],
    [7, "What will be created"],
    [8, "What will be created"],
  ])("an old `?step=%i` link opens the step that now holds its fields", (old, title) => {
    // ⛔ **THE ONE THAT MATTERS IS `?step=6`.** It was *Charges*; a bare clamp
    // holds 6 inside [1,5] as 5 and opens **Review**, one step PAST the charge
    // lines and the payment terms, on a page whose button says *Create
    // connection*.
    mountAt(`?step=${old}`);
    expect(pageTitle()).toBe(title);
  });

  it.each([
    [1, "Who is asking, and what for?"],
    [2, "The premise"],
    [3, "The units"],
    [4, "Charges"],
    [5, "What will be created"],
  ])("reads `?step=%i` in the FIVE-step shape, because it is ambiguous", (at, title) => {
    // ⚠ **THIS IS THE DECISION, ASSERTED RATHER THAN IMPLIED.** `?step=4` was
    // *Map services* yesterday and is *Charges* today, and nothing in the
    // address says which. It is read as TODAY's, for two reasons stated in
    // `newConnectAddressStep`: the wizard writes these numbers itself, so the
    // other reading walls Continue on step 3 forever; and a bare `?step=`
    // link carries no draft, so an old bookmark landing on an EMPTY Charges
    // instead of an EMPTY Units loses a clerk nothing.
    mountAt(`?step=${at}`);
    expect(pageTitle()).toBe(title);
  });

  it("walls nothing — Continue from step 3 reaches step 4 and stays there", () => {
    // ⛔ **THE REGRESSION THIS FILE ALREADY CAUGHT ONCE.** The first cut put
    // the FULL map on the address, so the wizard's own `setStep(4)` was read
    // back as 3 and Continue did nothing, forever, on a screen with no error.
    mountAt("?step=4");
    expect(pageTitle()).toBe("Charges");
  });

  it("still clamps a number off the end, and never errors (BR-SHL-011)", () => {
    mountAt("?step=97");
    expect(pageTitle()).toBe("What will be created");
    cleanup();
    mountAt("?step=banana");
    expect(pageTitle()).toBe("Who is asking, and what for?");
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 4 · A PARKED DRAFT, REOPENED
// ════════════════════════════════════════════════════════════════════════════
describe("CR-150 · a draft parked under the eight-step shape", () => {
  it("prints its step in the five-step shape on the waiting list", () => {
    // Without the map this row reads `Step 6 of 5` — not merely stale but
    // impossible, on a row a clerk is reading to decide what to pick up.
    expect(stepOf({ flow: "new_connect", step: 6 } as never)).toEqual({ step: 4, of: 5 });
    expect(stepOf({ flow: "new_connect", step: 8 } as never)).toEqual({ step: 5, of: 5 });
    expect(stepOf({ flow: "new_connect", step: 1 } as never)).toEqual({ step: 1, of: 5 });
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 5 · THE SERVER'S REFUSALS LAND ON THE STEP HOLDING THEIR FIELD
// ════════════════════════════════════════════════════════════════════════════
//
// ⚠ **THE POSITIONS MOVED AND THE IDS DID NOT, WHICH IS THE WHOLE DEFENCE.**
// `connections.py` declares exactly three — `STEP_OF_THE_PREMISE`,
// `STEP_OF_THE_UNITS`, `STEP_OF_THE_CHARGES` — and stamps them AT THE CALL
// SITE (`DEF-MET-7690`), never by matching a field name. So folding eight
// steps into five needs no second map: `charges` was position 6 and is now 4
// because `stepOwningRefusal` looks the id up in the declared list.
//
// ⚠ **A REFUSAL ON THE WRONG STEP IS WORSE THAN ONE WITH NO STEP**, because it
// sends a clerk to a screen where the field is not. That is what these assert.
describe("CR-150 · a server refusal, remapped by id and not by hand", () => {
  function refusal(step: string): ApiError {
    return new ApiError(422, {
      code: "BIZ-COMPLETENESS",
      message_key: "metering.connection_unit_label_taken",
      params: { step },
      br_ref: "BR-MET-112",
    });
  }

  it.each([
    ["premise", 2],
    ["units", 3],
    ["charges", 4],
  ])("`%s` lands on step %i, the step that now holds its fields", (id, position) => {
    expect(stepOwningRefusal(refusal(id))).toEqual({ id, position });
  });

  it("routes nothing it does not recognise, including a RETIRED step id", () => {
    // ⚠ A refusal stamped `services` would once have been step 4. Nothing
    // stamps it — but if anything ever did, the honest answer is the ordinary
    // failure card, never a guess at which of the five absorbed it.
    for (const gone of ["services", "plans", "communication", "owner"]) {
      expect(stepOwningRefusal(refusal(gone))).toBeNull();
    }
  });
});

// ════════════════════════════════════════════════════════════════════════════
// 6 · NOTHING IS LOST — *"we dont want any information to be reduced or lost"*
// ════════════════════════════════════════════════════════════════════════════
describe("CR-150 · the three absorbed steps still ask what they asked", () => {
  it("step 3 · Units carries the per-unit services AND the work orders", () => {
    // ⚠ **THE MARKERS ARE THE REDRAWN STEP'S, NOT THE OLD STEPS'.** The UNITS
    // lane rebuilt step 3 to `step3-units.png` — one *Units and service
    // points* table with a required *Apply to all* above it — so the old
    // `data-unit-service-grid` and `data-grid-counts` no longer exist
    // ANYWHERE and asserting them would be a check that can only fail. What
    // this case exists to hold is that the two absorbed steps' WORK is on
    // this screen, and these three markers are where it now lives. The
    // field-by-field audit is
    // `05-prototype/new-connect-redesign-2026-09-28/step3-absorbed-field-audit.md`.
    mountAt("?step=3");
    // Old step 3 · Units — the drawing's one *Units and service points*
    // table, with the `+ Add row` that replaced the From/To range
    // (`DEF-CUS-7605`: a range cannot express units 1, 2 and 15).
    expect(document.querySelector("[data-editable-table]")).not.toBeNull();
    expect(document.querySelector("[data-editable-addrow]")).not.toBeNull();
    // Old step 4 · Map services — the common selection applied to every unit.
    expect(document.querySelector("[data-apply-to-all]")).not.toBeNull();
    // Old step 5 · Work orders — the picker and the proposals it reads.
    expect(document.querySelector("[data-add-order]")).not.toBeNull();
    expect(document.querySelector("[data-proposals]")).not.toBeNull();
  });

  it("step 5 · Review carries the messages table from old step 7", () => {
    mountAt("?step=5");
    // Old step 7 · Communication — the whole Messages table, folded in.
    expect(document.querySelector("[data-telling]")).not.toBeNull();
    // ⊕ **AMENDED 2026-09-29 — THIS LINE COULD NEVER HAVE PASSED, WHICH IS
    // WORSE THAN A STALE ONE AND IS WHY IT IS WRITTEN OUT HERE.** It asked for
    // `[data-from-each-step]`, the review's old *From each step* `PlainTable`.
    // `22cf1c575` (09:07) replaced that table with four collapsible
    // `data-review-group` panels, each carrying its own `Edit ›`
    // (`DEF-CUS-7613`); this file was added by `ed4e7cb30` at **09:09, two
    // minutes later**, asserting a marker the tree no longer held. So it was
    // red on its first run on the branch — born red, not gone stale — and the
    // 20-of-30 RED proof recorded in that commit could not have covered it.
    //
    // **Re-pointed rather than deleted:** what the line is FOR is that the
    // review still shows what each earlier step answered. The groups are
    // where that lives now, so the case asks for them by name and pins the
    // four the redesign draws, in order — a bare "at least one group" would
    // go green again the day three of them are dropped.
    const groups = Array.from(document.querySelectorAll("[data-review-group]")).map((el) =>
      el.getAttribute("data-review-group"),
    );
    expect(groups).toEqual(["customer", "premise", "units", "charges"]);
  });

  it("the merged step still REFUSES Continue, so the guard came with the fields", async () => {
    // ⛔ **THIS IS THE CASE THE OTHERS CANNOT SEE.** A step that renders the
    // services grid and drops the services step's `validate` looks complete
    // and lets a unit take sewer without water — `TC-NCT-6`, a rule with a
    // meter behind it, un-enforced by a layout change.
    //
    // ⚠ **WHAT THIS PROVES AND WHAT IT DOES NOT.** It presses Continue on an
    // empty step 3 and asserts the wizard REFUSES and STAYS — which is the
    // merged `validate` running at all. The sewer-without-water half needs a
    // draft with units, services and a street that cannot deliver, which is a
    // browser walk and is named rather than faked here:
    // `10-scripts/cr150_new_connect_five_steps_walkthrough.mjs`.
    const user = (await import("@testing-library/user-event")).default.setup();
    mountAt("?step=3");
    await user.click(screen.getByRole("button", { name: /continue/i }));
    expect(pageTitle()).toBe("The units");
    expect(screen.getByText(/Add at least one unit\./)).toBeInTheDocument();
  });
});

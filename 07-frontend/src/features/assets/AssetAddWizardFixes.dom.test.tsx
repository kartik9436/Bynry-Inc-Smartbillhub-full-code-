// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-092-BRC01 step 2, wave B lane 5 — the add-asset wizard
//          (screens 28–31, blueprint PDF pages 109–119).
// Defects: DEF-MET-4980 (the utility service was a free-text box and
//          `GET /settings/services` was never called) · DEF-MET-4981 (the step
//          did not mark it required and the server refused on step 4) ·
//          DEF-MET-4983 (a reload kept the step and discarded every answer) ·
//          DEF-MET-4984 (the refused *Opening read* was pixel-identical to the
//          editable fields beside it) · DEF-MET-4985 (two device helpers named
//          a device that was not on screen) · DEF-MET-4986 (the service is not
//          kept on the default destination and nothing said so) ·
//          DEF-MET-4990 (the step-4 summary printed lookup CODES)
// Rules:   BR-AST-009 (a measuring kind declares a service) · BR-SHL-025 (a
//          control that cannot act is DISABLED with its reason) · B14 rule 11
//          (a consequence preview before a commit that changes service state) ·
//          B14 rule 31 (no internal code is the visible value of a field) ·
//          B14 rule 21 (both files are on src/styles/route-b-migrated.txt)
// ───────────────────────────────────────────────────────
//
// ⚠ **WHY A `.dom.test.tsx` AND NOT THE STATIC-RENDER SUITE.** Five of the
// seven are only reachable by PRESSING something — choosing a destination,
// pressing Continue, arriving on a step from an address. `AssetLifecycle.test`
// asserts the pure halves beautifully and cannot press a button, which is how
// every one of these survived: the front-end tests assert that `addPayload()`
// CONTAINS the service, which it does. The loss is downstream of that.
//
// RED-FIRST PROOF (r11 step 2d), taken against `ce623f444` before the change:
//
//   DEF-MET-4980 → `expected 'INPUT' to be 'SELECT'`
//   DEF-MET-4981 → `expected false to be true` (the required marker)
//   DEF-MET-4983 → `Unable to find an element with the text: Your answers…`
//   DEF-MET-4984 → `expected false to be true` (disabled)
//   DEF-MET-4985 → `expected '…inverters and batteries only.' not to match /inverter/`
//   DEF-MET-4986 → `Unable to find [data-consequence="assets-add-service-dropped"]`
//   DEF-MET-4990 → `expected '… · meter · water' to contain 'Water'`
//
// ⚠ **AND EACH WAS PROVED RED A SECOND TIME, ONE FIX AT A TIME.** The run above
// reverts the whole change, so most cases die on *"Unable to find a label"* —
// red for the right reason, but not on their own assertion. So the fixes were
// then sabotaged individually against the finished code, and each case failed
// alone: `readOnly` back on the opening read (4984), the consequence box
// rendered behind `false` (4986), the summary reading `values.type` /
// `values.service` again (4989), and the untouched-form guard forced true so
// the step is always honoured (4983 — both of its cases).
//
// ⚠ **TWO CASES HERE DO NOT DISCRIMINATE ON THEIR OWN AND SAY SO RATHER THAN
// PRETENDING (law 7 habit 2).** *"a PV inverter reads exactly the same
// sentences"* passes on the OLD code too — the old sentences were also shared,
// they were simply wrong — so it guards a future lane branching them and proves
// nothing about today. *"arriving at step 1 normally says nothing at all"* is a
// control case and passes everywhere by design; its job is to catch a redirect
// that fires when it should not.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import i18n from "@/i18n";
import { createApiClient } from "@/api/client";
import type { LookupEntry } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { AssetAddWizard } from "./AssetAddWizard";

afterEach(cleanup);

const t = (key: string): string => i18n.t(key);

/** `brazosbend`'s own shape: TWO enabled of the eleven the platform carries,
 *  and one disabled row so the filter is asserted rather than assumed. */
const SERVICES = [
  { service: "water", name: "Water", enabled: true },
  { service: "trash", name: "Trash", enabled: true },
  { service: "gas", name: "Gas", enabled: false },
];

function lookup(code: string, name: string, category: string): LookupEntry {
  return { id: code, code, name, active: true, is_system: true, used_by: 0, category } as LookupEntry;
}

const TYPES: LookupEntry[] = [
  lookup("meter", "Meter", "meters"),
  lookup("net_meter", "Net meter", "meters"),
  // `AST-B-27` — the sub-meter class was absent from this fixture, so nothing
  // here could reach the tab where allocation is asked for.
  lookup("sub_meter", "Sub-meter", "sub_meters"),
  lookup("backflow", "Backflow preventer", "behind_the_meter"),
  lookup("pv", "PV / solar", "behind_the_meter"),
];

/** BR-AST-003 — a sub-meter cannot exist without an ACTIVE master, and step 1
 *  refuses Continue without one. The picker reads this list, so an empty one
 *  would have parked the allocation cases on step 1 for a reason that has
 *  nothing to do with allocation. */
const MASTERS = [
  {
    id: "m-1",
    asset_no: "W-5001",
    type: "meter",
    behavior_class: "in_service",
  },
];

function paged<T>(results: T[]) {
  return { results, page: 1, per: 200, total: results.length };
}

function seeded(): QueryClient {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(["lookups", "asset_types"], paged(TYPES));
  queryClient.setQueryData(["lookups", "read_methods"], paged([]));
  queryClient.setQueryData(["lookups", "meter_types"], paged([]));
  queryClient.setQueryData(["lookups", "service_size_classes"], paged([]));
  queryClient.setQueryData(queryKeys.tenantServices, SERVICES);
  queryClient.setQueryData(["assets", "add-parent-picker"], paged(MASTERS));
  queryClient.setQueryData(["premises", "asset-add-picker"], paged([]));
  queryClient.setQueryData(["units", "asset-add-picker"], paged([]));
  return queryClient;
}

function Providers(props: { children: ReactNode; path: string; client?: QueryClient }) {
  return (
    <QueryClientProvider client={props.client ?? seeded()}>
      <ToastProvider>
        {/* ⚠ MOUNTED UNDER THE REAL PATH PATTERN. A bare MemoryRouter with no
            `/:tenant/…` route leaves `useParams().tenant` undefined and every
            address the page builds comes out `//assets/…` — a string that reads
            as perfectly good to `toContain` (hard-won law 2). */}
        <MemoryRouter initialEntries={[props.path]}>
          <Routes>
            <Route path="/:tenant/assets/new" element={props.children} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}

function mount(path: string, client?: QueryClient): void {
  render(
    <Providers path={path} client={client}>
      <AssetAddWizard timeZone="America/Chicago" today="2026-09-12" />
    </Providers>,
  );
}

/** Step 1, answered the way a clerk answers it. */
async function answerIdentity(type: string, service: string | null): Promise<void> {
  await userEvent.selectOptions(
    screen.getByLabelText(new RegExp(t("assets.col.assetType"))),
    type,
  );
  if (service !== null) {
    await userEvent.selectOptions(
      screen.getByLabelText(new RegExp(t("assets.form.utilityService"))),
      service,
    );
  }
}

async function continueStep(): Promise<void> {
  await userEvent.click(screen.getByRole("button", { name: t("wizard.continue") }));
}

// ══════════════════════════════════════════════════════════════════════════
describe("DEF-MET-4980 — the utility service is CHOSEN from the tenant's list", () => {
  it("is a select over the ENABLED services, by name, never a text box", () => {
    mount("/brazosbend/assets/new?class=meters");
    const control = screen.getByLabelText(
      new RegExp(t("assets.form.utilityService")),
    ) as HTMLSelectElement;
    // The control shape is the defect: it was `<input type="text">` with
    // `placeholder` null and `list` null — nothing to open, nothing to read.
    expect(control.tagName).toBe("SELECT");
    const options = within(control)
      .getAllByRole("option")
      .map((option) => (option as HTMLOptionElement).value);
    expect(options).toContain("water");
    expect(options).toContain("trash");
    // BR-MET-003 — a service this utility does NOT sell is not offerable.
    expect(options).not.toContain("gas");
    // ⚠ **THE COUNT IS THE ASSERTION THAT CATCHES A HAND-TYPED ARRAY.** The
    // platform carries ELEVEN services and this tenant enables two; a picker
    // showing eleven would be the third hand-typed list in the front end
    // (CLAUDE.md hard-won law 2) and would pass every other check here.
    expect(options.filter((value) => value !== "")).toHaveLength(2);
    // B14 rule 31 — the option a clerk reads is the service's NAME.
    expect(
      within(control)
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toContain("Water");
  });

  it("issues GET /settings/services — the call that was never made", async () => {
    // ⚠ **UNSEEDED ON PURPOSE.** Every other case here hands React Query the
    // answer, which proves the RENDER and says nothing about whether the screen
    // ever asks. The whole defect was that a full four-step walk issued twelve
    // API calls and none of them was this one.
    const asked: string[] = [];
    const client = createApiClient({
      tenant: "brazosbend",
      fetchImpl: async (input) => {
        asked.push(new URL(String(input), "http://localhost").pathname);
        return new Response("[]", { status: 200, headers: { "Content-Type": "application/json" } });
      },
    });
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <ToastProvider>
          <MemoryRouter initialEntries={["/brazosbend/assets/new?class=meters"]}>
            <Routes>
              <Route
                path="/:tenant/assets/new"
                element={<AssetAddWizard client={client} timeZone="America/Chicago" today="2026-09-12" />}
              />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
    await screen.findByLabelText(new RegExp(t("assets.form.utilityService")));
    await new Promise((resolve) => setTimeout(resolve, 60));
    expect(asked.some((path) => path.endsWith("/settings/services"))).toBe(true);
  });
});

// ══════════════════════════════════════════════════════════════════════════
describe("DEF-MET-4981 — the service is marked required, where the server requires it", () => {
  it("a meter cannot leave step 1 without one, and the label says so", async () => {
    mount("/brazosbend/assets/new?class=meters");
    const control = screen.getByLabelText(new RegExp(t("assets.form.utilityService")));
    // BR-SHL-017's marker, and the AT half of it.
    expect(control).toHaveAttribute("aria-required", "true");
    await answerIdentity("meter", null);
    await continueStep();
    // BR-SHL-025's posture — the refusal is AT the button, and the field it is
    // about is on this screen rather than three steps back.
    expect(await screen.findByRole("alert")).toHaveTextContent(t("wizard.blocked"));
    await userEvent.selectOptions(control, "water");
    await continueStep();
    expect(await screen.findByRole("button", { name: t("wizard.back") })).toBeInTheDocument();
  });

  it("a behind-the-meter device needs none — BR-AST-009 asks nothing of it", async () => {
    mount("/brazosbend/assets/new?class=behind_the_meter");
    expect(screen.getByLabelText(new RegExp(t("assets.form.utilityService")))).not.toHaveAttribute(
      "aria-required",
    );
    await answerIdentity("backflow", null);
    await continueStep();
    expect(await screen.findByRole("button", { name: t("wizard.back") })).toBeInTheDocument();
  });
});

// ══════════════════════════════════════════════════════════════════════════
describe("DEF-MET-4983 — a step past the first, over an untouched form, is refused", () => {
  it("lands on step 1 and says the answers were not kept", async () => {
    mount("/brazosbend/assets/new?class=meters&step=3");
    // The sentence first — a silent redirect would be a second defect.
    expect(await screen.findByText(t("assets.add.restarted"))).toBeInTheDocument();
    // And the screen really is step 1: its own controls are here and step 3's
    // destination chooser is not.
    expect(screen.getByLabelText(new RegExp(t("assets.col.assetType")))).toBeInTheDocument();
    expect(screen.queryByLabelText(t("assets.add.assignNow"))).toBeNull();
  });

  it("an out-of-range step is refused the same way, not silently clamped", async () => {
    mount("/brazosbend/assets/new?class=meters&step=9");
    expect(await screen.findByText(t("assets.add.restarted"))).toBeInTheDocument();
  });

  it("arriving at step 1 normally says nothing at all", () => {
    mount("/brazosbend/assets/new?class=meters");
    expect(screen.queryByText(t("assets.add.restarted"))).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **`DEF-MET-4984`'s CASE IS GONE, AND ITS DISAPPEARANCE IS THE POINT.**
// It asserted that the opening read *"is disabled and does not render as an
// ordinary box"* — correct on 2026-09-11 and false on 2026-09-12, when the PO
// ruled *"Build it as drawn - move it to step 2, beside the multiplier,
// register digits and the warning"* (`AST-B-14`). A refusal is a HOLD, and the
// day a hold expires the test that asserts it must go with it or it becomes a
// check defending the defect.
//
// The cases below are what replaces it: the field is on step 2, it is
// editable, and it is NOT on step 3. The last of the three is the one that
// would have caught a lazy fix — un-disabling the control where it stood and
// adding a second one on step 2 passes both of the others.
describe("AST-B-14 — the opening read moved to step 2 and can be typed in", () => {
  const reachSpec = async (): Promise<void> => {
    mount("/brazosbend/assets/new?class=meters");
    await answerIdentity("meter", "water");
    await continueStep();
    await screen.findByLabelText(new RegExp(t("assets.form.uom")));
  };

  it("step 2 offers it as an ordinary editable box, beside the multiplier", async () => {
    await reachSpec();
    const opening = screen.getByLabelText(t("assets.add.openingRead")) as HTMLInputElement;
    const multiplier = screen.getByLabelText(new RegExp(t("assets.form.multiplier"))) as
      HTMLInputElement;
    expect(opening.disabled).toBe(false);
    // The class comparison is the mirror of DEF-MET-4984's: it proved the
    // refusal did NOT look like an ordinary field, and this proves the enabled
    // control DOES — same kit, same variant, no leftover refusal styling.
    expect(opening.className).toBe(multiplier.className);
    expect(opening.className).not.toContain("disabled:opacity-45");
    // And the warning it was moved to sit beside is on the same screen.
    expect(screen.getByText(t("assets.add.multiplierWarning"))).toBeInTheDocument();
    await userEvent.type(opening, "12481");
    expect(opening.value).toBe("12481");
  });

  it("its read date is beside it, and says what a blank one means", async () => {
    await reachSpec();
    expect(screen.getByLabelText(t("assets.add.openingReadDate"))).toBeInTheDocument();
    expect(screen.getByText(t("assets.add.openingReadDateHelp"))).toBeInTheDocument();
  });

  it("the consequence appears only once there is a reading to write", async () => {
    await reachSpec();
    // B14 rule 11 governs a form that writes; an empty box writes nothing, so
    // a box describing the write would be describing nothing.
    expect(document.querySelector('[data-consequence="opening-read"]')).toBeNull();
    await userEvent.type(screen.getByLabelText(t("assets.add.openingRead")), "12481");
    const box = document.querySelector('[data-consequence="opening-read"]');
    expect(box).not.toBeNull();
    // The failure rule is the half a clerk needs before the commit.
    expect(box?.textContent).toContain(t("assets.add.openingReadConsequenceBody"));
  });

  it("step 3 no longer carries it at all — DELETED, not un-disabled", async () => {
    await reachSpec();
    await userEvent.type(screen.getByLabelText(new RegExp(t("assets.form.uom"))), "kgal");
    await continueStep();
    // We really are on step 3: its own field is here.
    expect(screen.getByLabelText(t("assets.form.installDate"))).toBeInTheDocument();
    expect(screen.queryByLabelText(t("assets.add.openingRead"))).toBeNull();
  });

  it("a behind-the-meter device is not asked for one — it has no register", async () => {
    mount("/brazosbend/assets/new?class=behind_the_meter");
    await answerIdentity("backflow", null);
    await continueStep();
    await screen.findByRole("button", { name: t("wizard.back") });
    expect(screen.queryByLabelText(t("assets.add.openingRead"))).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
describe("AST-B-27 — a sub-meter is asked how its usage is shared", () => {
  it("the share and the method are on step 2, and the method is a chooser", async () => {
    mount("/brazosbend/assets/new?class=sub_meters");
    await answerIdentity("sub_meter", "water");
    // BR-AST-003 — the parent picker is a `SearchSelectField` combobox, not a
    // native select, so it is TYPED INTO and an option is CLICKED. It opens on
    // typing (`open` is set in `onChange`), and one character leaves the
    // debouncer's committed query empty, so the whole list shows.
    await userEvent.type(
      screen.getByRole("combobox", { name: new RegExp(t("assets.add.parent")) }),
      "W",
    );
    await userEvent.click(await screen.findByRole("option", { name: /W-5001/ }));
    await continueStep();
    await screen.findByRole("button", { name: t("wizard.back") });
    await screen.findByLabelText(new RegExp(t("assets.form.uom")));
    expect(screen.getByLabelText(t("assets.spec.allocationShare"))).toBeInTheDocument();
    const rule = screen.getByLabelText(t("assets.spec.allocationRule")) as HTMLSelectElement;
    // B14 rule 31 — the CODE is never the visible value. The four ratified
    // words are what a clerk reads; `rubs` is what is stored.
    const labels = Array.from(rule.options).map((option) => option.textContent);
    expect(labels).toContain(t("assets.allocationRule.rubs"));
    expect(labels).toContain(t("assets.allocationRule.absorb"));
    expect(labels).not.toContain("rubs");
    // Rule 8's searchable half aside, a fifth value cannot be typed in.
    expect(rule.tagName).toBe("SELECT");
  });

  it("a plain meter is not asked — it measures the whole building", async () => {
    mount("/brazosbend/assets/new?class=meters");
    await answerIdentity("meter", "water");
    await continueStep();
    await screen.findByLabelText(new RegExp(t("assets.form.uom")));
    expect(screen.queryByLabelText(t("assets.spec.allocationShare"))).toBeNull();
    expect(screen.queryByLabelText(t("assets.spec.allocationRule"))).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
describe("DEF-MET-4985 — a device step's sentences are true of the device on it", () => {
  const helpersFor = async (type: string): Promise<string[]> => {
    mount("/brazosbend/assets/new?class=behind_the_meter");
    await answerIdentity(type, null);
    await continueStep();
    await screen.findByRole("button", { name: t("wizard.back") });
    return [
      screen.getByText(t("assets.add.linkedMeterHelp")).textContent ?? "",
      screen.getByText(t("assets.add.exportCapacityHelp")).textContent ?? "",
    ];
  };

  it("a backflow preventer is not told about inverters and batteries", async () => {
    const helpers = await helpersFor("backflow");
    for (const sentence of helpers) {
      // The two sentences named a device the person was not adding: *"A
      // capacity, in kW — inverters and batteries only."* over a form offering
      // the field, and *"An exporting inverter links to the net meter that
      // measures its export."* on a control offered to all ten device types.
      expect(sentence).not.toMatch(/inverter|batter/i);
    }
  });

  it("and a PV inverter reads exactly the same sentences", async () => {
    const backflow = await helpersFor("backflow");
    cleanup();
    const pv = await helpersFor("pv");
    // One string per field, true everywhere, is what the blueprint's own
    // drawing chose (PDF page 115) — two strings would be two to keep true.
    expect(pv).toEqual(backflow);
  });
});

// ══════════════════════════════════════════════════════════════════════════
describe("DEF-MET-4986 — the screen says the service is not kept in inventory", () => {
  async function reachAssignment(): Promise<void> {
    mount("/brazosbend/assets/new?class=meters");
    await answerIdentity("meter", "water");
    await continueStep();
    await userEvent.type(screen.getByLabelText(new RegExp(t("assets.form.uom"))), "kgal");
    await continueStep();
    // ⚠ **THE MARKER USED TO BE THE OPENING READ, AND `AST-B-14` MOVED IT TO
    // STEP 2.** A test that waits for a control which has moved UPSTREAM does
    // not fail loudly — it resolves instantly on the previous screen and every
    // assertion after it runs against the wrong step. This one waits for a
    // field that only step 3 has.
    await screen.findByLabelText(t("assets.form.installDate"));
  }

  it("the default destination carries the consequence, naming the service", async () => {
    await reachAssignment();
    const box = document.querySelector('[data-consequence="assets-add-service-dropped"]');
    expect(box).not.toBeNull();
    // The service by NAME, so the sentence is about something the clerk chose.
    expect(box?.textContent).toContain("Water");
    expect(box?.textContent).toContain(t("assets.add.serviceDroppedBody"));
  });

  it("assigning it to a unit does not — there is nothing to warn about", async () => {
    await reachAssignment();
    await userEvent.click(screen.getByRole("radio", { name: t("assets.add.assignToUnit") }));
    expect(document.querySelector('[data-consequence="assets-add-service-dropped"]')).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
/**
 * ⚠ **THE SUMMARY WAS ON STEP 4 UNTIL 2026-09-13 AND IT IS ON STEP 5 NOW.**
 * Screen 32 of `05-prototype/01 Assets Menu Blueprint.pdf` — *Add an asset · 5
 * Review & add*, `NEW BUILD`, figure 49 on page 120, read as an image per B14
 * rule 42 — draws a FIVE-box rail (`1 Identity › 2 Specification ›
 * 3 Assignment › 4 Lifecycle › 5 Review`) with the Identity and Measurement
 * summary panels on the fifth. `data-add-summary` moved onto the review panel
 * with it, so three presses of Continue now land on Lifecycle, where the hook
 * does not exist. One more press is the whole fix; the RULE this case asserts —
 * B14 rule 31, a lookup code is never a visible value — is untouched.
 */
describe("DEF-MET-4990 — the step-5 review summary shows words, not lookup codes", () => {
  it("reads *Meter · Water*, never *meter · water*", async () => {
    mount("/brazosbend/assets/new?class=meters");
    await answerIdentity("meter", "water");
    await continueStep();
    await userEvent.type(screen.getByLabelText(new RegExp(t("assets.form.uom"))), "kgal");
    await continueStep();
    await continueStep();
    await continueStep(); // 4 Lifecycle → 5 Review (screen 32, figure 49)
    const summary = document.querySelector("[data-add-summary]");
    expect(summary).not.toBeNull();
    // B14 rule 31 — a lookup code is an internal reference and is never the
    // visible value of a field. The summary read them straight off the form.
    expect(summary?.textContent).toContain("Meter");
    expect(summary?.textContent).toContain("Water");
    expect(summary?.textContent).not.toContain("net_meter");
  });
});

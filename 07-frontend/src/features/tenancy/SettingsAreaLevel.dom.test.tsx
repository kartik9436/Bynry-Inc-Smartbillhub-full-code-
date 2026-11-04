// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Defect: DEF-TEN-4478 — Settings → Reference data → Areas & sub-areas. The PO
//         opened the Add dialog on a live tenant and said, verbatim: *"on add
//         screen there is not differnt whether Im addding area or sub areas"*.
//         Screens: S8 / r10 SET-04.areas
// Rules:  BR-MET-066b (two levels, depth enforced on the SERVER) ·
//         BR-TEN-030/031 · B14 rule 32 (a screen's description budget — this
//         dialog ends with LESS prose than it had) · B14 rule 8 (selects) ·
//         B14 rule 31 (no database id on screen)
// Note:   Written BEFORE the fix and shown RED — hard-won law 7, and shown red
//         through `vitest run`, the harness that will run it, never through a
//         hand-rolled entry point (DEF-GOV-3733).
// ───────────────────────────────────────────────────────
// ⚠ **WHY A DOM TEST AND NOT A MARKUP ASSERTION.** The defect is entirely
// inside a modal, and the modal opens on a click; `SettingsReferenceData.test.tsx`
// renders to static markup and can never reach it. That is also the honest
// answer to this defect's `escape_reason`: the capability was tested, the
// legibility of the capability was not, and no check in this repo reads
// rendered output.
//
// The load-bearing assertions are the two that read the WIRE. A chooser that
// changes a title and changes nothing else would satisfy every visible
// assertion here and still create the wrong row.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import type { LookupEntry } from "@/api/endpoints";
import { ToastProvider } from "@/components/Toast";

import { ReferenceDataTab, entryIsSubLevel } from "./SettingsReferenceData";
import { referenceCard } from "./referenceDataConfig";

const TEST_TENANT = "silver-creek-water1";

interface Sent {
  method: string;
  url: string;
  body: Record<string, unknown> | null;
}

/** The four seeded districts plus one sub-area, exactly as the areas handler
 *  serializes them (`is_sub_area`, `parent_code`, `parent_name`,
 *  `sub_area_count` — apps/tenancy/services.py). */
const AREA_ROWS: LookupEntry[] = [
  {
    id: "ar-north",
    code: "NORTH",
    name: "North district",
    active: true,
    is_system: true,
    used_by: 0,
    is_sub_area: false,
    parent_code: null,
    parent_name: null,
    sub_area_count: 0,
  },
  {
    id: "ar-dtwn",
    code: "DTWN",
    name: "Downtown",
    active: true,
    is_system: true,
    used_by: 0,
    is_sub_area: false,
    parent_code: null,
    parent_name: null,
    sub_area_count: 1,
  },
  {
    id: "ar-dtwn-ne",
    code: "DTWN-NE",
    name: "Downtown NE",
    active: true,
    is_system: false,
    used_by: 0,
    is_sub_area: true,
    parent_code: "DTWN",
    parent_name: "Downtown",
    sub_area_count: 0,
  },
];

/** Account sub-types — the OTHER tree through this same dialog (CR-010,
 *  `parentList`). Its parent is REQUIRED by the server, so it must NOT grow a
 *  two-way chooser: there is no second answer to choose. */
const TYPE_ROWS: LookupEntry[] = [
  { id: "at-res", code: "RES", name: "Residential", active: true, is_system: true, used_by: 0 },
  { id: "at-com", code: "COM", name: "Commercial", active: true, is_system: true, used_by: 0 },
];

function recordingClient(sent: Sent[], rows: LookupEntry[], parents: LookupEntry[] = rows) {
  return createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (method !== "GET") {
        sent.push({
          method,
          url,
          body:
            init?.body === undefined || init?.body === null
              ? null
              : (JSON.parse(String(init.body)) as Record<string, unknown>),
        });
        return new Response(JSON.stringify(rows[0]), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      if (url.includes("/fixture-gap")) {
        return new Response(JSON.stringify({ missing: [] }), {
          status: 200,
          headers: { "content-type": "application/json" },
        });
      }
      // The parent picker fetches its own unpaged list (`per=200`).
      const body = url.includes("per=200") ? parents : rows;
      return new Response(
        JSON.stringify({ count: body.length, next: null, previous: null, results: body }),
        { status: 200, headers: { "content-type": "application/json" } },
      );
    },
  });
}

function renderList(list: string, sent: Sent[], rows: LookupEntry[], parents?: LookupEntry[]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/settings/reference-data?list=${list}`]}>
        <ToastProvider>
          <ReferenceDataTab
            readOnly={false}
            client={recordingClient(sent, rows, parents ?? rows)}
          />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function openAdd(): Promise<HTMLElement> {
  await userEvent.click(await screen.findByRole("button", { name: /Add entry/i }));
  return screen.findByRole("dialog");
}

afterEach(cleanup);

describe("DEF-TEN-4478 — the Add dialog says which of the two it is making", () => {
  it("opens on Area, and says so in a CONTROL and in the TITLE, not in helper text", async () => {
    renderList("areas", [], AREA_ROWS);
    const form = await openAdd();

    // The control. A radio group is the shape that promises one-of-two.
    const chooser = within(form).getByRole("radiogroup", { name: "Area or sub-area" });
    expect(within(chooser).getByRole("radio", { name: "Area" })).toBeChecked();
    expect(within(chooser).getByRole("radio", { name: "Sub-area" })).not.toBeChecked();

    // The title FOLLOWS it. "Add to Areas & sub-areas" was true of both halves
    // and is the sentence the PO could not tell apart.
    expect(within(form).getByRole("heading", { name: "Add an area" })).toBeInTheDocument();
    expect(form.textContent).not.toContain("Add to Areas & sub-areas");

    // B14 rule 32 — the dialog ends with LESS prose. The sentence that used to
    // carry the whole distinction is gone, and so is the picker it explained.
    expect(form.textContent).not.toContain("Leave blank for an area");
    expect(within(form).queryByLabelText("Parent area")).not.toBeInTheDocument();

    // ORDER, and it is not decoration: the chooser decides what the dialog is,
    // so it comes before the fields that belong to that decision. Found by
    // looking at a screenshot of the running app — the first cut put it third,
    // under Code and Name, where a person types the code before deciding what
    // they are typing it for (hard-won law 6).
    const chooserFirst = chooser.compareDocumentPosition(within(form).getByLabelText(/^Code/));
    expect(chooserFirst & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("choosing Sub-area moves the title and reveals the parent picker", async () => {
    renderList("areas", [], AREA_ROWS);
    const form = await openAdd();
    await userEvent.click(within(form).getByRole("radio", { name: "Sub-area" }));

    expect(within(form).getByRole("heading", { name: "Add a sub-area" })).toBeInTheDocument();
    const picker = within(form).getByLabelText(/^Parent area/);
    expect(picker).toBeInTheDocument();
    // Only top-level rows are offered — the sub-area in the fixture is not a
    // legal parent and the server would refuse it by name.
    expect(Array.from(picker.querySelectorAll("option")).map((o) => o.textContent)).toEqual([
      "Select the parent area",
      "North district",
      "Downtown",
    ]);
    // B14 rule 31 — the option values are CODES, never row ids.
    expect(form.textContent).not.toContain("ar-dtwn");
  });

  it("a sub-area with no parent picked is REFUSED here, not turned into an area", async () => {
    // The one client-side rule this fix adds, and it is not a copy of the
    // server's depth rule: blank is a LEGAL write that makes the other thing,
    // so without this the screen would promise a sub-area and make an area.
    const sent: Sent[] = [];
    renderList("areas", sent, AREA_ROWS);
    const form = await openAdd();
    await userEvent.click(within(form).getByRole("radio", { name: "Sub-area" }));
    await userEvent.type(within(form).getByLabelText(/^Code/), "DTWN-SW");
    await userEvent.type(within(form).getByLabelText(/^Name/), "Downtown SW");
    await userEvent.click(within(form).getByRole("button", { name: "Add entry" }));

    expect(await within(form).findByText("Pick the area it sits under.")).toBeInTheDocument();
    expect(sent).toHaveLength(0);
  });

  it("Area SENDS an empty parent even after a parent was picked and unpicked", async () => {
    // The wire assertion. A chooser that only moved a title would pass every
    // visible assertion above and still post the picker's stale value.
    const sent: Sent[] = [];
    renderList("areas", sent, AREA_ROWS);
    const form = await openAdd();
    await userEvent.click(within(form).getByRole("radio", { name: "Sub-area" }));
    await userEvent.selectOptions(within(form).getByLabelText(/^Parent area/), "DTWN");
    await userEvent.click(within(form).getByRole("radio", { name: "Area" }));
    await userEvent.type(within(form).getByLabelText(/^Code/), "WEST");
    await userEvent.type(within(form).getByLabelText(/^Name/), "West district");
    await userEvent.click(within(form).getByRole("button", { name: "Add entry" }));

    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent[0].method).toBe("POST");
    expect(sent[0].body).toMatchObject({ code: "WEST", name: "West district", parent_code: "" });
  });

  it("Sub-area SENDS the parent it names", async () => {
    const sent: Sent[] = [];
    renderList("areas", sent, AREA_ROWS);
    const form = await openAdd();
    await userEvent.click(within(form).getByRole("radio", { name: "Sub-area" }));
    await userEvent.type(within(form).getByLabelText(/^Code/), "DTWN-SW");
    await userEvent.type(within(form).getByLabelText(/^Name/), "Downtown SW");
    await userEvent.selectOptions(within(form).getByLabelText(/^Parent area/), "DTWN");
    await userEvent.click(within(form).getByRole("button", { name: "Add entry" }));

    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent[0].body).toMatchObject({ code: "DTWN-SW", parent_code: "DTWN" });
  });

  it("editing a SUB-AREA opens on Sub-area, with its parent already named", async () => {
    renderList("areas", [], AREA_ROWS);
    await screen.findByText("Downtown NE");
    // The row's own Edit action — the third row is the sub-area.
    const row = screen.getByText("Downtown NE").closest("tr");
    expect(row).not.toBeNull();
    await userEvent.click(within(row as HTMLElement).getByRole("button", { name: /Edit/i }));
    const form = await screen.findByRole("dialog");

    expect(within(form).getByRole("radio", { name: "Sub-area" })).toBeChecked();
    expect(within(form).getByRole("heading", { name: "Edit a sub-area" })).toBeInTheDocument();
    await waitFor(() =>
      expect(within(form).getByLabelText(/^Parent area/)).toHaveValue("DTWN"),
    );
  });

  it("on a tenant with NO areas yet, choosing Sub-area says why it cannot be done", async () => {
    // The FIRST-RUN state, and the one the chooser makes reachable in a way it
    // was not before: a person can now ask for a sub-area on a list that has no
    // possible parent. A required picker with nothing in it and no explanation
    // is a dead end; the sentence naming what to do first is the whole answer,
    // and it is the ONE case where this dialog still earns a line of prose.
    renderList("areas", [], []);
    const form = await openAdd();
    await userEvent.click(within(form).getByRole("radio", { name: "Sub-area" }));
    const picker = within(form).getByLabelText(/^Parent area/);
    // Only the placeholder — `parentOptionsFor` had nothing to offer.
    expect(picker.querySelectorAll("option")).toHaveLength(1);
    expect(form.textContent).toContain("There is no top-level area to sit under yet.");
  });

  it("editing a top-level AREA opens on Area, with no picker to leave blank", async () => {
    renderList("areas", [], AREA_ROWS);
    await screen.findByText("North district");
    const row = screen.getByText("North district").closest("tr");
    await userEvent.click(within(row as HTMLElement).getByRole("button", { name: /Edit/i }));
    const form = await screen.findByRole("dialog");

    expect(within(form).getByRole("radio", { name: "Area" })).toBeChecked();
    expect(within(form).getByRole("heading", { name: "Edit an area" })).toBeInTheDocument();
    expect(within(form).queryByLabelText("Parent area")).not.toBeInTheDocument();
  });
});

describe("DEF-TEN-4478 — a value nobody chose can no longer change what gets made", () => {
  it("a parent set on the ELEMENT, with no React change event, does not reach the wire", async () => {
    // What the PO's screenshot showed: the picker reading *Downtown* while the
    // sentence above it said leave it blank for an area. A browser fill writes
    // the DOM and fires no React onChange, so the control and the state
    // disagree — and before this fix the disagreement was invisible and the
    // SILENT half won. Now the chooser is what decides, so the worst a stray
    // value can do is nothing.
    const sent: Sent[] = [];
    renderList("areas", sent, AREA_ROWS);
    const form = await openAdd();
    await userEvent.click(within(form).getByRole("radio", { name: "Sub-area" }));
    const picker = within(form).getByLabelText(/^Parent area/) as HTMLSelectElement;
    picker.value = "DTWN"; // the fill: DOM only, no event
    await userEvent.click(within(form).getByRole("radio", { name: "Area" }));
    await userEvent.type(within(form).getByLabelText(/^Code/), "SOUTH");
    await userEvent.type(within(form).getByLabelText(/^Name/), "South district");
    await userEvent.click(within(form).getByRole("button", { name: "Add entry" }));

    await waitFor(() => expect(sent.length).toBeGreaterThan(0));
    expect(sent[0].body).toMatchObject({ parent_code: "" });
  });

  it("the code and name inputs refuse browser fill by name", async () => {
    renderList("areas", [], AREA_ROWS);
    const form = await openAdd();
    expect(within(form).getByLabelText(/^Code/)).toHaveAttribute("autocomplete", "off");
    expect(within(form).getByLabelText(/^Name/)).toHaveAttribute("autocomplete", "off");
  });
});

describe("DEF-TEN-4478 — the OTHER tree through this dialog is untouched", () => {
  it("account sub-types get NO chooser: their parent is required, so there is no choice", async () => {
    renderList("account_subtypes", [], TYPE_ROWS);
    const form = await openAdd();
    expect(within(form).queryByRole("radiogroup")).not.toBeInTheDocument();
    // Its own words, its own always-visible picker, its own title.
    expect(within(form).getByLabelText(/^Account type/)).toBeInTheDocument();
    expect(form.textContent).toContain("Add to Account sub-types");
  });

  it("declares its levels on the card, so the words are never the view's", () => {
    const areas = referenceCard("areas");
    expect(areas?.hierarchical?.topKey).toBe("settings.reference.level.area");
    expect(areas?.hierarchical?.subKey).toBe("settings.reference.level.subArea");
    // The cross-list card declares none — that is what says "no chooser here".
    expect(referenceCard("account_subtypes")?.hierarchical).toBeUndefined();
  });

  it("reads the level off the row the server sent, not off a guess", () => {
    expect(entryIsSubLevel(null)).toBe(false);
    expect(entryIsSubLevel(AREA_ROWS[1])).toBe(false);
    expect(entryIsSubLevel(AREA_ROWS[2])).toBe(true);
    // A payload that carried the code and not the flag is still a sub-area.
    expect(entryIsSubLevel({ ...AREA_ROWS[0], is_sub_area: undefined, parent_code: "DTWN" })).toBe(
      true,
    );
  });
});

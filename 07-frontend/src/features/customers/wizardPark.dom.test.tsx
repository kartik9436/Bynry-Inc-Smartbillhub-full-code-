// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-035 — **Park actually works.** PO 2026-08-26, verbatim:
//          *"Park to actually work on the wizards - it should work ; in
//          pratcicail life all these request does not close in  day, hence user
//          genrllay park them"*.
// Rules:   BR-SHL-048 (PO verbatim: *"Option A - Unitl move in executed, no
//          records updates."*) — (a) no foreign key, (b) RE-VALIDATED at
//          execution and never trusted from the park, (c) a parked wizard holds
//          nothing · BR-SHL-047 (every wizard parks) · BR-SHL-046 (ONE declared
//          step list drives the bar and where a resume lands) · BR-SHL-018 (a
//          step is unlocked by Continue, never by arriving) · BR-SHL-025 ·
//          B19 §12.2 (`Save & exit` and `Park` are TWO controls) ·
//          hard-won law 2 (a prop nothing acts on is dead UI)
// ───────────────────────────────────────────────────────
//
// ⚠ **EVERY ASSERTION HERE IS ABOUT RENDERED OUTPUT OR ABOUT AN HTTP REQUEST
// THAT REALLY LEFT, AND THAT IS THE POINT OF THE FILE.** This whole feature is
// one prop away from being dead: `wizardParkPort()` could return an object that
// nothing calls, `onPark` could be threaded to a control that never fires it,
// and a suite written against the port's return value would be green over a
// screen where nothing happens. So:
//
//   · "the button acts" is read off the DOM (`data-wizard="park-blocked"` is
//     absent and the `Park` control is not `disabled`), never off
//     `wizardParkPort() !== null`;
//   · "parking works" is read off the fake transport's request log — the method,
//     the path and the BODY the server would receive;
//   · "resume works" is read off the rendered form fields and the rendered step
//     rail, never off the hook's return value.
//
// The three superseded assertions this file replaces asserted the opposite and
// were correct when written: `MoveInWizard.test.tsx` and `MoveOutWizard.test.tsx`
// each asserted `wizardParkPort()).toBeNull()` and a visible *"Parking is not
// available here yet"*. Both are updated in place rather than deleted, because
// the sentence they guard — a control that cannot act says why — is still the
// rule; only the fact changed.
import "@/i18n";
import "@testing-library/jest-dom/vitest";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import { createApiClient } from "@/api/client";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { DisconnectWizard } from "./DisconnectWizard";
import { MoveInWizard } from "./MoveInWizard";
import { MoveOutWizard } from "./MoveOutWizard";
import { NewConnectWizard } from "./NewConnectWizard";
import { TransferWizard } from "./TransferWizard";
import { ACCOUNTS_PERMISSION } from "./customersShared";
import { MOVE_IN_WIZARD_ROUTE, MOVE_OUT_WIZARD_ROUTE } from "./moveShared";
import { NEW_CONNECT_ROUTE } from "./newConnectShared";
import { DISCONNECT_WIZARD_ROUTE, TRANSFER_WIZARD_ROUTE } from "./transferDisconnectShared";
import { PARKED_PARAM, clampToSteps, hydrateForm, parkedString, parkedStringList } from "./wizardPark";
import type { WizardParkRow } from "./wizardParkEndpoints";

afterEach(cleanup);

const TEST_TENANT = "brazosbend";

// ── The server, as it really answers ───────────────────────────────────────

interface Call {
  method: string;
  url: string;
  body: unknown;
}

function json(body: unknown, status = 200): Response {
  return new Response(body === null ? "" : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** The parked draft the resume cases read back. BR-SHL-048's own worked case:
 *  a move-in for **Unit 12, 500 Main St**, parked on a **$150 deposit**. */
function draft(over: Partial<WizardParkRow> = {}): WizardParkRow {
  return {
    id: "park-1",
    flow: "move_in",
    subject_label: "500 Main St · Unit 12",
    subject_ref: { unit_id: "u-12", account_id: null },
    step: 3,
    values: {
      unit_id: "u-12",
      opened_at: "2026-09-02",
      customer: { full_name: "Okafor, Joy", email: "joy@example.test" },
      preferences: { autopay: true },
    },
    waiting_on: "deposit",
    park_note: "Waiting on the $150 deposit.",
    remind_on: "2026-09-02",
    parked_at: "2026-08-26T09:00:00Z",
    parked_by: "user-1",
    parked_by_name: "A. Clerk",
    age_days: 7,
    // `CR-122-BRC06` — the draft's own `MVI-` reference (image 47's title).
    reference: "MVI-26-0011",
    ...over,
  };
}

function permissions() {
  return {
    role: "billing_clerk",
    role_name: "Billing Clerk",
    permissions: [{ code: ACCOUNTS_PERMISSION, label: "Premises / Accounts", access: "Full" }],
  };
}

const UNIT = {
  id: "u-12",
  unit_no: "Unit 12",
  premises_id: "p-1",
  premise_no: "P-1",
  premise_address: "500 Main St",
  label: "Unit 12",
  unit_type: "residential",
  floor_label: null,
  square_feet: null,
  rate_plan_id: null,
  plan_effective_from: null,
  plan_locked: false,
  vacant_standby_auto: false,
  is_common_area: false,
  active: true,
  services: ["electric"],
  meters: [],
  occupancy: "vacant",
  occupant: null,
  account_no: null,
  status: "vacant",
  sub_metered: false,
};

/** Everything these five screens ask for, answered plainly. Anything not named
 *  answers an empty page rather than a 404, so a screen that grew a read does
 *  not fail this file for the wrong reason. */
function answer(url: string, method: string): Response {
  const path = url.split("?")[0];
  if (path.endsWith("/me/permissions")) {
    return json(permissions());
  }
  if (path.endsWith("/wizard-parks") && method === "POST") {
    return json(draft(), 201);
  }
  if (path.endsWith("/wizard-parks")) {
    return json({ count: 1, next: null, previous: null, results: [draft()] });
  }
  if (path.includes("/wizard-parks/")) {
    return method === "DELETE" ? json(null, 204) : json(draft());
  }
  // `DEF-CUS-10190` — step 1's unit search, in its own shape (it ends in
  // `/units` too, so it is answered first).
  if (path.endsWith("/move-ins/units")) {
    return json({ count: 1, next: null, previous: null, results: [
      { id: UNIT.id, unit_no: UNIT.unit_no, label: UNIT.label, premise_no: UNIT.premise_no, premise_name: null,
        address: { line1: UNIT.premise_address, city: null, state: null, postal_code: null }, meters: [],
        state: "vacant", occupant: null, selectable: true, path: "move_in", reason_key: null },
    ] });
  }
  if (path.endsWith("/units")) {
    return json({ count: 1, next: null, previous: null, results: [UNIT] });
  }
  // `DEF-CUS-6353` — a unit with no finished tenancy is now a FIRST OCCUPANT
  // and opens the move-in's real steps, so step 3 reads the unit's inventory.
  // Answered in its real shape: the empty-page fallback below is not one, and
  // the inventory panel reads `unit.id` off it.
  if (path.endsWith(`/units/${UNIT.id}/assets`)) {
    return json({
      unit: {
        id: UNIT.id,
        unit_no: UNIT.unit_no,
        label: UNIT.label,
        premises_id: UNIT.premises_id,
        premise_no: UNIT.premise_no,
        premise_address: UNIT.premise_address,
      },
      groups: [],
      counts: {},
      reading_expected: { served: false, reason: "", tracks: null },
    });
  }
  return json({ count: 0, next: null, previous: null, results: [] });
}

function mount(
  which: "move_in" | "move_out" | "transfer" | "disconnect" | "new_connect",
  search = "",
): { calls: Call[] } {
  const calls: Call[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input, init) => {
      const method = (init?.method ?? "GET").toUpperCase();
      const raw = init?.body;
      calls.push({
        method,
        url: String(input),
        body: typeof raw === "string" ? JSON.parse(raw) : null,
      });
      return answer(String(input), method);
    },
  });
  const route = {
    move_in: MOVE_IN_WIZARD_ROUTE,
    move_out: MOVE_OUT_WIZARD_ROUTE,
    transfer: TRANSFER_WIZARD_ROUTE,
    disconnect: DISCONNECT_WIZARD_ROUTE,
    new_connect: NEW_CONNECT_ROUTE,
  }[which];
  const element = {
    move_in: <MoveInWizard client={client} />,
    move_out: <MoveOutWizard client={client} />,
    transfer: <TransferWizard client={client} />,
    disconnect: <DisconnectWizard client={client} />,
    new_connect: <NewConnectWizard client={client} />,
  }[which];
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.myPermissions, permissions());
  render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[`/${TEST_TENANT}${route}${search}`]}>
          <Routes>
            <Route path={`/:tenant${route}`} element={element} />
            {/* Where a successful park lands. Rendered so the navigation is
                OBSERVABLE rather than asserted through a router spy — a park
                that "succeeded" and left the clerk on the wizard is the defect
                this case exists to catch. */}
            <Route path="/:tenant/accounts" element={<p>ACCOUNTS SCREEN</p>} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { calls };
}

const FLOWS = ["move_in", "move_out", "transfer", "disconnect", "new_connect"] as const;

// ══════════════════════════════════════════════════════════════════════════
// 1 · THE SWITCH — five disabled buttons, ON RENDERED OUTPUT
// ══════════════════════════════════════════════════════════════════════════

describe("CR-035 · the port — `Park` acts on all five wizards", () => {
  for (const flow of FLOWS) {
    it(`${flow}: the Park control is ENABLED and carries NO blocked reason`, async () => {
      mount(flow);
      const park = await screen.findByRole("button", { name: "Park" });
      // hard-won law 2 read the other way round: the assertion is that the
      // control the clerk can press is not disabled, NOT that a port exists.
      expect(park).toBeEnabled();
      // BR-SHL-025's disabled-with-reason wrapper is GONE, and with it the
      // sentence DEF-731 rewrote. A grep-level check would have missed this:
      // the wrapper renders only when a reason exists.
      expect(document.body.querySelector('[data-wizard="park-blocked"]')).toBeNull();
      expect(document.body.textContent).not.toContain("Parking is not available here yet");
    });

    /**
     * ⚠ **B19 §12.2 STILL HOLDS FOR FOUR FLOWS AND IS SUPERSEDED FOR THE
     * FIFTH — `CR-125-BRC07`, PO ruling 2026-09-21.**
     *
     * Verbatim: *"we need to keep only park, complete - two action only"*,
     * confirmed *"this si correct"*. On the DISCONNECT wizard `Save & exit`
     * MERGED INTO Park — they were two names for one act — so this case asks a
     * different question there and the same question everywhere else.
     *
     * The flow is named rather than the case being skipped, so that the day a
     * sixth wizard arrives it lands in the four-flow branch and has to be
     * argued out of it, instead of quietly inheriting an exemption.
     */
    it(`${flow}: B19 §12.2 — the exit controls are the ones this flow is ruled to have`, async () => {
      mount(flow);
      const park = await screen.findByRole("button", { name: "Park" });
      expect(park).toBeEnabled();
      if (flow === "disconnect") {
        expect(screen.queryByRole("button", { name: "Save & exit" })).toBeNull();
      } else if (flow === "move_in") {
        // `CR-171-BRC10` P2.17 (image 30) — the move-in's leave control is the
        // page head's *Save draft & exit*, and the frame draws none of its own.
        expect(screen.queryByRole("button", { name: "Save & exit" })).toBeNull();
        expect(screen.getByRole("button", { name: "Save draft & exit" })).toBeEnabled();
      } else {
        expect(screen.getByRole("button", { name: "Save & exit" })).toBeEnabled();
      }
    });
  }
});

// ══════════════════════════════════════════════════════════════════════════
// 2 · PARKING — the panel opens, and what leaves is what the contract says
// ══════════════════════════════════════════════════════════════════════════

describe("CR-035 · parking a transfer writes ONE draft and nothing else", () => {
  it("POSTs the flow, the step, the reason, the note and the reminder — and lands the clerk on the list", async () => {
    const user = userEvent.setup();
    const { calls } = mount("transfer");

    await user.click(await screen.findByRole("button", { name: "Park" }));

    // The panel is `?park=1` URL state, so it renders after the click.
    const reason = await screen.findByLabelText(/Waiting on/);
    await user.selectOptions(reason, "deposit");
    await user.type(screen.getByLabelText(/Note/), "Deposit promised Friday");
    await user.click(screen.getByRole("button", { name: "Park it" }));

    await waitFor(() => {
      expect(calls.some((call) => call.method === "POST")).toBe(true);
    });
    const post = calls.find((call) => call.method === "POST");
    expect(post?.url).toContain(`/api/${TEST_TENANT}/wizard-parks`);
    // ⚠ THE BODY IS THE CONTRACT, FIELD BY FIELD. A park that posted the right
    // path with the wrong shape is the defect a URL-only assertion misses.
    expect(post?.body).toMatchObject({
      flow: "transfer",
      step: 1,
      waiting_on: "deposit",
      park_note: "Deposit promised Friday",
    });
    const body = post?.body as Record<string, unknown>;
    // ⚠ **`subject_ref` IS AN OBJECT, WHICH IS THE CORRECTION THAT MATTERS
    // MOST IN THIS FILE.** `wizard_parks._clean_json_object` refuses a bare
    // string with `VAL-002`, so a client that sent one would 422 EVERY park
    // while the button, the panel and every DOM assertion above stayed green.
    // Asserting the shape of what LEAVES is the only check that can see it.
    expect(typeof body.subject_ref).toBe("object");
    expect(body.subject_ref).not.toBeNull();
    // BR-SHL-048 (a) — COPIED ids only, and nothing at the top level of the
    // body names a relationship: no `account`, no `unit`, no `premise`.
    expect(Object.keys(body).sort()).toEqual(
      ["flow", "park_note", "step", "subject_label", "subject_ref", "values", "waiting_on"].sort(),
    );
    // An empty reminder is OMITTED on a create, never sent as `""` for
    // `_clean_remind_on` to parse.
    expect(Object.keys(body)).not.toContain("remind_on");

    // The clerk ends up where their parked work now is — a park that succeeded
    // silently and left them on the wizard is indistinguishable from one that
    // did nothing.
    expect(await screen.findByText("ACCOUNTS SCREEN")).toBeInTheDocument();
  });

  it("a park that FAILS keeps every answer on screen and says so — nothing is lost", async () => {
    const user = userEvent.setup();
    const calls: Call[] = [];
    const client = createApiClient({
      tenant: TEST_TENANT,
      fetchImpl: async (input, init) => {
        const method = (init?.method ?? "GET").toUpperCase();
        calls.push({ method, url: String(input), body: null });
        if (method === "POST") {
          return json({ code: null, message_key: "api.error.unexpected" }, 500);
        }
        return answer(String(input), method);
      },
    });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[`/${TEST_TENANT}${TRANSFER_WIZARD_ROUTE}`]}>
            <Routes>
              <Route
                path={`/:tenant${TRANSFER_WIZARD_ROUTE}`}
                element={<TransferWizard client={client} />}
              />
              <Route path="/:tenant/accounts" element={<p>ACCOUNTS SCREEN</p>} />
            </Routes>
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );

    await user.click(await screen.findByRole("button", { name: "Park" }));
    await user.selectOptions(await screen.findByLabelText(/Waiting on/), "permit");
    await user.type(screen.getByLabelText(/Note/), "Inspector booked");
    await user.click(screen.getByRole("button", { name: "Park it" }));

    // BR-SHL-020 — plain language, and it says the work is still there. The
    // clerk must NOT be navigated away from a park that did not happen.
    expect(await screen.findByText(/could not be parked/i)).toBeInTheDocument();
    expect(screen.queryByText("ACCOUNTS SCREEN")).toBeNull();
    expect((screen.getByLabelText(/Note/) as HTMLInputElement).value).toBe("Inspector booked");
  });
});

describe("CR-035 · re-parking a RESUMED draft patches the one row it came from", () => {
  it("PATCHes five fields and does NOT create a second draft, or move the flow or the subject", async () => {
    const user = userEvent.setup();
    const { calls } = mount("move_in", `?${PARKED_PARAM}=park-1`);

    await waitFor(() => {
      expect(calls.some((call) => call.url.includes("/wizard-parks/park-1"))).toBe(true);
    });
    await user.click(await screen.findByRole("button", { name: "Park" }));
    await user.selectOptions(await screen.findByLabelText(/Waiting on/), "documents");
    await user.click(screen.getByRole("button", { name: "Park it" }));

    await waitFor(() => {
      expect(calls.some((call) => call.method === "PATCH")).toBe(true);
    });
    // ⚠ A SECOND POST WOULD LEAVE THE CLERK TWO ROWS FOR ONE JOB — the failure
    // is invisible on the wizard and obvious on the list a week later.
    expect(calls.some((call) => call.method === "POST")).toBe(false);

    // ⚠ **FIND THE *PARK* PATCH BY WHAT MAKES IT ONE — A REASON.** Since
    // `CR-122-BRC06` the wizard also AUTOSAVES a draft, so `calls.find(method
    // === "PATCH")` is now whichever keystroke landed first, and this
    // assertion used to read that one and fail. The park is the patch that
    // carries `waiting_on`; there is exactly one.
    const patches = calls.filter((call) => call.method === "PATCH");
    const parkPatches = patches.filter(
      (call) => (call.body as Record<string, unknown>)?.waiting_on !== undefined,
    );
    expect(parkPatches).toHaveLength(1);
    const patch = parkPatches[0];
    expect(patch?.url).toContain("/wizard-parks/park-1");
    // `update_park` reads exactly these five for a PARK. `flow` is NOT among
    // them, in its own words because *"a draft that changed which flow it was
    // would be a different draft wearing the same id"* — so the client does
    // not pretend to send it.
    expect(Object.keys(patch?.body as Record<string, unknown>).sort()).toEqual(
      ["park_note", "remind_on", "step", "values", "waiting_on"].sort(),
    );
    // ⚠ **AND THE AUTOSAVE MUST NEVER CARRY A REASON, A NOTE OR A REMINDER.**
    // This is the line that keeps B19 §12.2's two controls apart: if a
    // keystroke sent the whole entry, a clerk who PARKED a draft *waiting on a
    // deposit* and then carried on typing would silently demote it back to an
    // unexplained draft on the queue everybody else reads.
    for (const autosave of patches.filter((call) => call !== patch)) {
      const body = autosave.body as Record<string, unknown>;
      expect(body.waiting_on).toBeUndefined();
      expect(body.park_note).toBeUndefined();
      expect(body.remind_on).toBeUndefined();
    }
    // An emptied note is an explicit `null` on a PATCH, never an omission:
    // *"an absent key is left alone; an explicit `null` clears"*, so omitting it
    // would leave last week's note on a draft the clerk just cleared.
    expect((patch?.body as Record<string, unknown>).park_note).toBeNull();
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 3 · RESUME — the typing comes back, the step is landed on, NOTHING is trusted
// ══════════════════════════════════════════════════════════════════════════

describe("CR-035 · resume (BR-SHL-046 · BR-SHL-048 (b))", () => {
  it("reads the draft, lands on the step it was parked at, and puts the typing back", async () => {
    const { calls } = mount("move_in", `?${PARKED_PARAM}=park-1`);

    // The draft is READ — one GET, by id, and it is the only read of the store.
    await waitFor(() => {
      expect(calls.some((call) => call.url.includes("/wizard-parks/park-1"))).toBe(true);
    });

    // BR-SHL-046 — the draft was parked at step 3 of the SEVEN-step list
    // (Customer, no `step_shape`), so it lands on step 2 of the FOUR — the
    // same step by name (`moveShared.moveInStoredStep`, CR-171-BRC10 P1.03).
    // Read off the rail's own `data-state`, which is rendered output.
    await waitFor(() => {
      const active = document.body.querySelector('[data-wizard-step="2"]');
      expect(active?.getAttribute("data-state")).toBe("active");
    });

    // ⚠ **AND THE STEPS AFTER IT ARE STILL LOCKED — BR-SHL-018 · BR-SHL-048 (b).**
    // This is the assertion that catches the tempting shortcut: restoring
    // `reached` alongside `step` would let a week-old draft jump straight to
    // Review, reaching the commit without step 4's checks ever running on
    // today's data. `disabled` on the rail button is what refuses that.
    const ahead = document.body.querySelector('[data-wizard-step="3"]');
    expect(ahead?.getAttribute("data-state")).toBe("upcoming");
    expect(ahead).toBeDisabled();
  });

  it("CR-171-BRC10 S9 · a resumed move-in carries NO park-age sentence, and is titled as an edit", async () => {
    // ⚠ **INVERTED 2026-10-05 (P2.17).** This asserted the frame's age line —
    // *"Waiting {{days}} days — nothing is held or changed until you finish
    // this"* — on the move-in. The PO ruled it out of this wizard (CR §2 S9,
    // *"this is okay"*) and images 30/47 draw no such line; the frame still
    // draws it for the flows that did not ask to drop it.
    // RED-FIRST, verbatim, with the age still handed to the frame:
    //   AssertionError: expected <span …(2)></span> to be null
    mount("move_in", `?${PARKED_PARAM}=park-1`);
    await waitFor(() => {
      expect(document.body.querySelector('[data-wizard-step="2"]')?.getAttribute("data-state")).toBe(
        "active",
      );
    });
    expect(document.body.querySelector('[data-wizard="park-age"]')).toBeNull();
    expect(document.body.textContent).not.toContain("nothing is held");
    expect(document.body.textContent).not.toContain("the unit is still held");
    // Image 47 — a resumed draft is an EDIT of that move-in, by its reference.
    expect(document.body.querySelector("h1")?.textContent).toBe("Edit move-in · MVI-26-0011");
  });

  it("BR-SHL-048 (b): resume reads the DRAFT and re-reads the PRODUCT — it does not take the draft's word", async () => {
    const { calls } = mount("move_in", `?${PARKED_PARAM}=park-1`);
    await waitFor(() => {
      expect(calls.some((call) => call.url.includes("/wizard-parks/park-1"))).toBe(true);
    });
    // The unit id in the draft is used to ASK AGAIN, never as an answer: the
    // wizard re-reads the accounts on that unit exactly as it would for a clerk
    // who had just chosen it. A resume that skipped this would be trusting a
    // week-old fact about who occupies Unit 12.
    await waitFor(() => {
      expect(calls.some((call) => call.url.includes("unit_id=u-12"))).toBe(true);
    });
  });
});

// ══════════════════════════════════════════════════════════════════════════
// 4 · THE HELPERS — a draft is JSON that left this app days ago
// ══════════════════════════════════════════════════════════════════════════

describe("hydrateForm / parkedString / parkedStringList — the draft is not trusted", () => {
  it("keeps the empty form's value for a field the draft does not carry", () => {
    expect(hydrateForm({ a: "", b: false }, { a: "typed" })).toEqual({ a: "typed", b: false });
  });

  it("REFUSES a field of the wrong type rather than coercing it", () => {
    // `autopay: "false"` is TRUTHY, and coercing it is the shape of a very quiet
    // money defect — an account silently enrolled in autopay by a stale draft.
    expect(hydrateForm({ autopay: false, unitId: "" }, { autopay: "false", unitId: 42 })).toEqual({
      autopay: false,
      unitId: "",
    });
  });

  it("refuses `null`, an array and a non-object outright", () => {
    expect(hydrateForm({ a: "" }, null)).toEqual({ a: "" });
    expect(hydrateForm({ a: "" }, ["a"])).toEqual({ a: "" });
    expect(hydrateForm({ a: "" }, "not an object")).toEqual({ a: "" });
    expect(hydrateForm({ a: "x" }, { a: null })).toEqual({ a: "x" });
  });

  it("parkedString reads a string and calls anything else `not filled in`", () => {
    expect(parkedString({ id: "u-12" }, "id")).toBe("u-12");
    expect(parkedString({ id: 12 }, "id")).toBe("");
    expect(parkedString({}, "id")).toBe("");
  });

  it("parkedStringList drops what is not a string rather than stringifying it", () => {
    expect(parkedStringList(["electric", 4, null, "water"])).toEqual(["electric", "water"]);
    expect(parkedStringList("electric")).toEqual([]);
  });

  it("clampToSteps holds a parked step inside the flow's OWN list (BR-SHL-046)", () => {
    const five = [{ id: "1", labelKey: "k", en: "e" }, { id: "2", labelKey: "k", en: "e" }];
    expect(clampToSteps(2, five)).toBe(2);
    // A draft parked at a step that no longer exists lands on the last one
    // rather than erroring — BR-SHL-011's fallback law.
    expect(clampToSteps(9, five)).toBe(2);
    expect(clampToSteps(0, five)).toBe(1);
    expect(clampToSteps(1.5, five)).toBe(1);
  });
});

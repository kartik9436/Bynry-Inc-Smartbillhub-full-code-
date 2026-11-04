// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-031 (EP-WRK-05) TC-1, TC-3, TC-4, TC-5, TC-6 ·
//           US-WRK-029 (EP-WRK-05) TC-1, TC-2, TC-3
// Rules:    BR-WRK-031 (the customer is told when the date or window moves;
//           every field change is audited) · BR-WRK-032 (Cancel is danger
//           tier; Save follows the box) · BR-WRK-023 (the third axis) ·
//           B14 rules 11, 32, 33
// Tests:    this file
// ───────────────────────────────────────────────────────
//
// ⚠ **THE PATCH TESTS ARE THE ONES THAT MATTER, AND THEY ARE PURE.**
// `patchOf` decides what a Save actually SENDS, and `US-WRK-031` TC-6 lives
// entirely inside it: a browser posts the whole form, so a Save that changed
// only the notes must still carry no `window_start` — otherwise the server
// fires the customer notification and tells somebody their visit moved to the
// time it already was. That is a bug no rendering assertion would ever catch,
// which is why it is tested as arithmetic on a function rather than through the
// DOM.
//
// ⚠ **THE RENDERED CASES MOUNT UNDER THE REAL ROUTE PATTERN.** Hard-won law 2's
// fixture clause: the portal's front page hid two working doors out of eight
// because its test mounted the component bare in a `MemoryRouter` with no
// `/:tenant/…` route, so `useParams()` came back undefined and every address
// the page built came out `//portal/…` — a protocol-relative URL to another
// host, which reads as a perfectly good string to `toContain`. So these mount
// at `/:tenant/work/orders/:orderId/edit` with a real `Route`, or `orderId`
// would be empty and the fetch would go to `/work-orders//edit`.
import { describe, expect, it } from "vitest";

import { patchOf } from "./OrderEditPage";
import type { OrderEditForm } from "./workEndpoints";

const WO_4821: OrderEditForm = {
  id: "11111111-1111-4111-8111-111111111111",
  order_no: "WO-4821",
  type: "Disconnect for non-payment",
  dispatch_state: "en_route",
  state: "in_progress",
  priority_id: "p-high",
  due_at: "2026-08-16T16:00:00",
  window_start: "2026-08-16T08:00:00",
  window_end: "2026-08-16T12:00:00",
  area_id: "a-north",
  technician_notes: "Dog on property — use side gate. Customer notified 08:00.",
  technician: { kind: "person", name: "D. Ortiz", slug: "d-ortiz" },
  technician_id: "t-ortiz",
  premise: { id: "prem-1", premise_no: "P-0007", address: "903 Birch Ln" },
  template_id: "tpl-disconnect",
  priority_locked: false,
};

/** The draft the screen builds when the order loads — the identity case. */
function loadedDraft() {
  return {
    dispatch_state: "en_route",
    priority_id: "p-high",
    area_id: "a-north",
    technician_notes: "Dog on property — use side gate. Customer notified 08:00.",
    technician_id: "t-ortiz",
    date: "2026-08-16",
    window: "morning" as const,
    exact: "",
  };
}

describe("US-WRK-031 — what a Save actually sends", () => {
  it("TC-6 · changing only the notes reaches NO notification branch", () => {
    // ⛔ THE CASE THIS WHOLE FUNCTION EXISTS FOR. The form posts every field;
    // if `window_start` rode along unchanged, the server would see the window
    // "move" to where it already was and queue an `appointment` message. Sarah
    // Miller would be told her visit had moved — to the time she was already
    // given.
    const patch = patchOf(WO_4821, {
      ...loadedDraft(),
      technician_notes: "Dog on property — use side gate. Ring first.",
    });
    expect(Object.keys(patch)).toEqual(["technician_notes"]);
    expect(patch).not.toHaveProperty("window_start");
    expect(patch).not.toHaveProperty("window_end");
    expect(patch).not.toHaveProperty("due_at");
  });

  it("a Save that changed nothing sends nothing", () => {
    // The server answers `changed: []` and writes no audit row. A Save that
    // logged "nothing changed" would make the audit tab unusable, and that tab
    // is what a supervisor reads to find out what happened.
    expect(patchOf(WO_4821, loadedDraft())).toEqual({});
  });

  it("TC-1 · moving the technician AND the window sends both, and only both", () => {
    const patch = patchOf(WO_4821, {
      ...loadedDraft(),
      technician_id: "t-patel",
      window: "afternoon",
    });
    expect(patch.technician_id).toBe("t-patel");
    expect(patch.window_start).toBe("2026-08-16T12:00:00");
    expect(patch.window_end).toBe("2026-08-16T17:00:00");
    // The demo script's move: 08:00–12:00 becomes 12:00–17:00.
    expect(patch).not.toHaveProperty("area_id");
    expect(patch).not.toHaveProperty("technician_notes");
  });

  it("*Any time* CLEARS the window rather than storing a fourth value", () => {
    // A window nobody promised is not a promise of "any time" — it is no
    // promise at all, so both ends go to null and the customer is told the
    // visit moved, because it did.
    const patch = patchOf(WO_4821, { ...loadedDraft(), window: "any" });
    expect(patch.window_start).toBeNull();
    expect(patch.window_end).toBeNull();
  });

  it("an exact appointment is a START and no END — one moment, not a range", () => {
    const patch = patchOf(WO_4821, {
      ...loadedDraft(),
      window: "exact",
      exact: "15:30",
    });
    expect(patch.window_start).toBe("2026-08-16T15:30:00");
    expect(patch.window_end).toBeNull();
  });

  it("clearing the area sends an explicit null, never an empty string", () => {
    // `""` would be a uuid the server cannot resolve and a 404 the dispatcher
    // could not explain; `null` is *this order has no area*, which is a fact.
    const patch = patchOf(WO_4821, { ...loadedDraft(), area_id: "" });
    expect(patch.area_id).toBeNull();
  });

  it("a moved DATE alone still tells the customer — the day is the promise too", () => {
    const patch = patchOf(WO_4821, { ...loadedDraft(), date: "2026-08-17" });
    expect(patch.due_at).toBe("2026-08-17T00:00:00");
    expect(patch.window_start).toBe("2026-08-17T08:00:00");
  });
});

describe("DEF-WRK-9688 — the form opens on the utility's clock", () => {
  // A Brazos Bend (US Central) 08:00–12:00 on 6 Oct is stored as 13:00Z–17:00Z.
  // The server reads it back as `appointment` in the utility's zone; the form
  // must open on THAT, or a laptop in any other zone opens the job on an
  // *Exact* 13:00 and the next Save moves the visit five hours.
  const CENTRAL: OrderEditForm = {
    ...WO_4821,
    due_at: "2026-10-06T05:00:00+00:00",
    window_start: "2026-10-06T13:00:00+00:00",
    window_end: "2026-10-06T17:00:00+00:00",
    appointment: { date: "2026-10-06", start: "08:00", end: "12:00", time_zone: "America/Chicago" },
  };

  it("an unchanged Central morning sends nothing", () => {
    expect(patchOf(CENTRAL, { ...loadedDraft(), date: "2026-10-06" })).toEqual({});
  });

  it("moving it to the afternoon sends the utility's clock times", () => {
    const patch = patchOf(CENTRAL, { ...loadedDraft(), date: "2026-10-06", window: "afternoon" });
    expect(patch.window_start).toBe("2026-10-06T12:00:00");
    expect(patch.window_end).toBe("2026-10-06T17:00:00");
  });
});

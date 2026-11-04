// ── Trace ──────────────────────────────────────────────
// Story:    US-WRK-033 (the six-tab work order detail) TC-1..TC-7 ·
//           US-WRK-032 (everything drawn is the ORDER's own copy) ·
//           US-WRK-043 (safety blocks the task list).  Screens: Work-008
// Rules:    BR-WRK-008 (copy, never link) · BR-WRK-037 (the safety lock) ·
//           BR-MET-110 · B14 rules 6 · 11 · 21 · 31 · 32 · 33
// ───────────────────────────────────────────────────────
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, NOT BARE.** `DEF-CWP-3925`'s second
// lesson: a component mounted inside a `MemoryRouter` with no matching route
// has `useParams()` undefined, so every address it builds comes out `//…` — a
// protocol-relative URL to another host, which reads as a perfectly good string
// to `toContain`. The one assertion that could catch a broken link cannot be
// written from a bare mount.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { queryKeys } from "@/api/queryClient";
import { SCREEN_ROUTES } from "@/routing/screenIds";
// The screen fires a toast on a refusal, and `useToast` THROWS outside its
// provider — so a harness without one fails every case with one message and
// says nothing about the screen.
import { ToastProvider } from "@/components/Toast";

import {
  ORDER_DETAIL_HELD_CONTROLS,
  ORDER_DETAIL_TABS,
  OrderDetailPage,
  WORK_ORDER_DETAIL_ROUTE,
  WORK_ORDER_DETAIL_SCREEN,
  WORK_ORDER_DETAIL_SCREEN_PATH,
} from "./OrderDetailPage";
import { NEW_ORDER_WIZARD_ROUTE, NEW_ORDER_WIZARD_SCREEN_PATH } from "./NewOrderWizard";
import type { OrderChecklist } from "./workEndpoints";

const TENANT = "brazosbend";
const ID = "wo-4822";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

/** `10-execution-plan.md` H3's own fixture: `WO-4822 · Meter exchange ·
 *  221 Oak Ave · A-10688 · D. Ortiz · Today 15:30 · Scheduled`, with the
 *  drawing's seven tasks and three readings. */
const ORDER = {
  id: ID,
  order_no: "WO-4822",
  type: "Meter exchange",
  premise: { id: "p-1", premise_no: "P-00118", address: "221 Oak Ave" },
  service: "electric",
  state: "planned" as const,
  outcome: null,
  mode: "our_crew",
  is_gate: false,
  connection: null,
  account: { id: "a-1", account_no: "A-10688" },
  raised_at: "2026-03-15T09:00:00Z",
  priority: { id: "pr-3", code: "NORMAL", name: "Normal", colour: "info", rank: 3 },
  technician: { kind: "person", name: "D. Ortiz", slug: "d-ortiz" },
  due_at: "2026-03-15T15:30:00Z",
  window_start: null,
  window_end: null,
  dispatch_state: "scheduled" as const,
  source: "dispatcher" as const,
  source_ref: null,
  area: null,
  est_duration_minutes: 45,
};

function safety(seq: number, text: string, ticked = false) {
  return {
    id: `sf-${seq}`,
    seq,
    text,
    is_mandatory: true,
    ticked_at: ticked ? "2026-03-15T15:12:00Z" : null,
    ticked_by: ticked ? "u-ortiz" : null,
  };
}

function task(seq: number, title: string, minutes: number, photo = false) {
  return {
    id: `tk-${seq}`,
    seq,
    title,
    est_minutes: minutes,
    photo_required: photo,
    is_mandatory: false,
    ticked_at: null,
    ticked_by: null,
    photo_attachment_id: null,
  };
}

function checklist(over: Partial<OrderChecklist> = {}): OrderChecklist {
  const safetyRows = [
    safety(1, "Isolate at the main before opening the box"),
    safety(2, "Gloves and eye protection on"),
    safety(3, "Check for standing water"),
  ];
  return {
    order_id: ID,
    order_no: "WO-4822",
    template_id: "t-meter-exchange",
    template_version: 2,
    safety: safetyRows,
    safety_lock: {
      locked: true,
      remaining: 3,
      first_outstanding: "Isolate at the main before opening the box",
      ticked: 0,
      total: 3,
      mandatory_total: 3,
    },
    tasks: [
      task(1, "Confirm address and customer", 3),
      task(2, "Isolate supply & remove old meter", 12),
      task(3, "Record final read on old meter", 4, true),
      task(4, "Fit new meter and seal", 15, true),
      task(5, "Record opening read on new meter", 4),
      task(6, "Restore supply and test", 5),
      task(7, "Leave card and tidy site", 2),
    ],
    tasks_total: 7,
    tasks_ticked: 0,
    tasks_est_minutes: 45,
    readings: [
      {
        id: "rd-1", seq: 1, prompt: "Final read, old meter", unit_of_measure: "kWh",
        min_value: "0.0000", max_value: "99999.0000", required: true, photo_required: true,
        posts_as_meter_read: true, value: null, captured_at: null,
        photo_attachment_id: null, in_range: null,
      },
      {
        id: "rd-2", seq: 2, prompt: "Opening read, new meter", unit_of_measure: "kWh",
        min_value: "0.0000", max_value: "999.0000", required: true, photo_required: true,
        posts_as_meter_read: false, value: null, captured_at: null,
        photo_attachment_id: null, in_range: null,
      },
      {
        id: "rd-3", seq: 3, prompt: "New meter serial", unit_of_measure: "serial",
        min_value: null, max_value: null, required: true, photo_required: false,
        posts_as_meter_read: false, value: null, captured_at: null,
        photo_attachment_id: null, in_range: null,
      },
    ],
    materials: [
      {
        id: "mt-1", part_id: "p-mtr", part_no: "MTR-E1P",
        part_name: "Electric meter, single phase", planned_qty: "1.0000",
        used_qty: null, unit_of_measure: "each", unplanned: false,
      },
    ],
    help: [
      { id: "hp-1", seq: 1, kind: "document" as const, label: "Meter exchange SOP", ref: "SOP-114" },
      { id: "hp-2", seq: 2, kind: "phone" as const, label: "Control room", ref: "555-0142" },
      { id: "hp-3", seq: 3, kind: "phone" as const, label: "Duty supervisor", ref: "555-0188" },
    ],
    details: {
      access_notes: null, hazards: null, gate_code: null,
      show_account_summary: true, show_asset_card: false,
      show_access_notes: true, show_appointment: true,
    },
    ...over,
  };
}

function markup(
  tab = "checklist",
  list: OrderChecklist | null = checklist(),
  order: Record<string, unknown> = ORDER,
) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.workOrder(ID), order);
  if (list !== null) queryClient.setQueryData(queryKeys.workOrderChecklist(ID), list);
  queryClient.setQueryData(queryKeys.workOrderAudit(ID), { order_no: "WO-4822", rows: [] });
  return renderToStaticMarkup(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
      <MemoryRouter initialEntries={[`/${TENANT}/work/orders/${ID}?tab=${tab}`]}>
        <Routes>
          <Route path="/:tenant/work/orders/:orderNo" element={<OrderDetailPage />} />
        </Routes>
      </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

// ══════════════════════════════════════════════════════════════════════════
// THE CASE THAT WOULD HAVE CAUGHT `DEF-WRK-4051`, AND DID NOT EXIST
// ══════════════════════════════════════════════════════════════════════════
//
// ⚠ **BOTH SCREENS WERE UNREACHABLE FROM THE DAY THEY SHIPPED AND EVERY CHECK
// IN THIS REPOSITORY WAS GREEN OVER IT.** The route constants carried a
// `/:tenant` prefix that `App.tsx` adds for itself, so `ROUTE.slice(1)` came
// out `:tenant/:tenant/work/orders/…` and matched nothing; the address fell
// through to the not-built-yet page.
//
// `tsc` cannot see it — both are strings. The 44 cases below could not see it,
// because every one mounts its component DIRECTLY under a `MemoryRouter` with
// the pattern written into the test file: they prove the component works and
// say nothing about whether the app reaches it. Only the browser walkthrough
// could, and it is what found it.
//
// **These three cases are the cheap half of that proof**, so the next lane does
// not need a browser to catch the same mistake: they assert the SHAPE of what
// `App.tsx` will register, which is the fact that was wrong.
describe("the addresses App.tsx registers (DEF-WRK-4051)", () => {
  it("a ROUTE constant carries no tenant — App.tsx mounts it under one", () => {
    // `.slice(1)` on a constant beginning `/:tenant` yields `:tenant/…`, which
    // under a `:tenant` parent is `/:tenant/:tenant/…` and matches nothing.
    expect(WORK_ORDER_DETAIL_ROUTE.startsWith("/:tenant")).toBe(false);
    expect(NEW_ORDER_WIZARD_ROUTE.startsWith("/:tenant")).toBe(false);
    expect(WORK_ORDER_DETAIL_ROUTE).toBe("/work/orders/:orderNo");
    expect(NEW_ORDER_WIZARD_ROUTE).toBe("/work/orders/new");
  });

  it("a SCREEN-REGISTRY constant DOES carry the tenant — different job", () => {
    // `screenIds.ts` keys on the full pattern, and `OrdersPage.test.tsx`
    // compares hold addresses against it. Two jobs, two strings, named apart
    // so nobody has to remember which one a call site wants.
    expect(WORK_ORDER_DETAIL_SCREEN_PATH).toBe("/:tenant/work/orders/:orderNo");
    expect(NEW_ORDER_WIZARD_SCREEN_PATH).toBe("/:tenant/work/orders/new");
  });

  it("both registry paths are in the screen registry", () => {
    const registered = new Set(SCREEN_ROUTES.map((entry) => entry.path));
    expect(registered.has(WORK_ORDER_DETAIL_SCREEN_PATH)).toBe(true);
    expect(registered.has(NEW_ORDER_WIZARD_SCREEN_PATH)).toBe(true);
  });
});

/** The same order once the field has finished it — ruling 15's second shape. */
const COMPLETED = { ...ORDER, state: "completed" as const, outcome: "passed", dispatch_state: "complete" };

/** The header's pills, in order, as text — the WHOLE set, not one pill at a time. */
function headerPills(html: string): string[] {
  return [...html.matchAll(/<span class="pill [^"]*"[^>]*>([^<]*)<\/span>/g)].map((m) => m[1]);
}

describe("DEF-WRK-9681 (reverses DEF-WRK-9643) — the header draws image 04's four pills", () => {
  // The escape reason of 9643 still holds — *"nothing asserts the header as a
  // whole"* — so these assert the full set per state. What changed is the set:
  // image 04 draws *Complete · Completed · Passed · Awaiting approval*, and
  // rule 41 builds the drawn shape exactly (decision log, CR-168 round 8).
  it("an accepted job reads Complete · Completed · Passed · Accepted", () => {
    const accepted = { ...COMPLETED, accepted: { at: "2026-10-04T15:00:00Z", by: { name: "Dana Whitfield" } } };
    expect(headerPills(markup("overview", checklist(), accepted))).toEqual([
      t("work.orders.dispatch.complete"),
      t("work.orders.state.completed"),
      t("work.orders.outcome.passed"),
      t("work.order.approval.accepted"),
    ]);
  });

  it("a closed job awaiting approval reads Complete · Completed · Passed · Awaiting approval (image 04)", () => {
    expect(headerPills(markup("overview", checklist(), COMPLETED))).toEqual([
      t("work.orders.dispatch.complete"),
      t("work.orders.state.completed"),
      t("work.orders.outcome.passed"),
      t("work.order.approval.awaiting"),
    ]);
  });

  it("a finished job still carrying a stale dispatch status reads Complete, not Scheduled (DEF-WRK-9526)", () => {
    expect(headerPills(markup("overview", checklist(), { ...COMPLETED, dispatch_state: "scheduled" }))[0]).toBe(
      t("work.orders.dispatch.complete"),
    );
  });

  it("an open job keeps both axes — where the crew is, and the job's state", () => {
    expect(headerPills(markup("overview", checklist(), { ...ORDER, dispatch_state: "en_route" }))).toEqual([
      t("work.orders.dispatch.en_route"),
      t("work.orders.state.planned"),
    ]);
  });
});

describe("US-WRK-033 — the order detail (Work-008, CR-168 images 03–11)", () => {
  it("draws FOUR tabs — Location and Customer moved onto the Overview (ruling 12)", () => {
    // ⚠ REWRITTEN BY CR-168 (P1.21). It asserted WM-19's six; the PO ruled on
    // 2026-09-24, *"in overview tab only, no need of extra tabs"*.
    expect([...ORDER_DETAIL_TABS]).toEqual(["overview", "checklist", "parts", "audit"]);
  });

  it("TC-7 · B14 rule 31 — the visible reference is WO-4822, never the uuid", () => {
    const html = markup();
    expect(html).toContain("WO-4822");
    // The uuid IS in the DOM as a link target and a form value; what rule 31
    // forbids is it being the VISIBLE VALUE of a field. `data-screen` and
    // hrefs are not fields, so the assertion is on the rendered TEXT.
    const visible = html.replace(/<[^>]*>/g, " ");
    expect(visible).not.toContain(ID);
  });

  it("TC-7 — one page header, and the screen declares its badge", () => {
    const html = markup();
    expect(html).toContain(`data-screen="${WORK_ORDER_DETAIL_SCREEN}"`);
    expect((html.match(/data-page-header-tabs/g) ?? []).length).toBe(1);
  });

  it("TC-1 — the checklist draws seven tasks, three safety rows and three readings", () => {
    const html = markup();
    expect((html.match(/data-task-row=/g) ?? []).length).toBe(7);
    expect((html.match(/data-safety-row=/g) ?? []).length).toBe(3);
    expect((html.match(/data-reading-row=/g) ?? []).length).toBe(3);
    expect(html).toContain("Isolate supply &amp; remove old meter");
  });

  it("TC-1 · hard rule 3 — a reading's unit is its own cell, never inside the prompt", () => {
    const html = markup();
    // The drawing's own two ranges, and the unit beside them rather than in
    // the words: *Final read (kWh)* is a unit nothing can compare.
    expect(html).toContain("kWh");
    // P1.18 (CR-168) — `0.0000–99999.0000` printed the column's four places.
    expect(html).toContain("0–99,999");
    expect(html).not.toContain("0.0000");
    expect(html).not.toContain("Final read (kWh)");
  });

  it("TC-1 — the count is the SERVER's two numbers, not a string built here", () => {
    // The count is the RECORD's (ruling 15) — it shows on a completed job only.
    const html = markup("checklist", checklist({ tasks_ticked: 3 }), COMPLETED);
    expect(html).toContain(t("work.order.tasks.count", { done: 3, total: 7 }));
    expect(markup("checklist", checklist({ tasks_ticked: 3 }))).not.toContain(
      t("work.order.tasks.count", { done: 3, total: 7 }),
    );
  });

  it("BR-WRK-008 — the version the checklist came from is drawn as a NUMBER", () => {
    // The order keeps `template_id` + `template_version` and nothing else, so
    // the Overview shows a version rather than a link to something that moves.
    expect(markup("overview")).toContain(t("work.order.overview.versionValue", { version: 2 }));
  });

  // ⚠ **FOUR CASES LEFT HERE WITH *Mark complete* (CR-168, ruling 18).** They
  // asserted the office's *Mark complete* greyed under the safety lock, live
  // once it lifted, and the *Marking complete* consequence box. The PO ruled
  // on 2026-09-24 that *"back office cannot complete the job it can only
  // accept it"*: the button, the box and the office's tick boxes are GONE, and
  // `orderPage/orderPage.dom.test.tsx` now asserts their absence on both
  // shapes. The safety lock is still the server's rule (`BR-WRK-037`) — it
  // binds the PHONE's tick, which is where a line is ticked now.

  it("B14 rule 6 — Cancel order is the danger tier", () => {
    expect(markup()).toContain(t("work.order.actions.cancel"));
  });

  // ══════════════════════════════════════════════════════════════════════
  // Hard-won law 2's MIRROR clause, pointed at the next wave
  // ══════════════════════════════════════════════════════════════════════
  //
  // Wave G declared its two refusals as data with the address that released
  // each, and wave H landing those addresses turned its suite red and NAMED
  // the controls. This is the same machinery for `Work-008`'s four commits,
  // none of which wave H wired.

  it("every held action declares a reason and the endpoint that releases it", () => {
    // ⚠ **ZERO SINCE WAVE L — the four entries went out in the commit that
    // wired the four buttons.** The loop stays because it is the machinery, and
    // the case that FIRES when a hold expires now lives in
    // `OrderDetailPage.dom.test.tsx`, where it can ask the question that
    // matters here: does this screen already CALL the endpoint the hold is
    // waiting for?
    for (const hold of ORDER_DETAIL_HELD_CONTROLS) {
      // A rendered refusal has COPY — `BR-SHL-025`. A held control with no
      // sentence is a greyed button a person has to guess about.
      expect(i18n.exists(hold.reasonKey)).toBe(true);
      expect(hold.releasedBy).toMatch(/^(GET|POST|PATCH) \/work-orders\//);
    }
  });

  it("FIRES WHEN A WAVE WIRES ONE: every held action is still disabled", () => {
    // The day somebody wires *Put on hold…* and forgets to take its entry out
    // of the list, this fails and names the control — rather than leaving a
    // stale sentence under a working button, which is `DEF-CWP-3925` and which
    // no gate in this repository can see.
    const html = markup();
    for (const hold of ORDER_DETAIL_HELD_CONTROLS) {
      const label = t(`work.order.${hold.control}`);
      const at = html.indexOf(label);
      expect(at, `${hold.control} is not on the screen at all`).toBeGreaterThan(-1);
      const button = html.slice(html.lastIndexOf("<button", at), at);
      // ⚠ **`toContain("disabled")` HERE COULD NOT FAIL, AND ONLY THE RED PROOF
      // FOUND IT (law 7, and law 11's *a check whose output cannot distinguish
      // pass from fail is worse than no check*).** The shared button kit emits
      // `disabled:opacity-45 disabled:cursor-not-allowed` in its CLASS string
      // on every button it draws, enabled or not — so the substring matched
      // always. Enabling *Put on hold…* and re-running gave **19 passed**.
      //
      // It is the third check of this exact shape this lane met in one session:
      // `text-danger` was a listed class that resolved to nothing, and wave G's
      // `not.toContain("<p")` matched `<path>`. All three are a substring
      // standing in for a structure.
      //
      // The ATTRIBUTE, not the word. React renders a disabled button as
      // `disabled=""`, and the class utilities never contain that.
      expect(
        button,
        `${hold.control} is enabled but still listed in ORDER_DETAIL_HELD_CONTROLS — ` +
          "take its entry out in the commit that wires it (hard-won law 2's mirror clause)",
      ).toMatch(/\sdisabled=""/);
    }
  });

  it("every hold's reason is a HELD reason — the lock's is a different namespace", () => {
    // ⚠ **THIS CASE WAS FIRST WRITTEN AS `some(h => h.reasonKey ===
    // "work.order.checklist.locked")` AND `tsc` REFUSED IT** — *"This
    // comparison appears to be unintentional… have no overlap"*. It was right:
    // `ORDER_DETAIL_HELD_CONTROLS` is `as const`, so the reason keys are a
    // literal union and the comparison could never be true. A FOURTH check
    // that could not fail, and the compiler caught this one.
    //
    // The TYPE is therefore the guard: adding the lock's key to that list would
    // not compile. What is worth asserting at runtime is the invariant behind
    // it — a hold's reason lives under `work.order.held.`, and the safety
    // lock's does not, because they are different kinds of refusal. A lane
    // that reached for the lock's sentence to explain a hold would fail here.
    //
    // ⚠ **AND THE `as const` GUARD DESCRIBED ABOVE IS GONE SINCE WAVE L**, with
    // the four entries: an empty `as const` array has no literal union to
    // compare against, so the type can no longer refuse anything and this
    // runtime loop is the whole check. It runs zero times today. That is not a
    // reason to delete it — it is the machinery the next hold inherits, and
    // `OrderDetailPage.dom.test.tsx` carries the case that FIRES when a hold
    // expires.
    for (const hold of ORDER_DETAIL_HELD_CONTROLS) {
      expect(hold.reasonKey.startsWith("work.order.held.")).toBe(true);
    }
    expect("work.order.checklist.locked".startsWith("work.order.held.")).toBe(false);
  });

  it("TC-7 · B14 rule 32 — no rule id or internal code in clerk-facing copy", () => {
    const visible = markup().replace(/<[^>]*>/g, " ");
    for (const forbidden of ["BR-WRK", "WS-08", "WM-1", "US-WRK", "work_order_"]) {
      expect(visible).not.toContain(forbidden);
    }
  });

  // ⚠ **THE CASE `DEF-WRK-4635` NEEDED AND TC-7 COULD NOT BE.** TC-7's fixture
  // sets `template_id: null`, which makes *raised without a template* TRUE — so
  // it proves the branch and can never see that the SENTENCE asserts a cause
  // the branch does not test. A template published with no steps is lawful, and
  // an order raised from one drew that sentence while the Overview tab drew its
  // version. One screen, two tabs, contradicting each other.
  it("DEF-WRK-4635 — an EMPTY TEMPLATE does not claim the order had none", () => {
    const fromEmptyTemplate = checklist({
      template_id: "tpl-1", template_version: 1, tasks: [], safety: [],
      tasks_total: 0, tasks_ticked: 0,
      safety_lock: { locked: false, remaining: 0, first_outstanding: null, ticked: 0, total: 0, mandatory_total: 0 },
    });
    const html = markup("checklist", fromEmptyTemplate);
    expect(html).toContain(t("work.order.checklist.emptyTemplate"));
    expect(html).not.toContain(t("work.order.checklist.empty"));
  });

  it("US-WRK-032 TC-7 — an order with no template shows the empty state, not an error", () => {
    const html = markup("checklist", checklist({
      safety: [], tasks: [], readings: [], materials: [], help: [], details: null,
      tasks_total: 0, tasks_ticked: 0, tasks_est_minutes: 0,
      template_id: null, template_version: null,
      safety_lock: {
        locked: false, remaining: 0, first_outstanding: null,
        ticked: 0, total: 0, mandatory_total: 0,
      },
    }));
    expect(html).toContain(t("work.order.checklist.empty"));
  });

  it("the readings PHOTOGRAPH column is the RECORD's — not on an open job (ruling 15)", () => {
    expect(markup("checklist", checklist(), COMPLETED)).toContain(t("work.order.readings.photograph"));
    expect(markup()).not.toContain(`>${t("work.order.readings.photograph")}<`);
  });

  it("the parts tab draws the planned quantity WITH its unit (hard rule 3), no trailing zeros (P1.18)", () => {
    expect(markup("parts")).toContain("1 each");
    expect(markup("parts")).not.toContain("1.0000");
  });
});

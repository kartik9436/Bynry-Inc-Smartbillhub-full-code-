// @vitest-environment jsdom
// ── Trace ──────────────────────────────────────────────
// Change:  CR-150-BRC09 — the New connects list, revamped to
//          `05-prototype/new-connect-detail-2026-09-28/00-list.png`.
// Rules:   hard-won law 2 (built is not wired — a tile that renders and does
//          nothing when pressed is the defect this file is written against) ·
//          law 2's fixture clause (mount under the REAL path pattern) ·
//          BR-SHL-025 (a control that cannot act is disabled WITH its reason)
// Tests:   the two claims a static render structurally CANNOT make
// ───────────────────────────────────────────────────────
//
// ╔══════════════════════════════════════════════════════════════════════════╗
// ║  WHY THIS FILE EXISTS BESIDE `NewConnectsTab.test.tsx`                   ║
// ╚══════════════════════════════════════════════════════════════════════════╝
// The sibling file renders with `renderToStaticMarkup`, which is the right
// tool for *what is on the screen* and is **structurally incapable** of
// answering *what happens when a clerk presses this* — there is no event loop
// and no state. Task 16's requirement is a BEHAVIOUR: *"the tile must set the
// filter, not filter around it — after clicking, the FilterBar must show that
// filter as applied, or two controls disagree about what the table is
// showing."* A static case can seed a filtered state and watch the bar draw
// it, and it would pass just as happily over a tile whose `onClick` did
// nothing at all. That is law 7's *check that cannot fail* shape, so the
// press itself is asserted here.
//
// ⚠ **MOUNTED UNDER THE REAL PATH PATTERN, WHICH IS LOAD-BEARING.** A bare
// `MemoryRouter` with no `/:tenant/...` route leaves `useParams().tenant`
// undefined, so every address the screen builds comes out `//accounts/…` — a
// protocol-relative URL to another host that reads as a perfectly good string
// to `toContain`. That is how the customer portal shipped eight doors with two
// of them working (`DEF-CWP-3925`).
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";
import i18n from "@/i18n";

import { createApiClient } from "@/api/client";

import { NewConnectsTab } from "./NewConnectsTab";
import type { ConnectionList, ConnectionRow } from "./worklistEndpoints";

const TEST_TENANT = "brazosbend";
const t = (key: string, params?: Record<string, unknown>): string => i18n.t(key, params);

function row(over: Partial<ConnectionRow> = {}): ConnectionRow {
  return {
    id: "con-0117",
    connection_no: "CON-26-0117",
    premises: {
      id: "prm-500",
      premise_no: "P-000500",
      name: "Main Street Block",
      address: "500 Main Street",
    },
    home: { kind: "premises", id: "prm-500" },
    units: 25,
    services: ["electric", "water"],
    orders: { done: 5, total: 7 },
    target_activation: "2026-09-30",
    waiting_on: null,
    state: "partly_activated",
    request_no: "SR-26-0018",
    applicant: "Rodriguez, M.",
    // ── `DEF-CUS-7804` · the five facts the endpoint has served since
    //    `01580d8fc` and that nothing on this screen read ────────────────
    customer: { name: "Jonas Janssen", account_no: "AC-2026-00011" },
    age_days: 16,
    age_is_accented: false,
    quote_total: { stored: "535.0000", display: "535.00" },
    mode: "our_crew",
    scope: "new_premise",
    raised_by: "Dana Whitfield",
    last_stamped_event: { at: "2026-09-12T09:15:00Z", what: "submitted" },
    ...over,
  };
}

function payload(over: Partial<ConnectionList> = {}): ConnectionList {
  return {
    count: 1,
    next: null,
    previous: null,
    results: [row()],
    kpis: {
      open: 7,
      waiting_on_inspection: 2,
      partly_activated: 3,
      units_awaiting_activation: 42,
      oldest: { days: 19, connection_no: "CON-26-0119", waiting_on: "permit" },
      // `DEF-CUS-7804` — the drawing's *Waiting on someone*, which is every
      // open build with ANY `waiting_on` and NOT the inspection literal above.
      waiting_on_anyone: 3,
      // ⛔ `DEF-CUS-7619` — exactly one of the two is ever set, and today it
      // is always the reason. `connection_reads.OWED_ON_OPEN_BUILDS_UNAVAILABLE`
      // verbatim, so the case moves when the server's own constant does.
      owed_on_open_builds: null,
      owed_on_open_builds_unavailable: {
        code: "billing_publishes_no_batched_invoice_position",
        tracks: "DEF-CUS-7619",
        detail:
          "What each build still owes is held on its bill, and the bills cannot be read a " +
          "page at a time yet. No total is shown, and nothing says these builds are paid for.",
      },
    },
    segment: "all",
    unavailable: [],
    filters: ["state"],
    states: [{ code: "open" }, { code: "partly_activated" }, { code: "on_hold" }],
    ...over,
  };
}

// ⚠ **THERE IS NO GLOBAL `setupFiles` IN THIS REPO, SO NOTHING UNMOUNTS
// BETWEEN CASES.** `vitest.config`'s own note says so deliberately. Without
// this hook every `render` appends to the same `document.body` and the second
// case reads the first case's screen — which is not a flake, it is a suite
// asserting over a DOM that no longer matches any one mount. The first draft
// of this file learned it as *"Found multiple elements with the text:
// CON-26-0117"* on five of seven cases.
afterEach(() => {
  cleanup();
});

/** Mount the tab where the router really mounts it, and record what it asks
 *  the server for — the filter reaching the WIRE is the other half of task 16
 *  and a rendered chip alone cannot show it. */
function mount(body: ConnectionList = payload()) {
  const urls: string[] = [];
  const client = createApiClient({
    tenant: TEST_TENANT,
    fetchImpl: async (input) => {
      urls.push(String(input));
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    },
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/${TEST_TENANT}/accounts?tab=new-connects`]}>
        <Routes>
          <Route path="/:tenant/accounts" element={<NewConnectsTab client={client} />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return { urls, view };
}

/** The rows arrive from a query, so every case waits for the first one before
 *  it presses anything. Scoped to the MOUNT's own container rather than to
 *  `screen`, which reads the whole document. */
async function settled(container: HTMLElement): Promise<void> {
  await waitFor(() => {
    expect(container.querySelector("[data-tile]")).not.toBeNull();
    expect(container.textContent).toContain("CON-26-0117");
  });
}

describe("S86 · the New connects list — what a press actually does (CR-150-BRC09)", () => {
  it("task 16 — pressing `Open` SETS the filter, and the toolbar then says so", async () => {
    const { view } = mount();
    const box = view.container;
    await settled(box);
    // ⚠ **THE TILE IS ADDRESSED BY `data-tile`, NOT BY ITS WORD.** *Open* is
    // also the first word of the row's eye action (*Open this connection*),
    // so a `getByRole("button", {name: /Open/})` finds two controls and the
    // case fails for a reason that has nothing to do with what it asserts.
    const tile = box.querySelector('[data-tile="open"]') as HTMLElement;
    expect(tile.getAttribute("aria-pressed")).toBe("false");

    fireEvent.click(tile);

    // ⚠ **THE TILE AND THE BAR READ ONE STATE.** A tile that narrowed the rows
    // itself would leave the bar empty here, and the screen would be showing a
    // filtered table under a toolbar saying nothing is filtered.
    expect(box.querySelector('[data-tile="open"]')?.getAttribute("aria-pressed")).toBe("true");
    // ⚠ **`[data-chip-row]` IS THE FILTER BAR, AND `.table-toolbar` IS NOT.**
    // The toolbar holds the search box and the `▦ Columns` panel; the bar the
    // filter chips live in is the slot beside it. The first draft read
    // `.table-toolbar` and came back with *"Columns · show / hide · ↑↓
    // reorder"* — a true reading of the wrong element, which is law 7's
    // *looking at the wrong thing* in miniature.
    const bar = box.querySelector("[data-chip-row]") as HTMLElement;
    // ⚠ **THIS ASSERTION FOUND A REAL DEFECT AND IT IS WHY THE QUERY NOW
    // CARRIES `placeholderData`.** Pressing a tile changes the query KEY, so
    // `listQuery.data` went `undefined` for the round trip — and this screen
    // builds its filter OPTIONS out of that payload, so `offerableFilters`
    // emptied the group, `FilterBar` returned `null`, and the whole chip row
    // including the chip the clerk had just made vanished until the response
    // landed. No static render could see it: they each show one settled
    // payload.
    expect(bar).not.toBeNull();
    // `textContent` rather than `getByText`: the chip renders its label and
    // its value in two elements, so a text matcher over one of them cannot
    // see the sentence a clerk actually reads.
    expect(bar.textContent).toContain("Show");
    expect(bar.textContent).toContain("Open");
  });

  it("task 16 — pressing it a second time clears the filter", async () => {
    const { view } = mount();
    const box = view.container;
    await settled(box);
    fireEvent.click(box.querySelector('[data-tile="open"]') as HTMLElement);
    expect(box.querySelector('[data-tile="open"]')?.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(box.querySelector('[data-tile="open"]') as HTMLElement);
    expect(box.querySelector('[data-tile="open"]')?.getAttribute("aria-pressed")).toBe("false");
  });

  it("task 16 — the filter the tile set LEAVES THE BROWSER", async () => {
    // A filter applied in the browser narrows THE PAGE IN HAND — a subset of a
    // subset under an authoritative-looking total, which is worse than no
    // control at all (`DEF-1702`). So the assertion is on the request.
    const { urls, view } = mount();
    await settled(view.container);
    const before = urls.length;
    fireEvent.click(view.container.querySelector('[data-tile="open"]') as HTMLElement);
    await waitFor(() => {
      expect(urls.length).toBeGreaterThan(before);
    });
    expect(urls[urls.length - 1]).toContain("f.state=open");
  });

  it("task 16 — a tile with no served dimension is NOT a button", async () => {
    const { view } = mount();
    const box = view.container;
    await settled(box);
    // *Units awaiting* counts units where every control here selects builds,
    // so it is a fact. A dead button is law 2's mirror and costs more than a
    // missing one.
    expect(box.querySelector('[data-tile="units-awaiting"]')?.tagName.toLowerCase()).toBe("div");
    expect(box.querySelector('[data-tile="open"]')?.tagName.toLowerCase()).toBe("button");
  });

  it("task 22 — the row's `⋮` opens Hold, Waiting on and Cancel", async () => {
    const { view } = mount();
    const box = view.container;
    await settled(box);
    const more = within(box).getByLabelText(t("table.rowActions.more"));
    fireEvent.click(more);
    const menu = more.closest("details") as HTMLElement;
    const words = within(menu)
      .getAllByRole("button")
      .map((button) => button.textContent ?? "");
    expect(words).toHaveLength(3);
    expect(words[0]).toContain("Hold");
    expect(words[1]).toContain("Waiting on");
    expect(words[2]).toContain("Cancel");
  });

  it("task 22 — a CANCELLED build's acts are disabled with Work's own reason", async () => {
    const { view } = mount(payload({ results: [row({ state: "cancelled" })] }));
    const box = view.container;
    await settled(box);
    const menu = within(box)
      .getByLabelText(t("table.rowActions.more"))
      .closest("details") as HTMLElement;
    const items = within(menu).getAllByRole("button");
    expect(items).toHaveLength(3);
    for (const button of items) {
      expect((button as HTMLButtonElement).disabled).toBe(true);
      // Not a hardcoded string: `actBlockedReason` is the function the build
      // page uses and the sentence the SERVICE itself would answer with.
      expect(button.getAttribute("title")).toBe(t("customers.connection.act.whyCancelled"));
    }
  });

  it("task 22 — ticking a row raises the bulk bar with the SAME three acts", async () => {
    const { view } = mount();
    const box = view.container;
    await settled(box);
    expect(box.querySelector("[data-selection-toolbar]")).toBeNull();
    fireEvent.click(within(box).getByLabelText(/CON-26-0117/));
    const bar = box.querySelector("[data-selection-toolbar]") as HTMLElement;
    expect(bar).not.toBeNull();
    // Three acts from ONE list, so a menu and a bar cannot offer different
    // sets of the same feature — plus the bar's own `Clear`.
    expect(bar.querySelectorAll("[data-act]")).toHaveLength(3);
  });
});

// ══════════════════════════════════════════════════════════════════════════
// `DEF-CUS-7804` — THE FIVE FACTS THE SERVER SERVED AND NO SCREEN READ
// ══════════════════════════════════════════════════════════════════════════
//
// `01580d8fc` (2026-09-28) added `customer`, `age_days` + `age_is_accented`,
// `quote_total`/`mode`/`scope`/`raised_by`/`last_stamped_event`,
// `kpis.waiting_on_anyone` and the owed tile's stated absence to
// `GET /connections`. **Not one of them was declared on `ConnectionRow`, so
// not one of them could reach a cell** — `tsc` passed, 24 backend cases
// passed, every gate passed, and the screen rendered exactly what it had
// rendered the day before. That is hard-won law 2, and these cases are what
// goes red if any of the five is un-wired again.
//
// ⚠ **EVERY ONE READS RENDERED OUTPUT, AND EVERY ONE IS MOUNTED UNDER THE
// REAL `/:tenant/accounts` PATTERN** (this file's `mount`). A case that read
// a prop would pass over a cell that is never placed in a column, which is
// the whole defect.
describe("S86 · the five served facts the list now draws (DEF-CUS-7804)", () => {
  it("CUSTOMER draws the name over the account NUMBER, which is not a database id", async () => {
    const { view } = mount();
    const box = view.container;
    await settled(box);
    const cell = box.querySelector("[data-customer-account]") as HTMLElement;
    expect(cell).not.toBeNull();
    expect(cell.textContent).toContain("Jonas Janssen");
    // B14 rule 31 is about the PRIMARY KEY. `AC-2026-00011` is the number a
    // clerk reads down the phone, the same class as `CON-26-0117` beside it.
    expect(cell.textContent).toContain("AC-2026-00011");
    // …and the row id is nowhere on this cell, which is what keeps rule 31
    // rather than merely claiming it.
    expect(cell.textContent).not.toContain("con-0117");
  });

  it("a build with NO owner account reads `no account yet`, never an empty cell", async () => {
    // `connection_reads._row` serves the WHOLE BLOCK as null — *there is no
    // owner yet* is one fact. A blank here and an absent fact read the same
    // way once drawn, which is `DEF-127` one column along.
    const { view } = mount(payload({ results: [row({ customer: null })] }));
    const box = view.container;
    await settled(box);
    const cell = box.querySelector("[data-customer-absent]") as HTMLElement;
    expect(cell).not.toBeNull();
    expect(cell.textContent).toBe("no account yet");
    expect(box.querySelector("[data-customer-account]")).toBeNull();
  });

  it("AGING renders the SERVER's accent, and an unknown accent is drawn apart from a known plain one", async () => {
    // Three renderings, because there are three facts. `null` is *nobody
    // could be asked* — `seams.age_is_accented` returns it when customers
    // publishes no threshold — and answering *not old* for it is `DEF-075`'s
    // substitution on the column a clerk chases work from.
    const accented = mount(payload({ results: [row({ age_days: 41, age_is_accented: true })] }));
    await settled(accented.view.container);
    const hot = accented.view.container.querySelector("[data-age-days]") as HTMLElement;
    expect(hot.getAttribute("data-age-days")).toBe("41");
    expect(hot.getAttribute("data-age-accented")).toBe("true");
    expect(hot.className).toContain("text-accent-700");
    cleanup();

    const plain = mount(payload({ results: [row({ age_days: 16, age_is_accented: false })] }));
    await settled(plain.view.container);
    const cool = plain.view.container.querySelector("[data-age-days]") as HTMLElement;
    expect(cool.getAttribute("data-age-accented")).toBe("false");
    expect(cool.className).not.toContain("text-accent-700");
    cleanup();

    const unknown = mount(payload({ results: [row({ age_days: 16, age_is_accented: null })] }));
    await settled(unknown.view.container);
    const grey = unknown.view.container.querySelector("[data-age-days]") as HTMLElement;
    // ⚠ **THE POINT OF THE CASE: `unknown` IS NOT `false`.** Both draw the
    // number without the accent, so a check reading only the colour would
    // pass over the substitution; the FACT is what is asserted.
    expect(grey.getAttribute("data-age-accented")).toBe("unknown");
    expect(grey.getAttribute("data-age-accented")).not.toBe(cool.getAttribute("data-age-accented"));
    expect(grey.className).not.toBe(cool.className);
  });

  it("the column chooser offers the drawing's five, and `Charged` prints the server's own string", async () => {
    const { view } = mount();
    const box = view.container;
    await settled(box);
    // The README names them: *"Columns chooses the rest: charged, mode,
    // scope, raised by, request number, last event."* They are declared OFF,
    // so the assertion is that the CHOOSER holds them — a column declared
    // nowhere cannot be turned on at all, which was the defect.
    fireEvent.click(within(box).getByLabelText(t("table.columns.open")));
    for (const label of ["Charged", "Mode", "Scope", "Raised by", "Last event"]) {
      expect(within(box).getByLabelText(label, { exact: true })).toBeTruthy();
    }
    fireEvent.click(within(box).getByLabelText("Charged", { exact: true }));
    const charged = box.querySelector("[data-charged]") as HTMLElement;
    // ⚠ **PRINTED, NOT RE-ROUNDED AND NOT MULTIPLIED** (hard rule 2). The
    // server rounded once; `535.00` is its 2-dp string and `stored` is never
    // read here.
    expect(charged.getAttribute("data-charged")).toBe("535.00");
    expect(charged.textContent).toBe("535.00");
  });

  it("an UNPRICED build states the absence and never `$0.00`", async () => {
    // `{stored: null, display: null}` is a build nobody priced — a parked
    // draft always is. `DEF-127`: a fabricated zero *"looks exactly like a
    // settled account"*, and here it would say the customer owes nothing.
    const { view } = mount(
      payload({ results: [row({ quote_total: { stored: null, display: null } })] }),
    );
    const box = view.container;
    await settled(box);
    fireEvent.click(within(box).getByLabelText(t("table.columns.open")));
    fireEvent.click(within(box).getByLabelText("Charged", { exact: true }));
    const cell = box.querySelector("[data-charged-absent]") as HTMLElement;
    expect(cell).not.toBeNull();
    expect(cell.textContent).toBe("Not priced");
    expect(box.querySelector("[data-charged]")).toBeNull();
    const table = box.querySelector("tbody") as HTMLElement;
    expect(table.textContent).not.toContain("0.00");
  });

  it("the OWED tile states its absence and prints no figure at all (DEF-CUS-7619)", async () => {
    const { view } = mount();
    const box = view.container;
    await settled(box);
    const tile = box.querySelector('[data-tile="owed"]') as HTMLElement;
    expect(tile).not.toBeNull();
    const absent = tile.querySelector("[data-owed-absent]") as HTMLElement;
    expect(absent).not.toBeNull();
    // Keyed off the server's CODE, so the sentence moves when the reason does.
    expect(absent.getAttribute("data-owed-code")).toBe(
      "billing_publishes_no_batched_invoice_position",
    );
    expect(absent.getAttribute("data-tracks")).toBe("DEF-CUS-7619");
    // ⚠ **THREE THINGS THIS TILE MAY NOT SAY**, and each has cost something
    // once: a zero (`DEF-127` — *every build is paid for*), a currency the
    // endpoint never served, and the server's two-sentence reason as body
    // copy (B14 rule 33 — rationale is ZERO words on screen; `DEF-742` is the
    // same substitution one register along).
    expect(tile.textContent).not.toContain("0.00");
    expect(tile.textContent).not.toContain("$");
    expect(tile.textContent).not.toContain("a page at a time");
    expect(tile.textContent).toContain("No total yet");
    // And it is a FACT, so it is not a control either.
    expect(tile.tagName.toLowerCase()).toBe("div");
  });

  it("the WAITING ON SOMEONE tile shows the served count and is NOT clickable", async () => {
    const { view } = mount();
    const box = view.container;
    await settled(box);
    const tile = box.querySelector('[data-tile="waiting-anyone"]') as HTMLElement;
    expect(tile).not.toBeNull();
    expect(tile.textContent).toContain("3");
    expect(tile.textContent).toContain("Waiting on someone");
    // ⛔ `f.state` has no *waiting* value — *waiting* is derived from a
    // separate COLUMN and `OQ-371` is the open question about ranking it. A
    // `<button>` here would be law 2's mirror: a live-looking control that
    // either refuses or, worse, applies a filter that means something else.
    expect(tile.tagName.toLowerCase()).toBe("div");
    expect(tile.getAttribute("aria-pressed")).toBeNull();
    expect(tile.getAttribute("data-tile-filter")).toBeNull();
    // The older literal tile has NOT been taken off — it answers a different
    // question and is live (`DEF-CUS-7805` counts the seven against the
    // drawing's five).
    expect(box.querySelector('[data-tile="waiting-inspection"]')).not.toBeNull();
  });
});

// ── Lifecycle ─────────────────────────────────────────────
// packet: CR-150-BRC09 · 05-prototype/new-connect-detail-2026-09-28/00-list.png
// generated: 2026-09-28 by lane LIST
// checklist: A=n/a B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
// exceptions: E4 **jsdom COMPUTES NO LAYOUT, SO NOTHING HERE ASSERTS A PIXEL.**
//         The drawing's spacing and the accent ring on the pressed tile are
//         hard-won law 6's territory — a person, in a browser, beside the
//         drawing — and no check in this repository can stand in for it
// status: VERIFIED-UNRATIFIED
// ──────────────────────────────────────────────────────────

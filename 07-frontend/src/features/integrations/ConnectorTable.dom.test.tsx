// @vitest-environment jsdom
// ── Trace ────────────────────────────────────────────────────────────────
// Change:  PO rulings 2026-09-17 — *"we are overriding the deciion and
//          converting it form Grid -> Table - table only"*, *"Action im
//          looking for - Connect, View, Edit, Keys- based on this status will
//          chnage"* (ratified over the full matrix as *"this is good - please
//          add it"*) and *"Im good with these columes - please implment it"*.
//          Recorded in 12-governance/02-decision-log.md, 2026-09-17.
// Screens: S8 · CON-01. The blueprint draws a CARD GRID (p011–p013) and
//          DECLINED to draw a table (p014); the ruling overrides B14 rule 41,
//          and the supersession is stated in the decision log and in
//          04-docs/05-modules/13-integrations/conformance/.
// Rules:   B14 rule 15 (icons with tooltips in an actions cell, never text
//          links) · rule 20 (ONE table type) · rule 31 (no database id is a
//          visible value) · rule 33 (a LABEL ≤ 3 words) · BR-SHL-025 (a
//          control that cannot act is DISABLED WITH ITS REASON, never hidden)
//          · BR-SHL-013 (the identity column can never be hidden).
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠⚠ **WHAT WOULD MAKE EVERY CHECK IN THIS FILE PASS WRONGLY — WRITTEN OUT
// BEFORE THE ASSERTIONS, BECAUSE A CHECK YOU CANNOT DESCRIBE A FALSE PASS FOR
// IS A CHECK YOU DO NOT UNDERSTAND** (hard-won law 7, habit 2). Five ways, and
// each is closed by name below rather than hoped away:
//
//  1. **ASSERTING A HEADER STRING THAT ALSO APPEARS SOMEWHERE ELSE ON THE
//     SCREEN.** *Direction*, *State* and *Environment* are ALSO the three
//     `+ Filter ▾` group legends on this very screen, and *Environment* is a
//     card fact label as well — so `getByText("Direction")` would pass with no
//     table on the page at all, and `toContain("State")` passes on the old
//     grid. **Closed by reading the headers out of the `<thead>` row only**,
//     as an ordered array of `<th>` text, and asserting the whole sequence.
//  2. **ASSERTING THAT THE ACTIONS CELL RENDERS, WITHOUT ASSERTING WHICH ICONS
//     FOR WHICH STATE.** `queryAllByRole("button")` is non-empty on every row
//     in every state, so *"the row has actions"* is true of a cell that
//     renders the wrong four, the same four everywhere, or four that are all
//     enabled. **Closed by asserting the four accessible NAMES in order AND
//     each one's disabled/enabled state AND, on every disabled one, its
//     `title` — per row, for all seven states.**
//  3. **A FIXTURE WHERE EVERY CONNECTOR IS IN ONE STATE.** The matrix has
//     seven rows and six of them differ only in which side is greyed; a
//     one-state fixture proves one row of it and reads as a full pass.
//     **Closed by `sevenStates()`, which puts ALL SEVEN on the screen at once
//     and asserts each by its own `data-provider`.**
//  4. **THE `Why` COLUMN BEING STRUCTURALLY INCAPABLE OF SHOWING ANYTHING.**
//     It reads `connection.last_test_text`, which is `null` on every row
//     except a failing one — so a fixture with no *Not working* connector in
//     it lets a column that can NEVER render pass every check (law 7's third
//     shape, *incapable of passing*). **Closed by asserting the sentence is
//     PRESENT in the failing row's cell and ABSENT from the working row's**,
//     and, because jsdom cannot prove a browser, by the walkthrough named at
//     the foot of this file.
//  5. **A CELL THAT READS `connection` CRASHING OR INVENTING A VALUE WHEN IT
//     IS `null`.** 12 of the 28 connectors in the demo tenant have no
//     connection at all. A test that only ever renders connected rows proves
//     nothing about the other twelve. **Closed by asserting the three
//     connection-backed cells are EMPTY — not "—", not "OK" — on a
//     `not_set_up` row.**
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@testing-library/jest-dom/vitest";
import "@/i18n";

import type {
  ConnectionRow,
  ConnectionState,
  DisplayState,
  IntegrationsGrid,
  OperationRow,
  ProviderCard,
} from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { IntegrationsTab } from "./IntegrationsTab";

function operation(over: Partial<OperationRow> = {}): OperationRow {
  return {
    name: "send",
    label: "Send",
    description: "Send a bill.",
    direction: "out",
    initiative: "us",
    state: "not_set_up",
    last_run_at: null,
    last_outcome: null,
    trace_id: null,
    test_action: null,
    test_needs_recipient: false,
    trigger: "manual",
    endpoint: null,
    rate_limit_per_minute: null,
    executor: "server",
    latency_budget_ms: null,
    result_disposition: null,
    ...over,
  } as OperationRow;
}

function connection(over: Partial<ConnectionRow> = {}): ConnectionRow {
  return {
    id: "c0ffee00-0000-4000-8000-000000000001",
    label: null,
    describe: "billing@•••.example",
    settings: {},
    connected_by: "Dana Reyes",
    environment: "production",
    status: "working",
    enabled: true,
    cadence: "nightly",
    next_run_at: null,
    last_test_at: "2026-09-16T06:14:00Z",
    last_test_ok: true,
    last_test_text: null,
    connected_at: "2026-09-01T09:00:00Z",
    credential: null,
    expiry: { state: "ok", expires_at: null, days_left: null, window_days: 30, version: 1 },
    ...over,
  } as ConnectionRow;
}

function card(over: Partial<ProviderCard> = {}): ProviderCard {
  const state: ConnectionState = (over.state ?? "not_set_up") as ConnectionState;
  return {
    key: "email_smtp",
    category: "email",
    display_name: "Custom SMTP",
    summary: "Send bills from this utility's own mail server.",
    fields: [{ name: "host", label: "Mail server", kind: "host", required: true, options: [] }],
    disposition: { kind: "live", wave: null, phase: 1 },
    kicker: { direction: "out", initiative: "us" },
    auth: { mode: "password", placement: "header" },
    codecs: [],
    adapter_registered: true,
    connection: null,
    connections: [],
    vocabularies: [],
    credentials: [],
    disconnect: null,
    issued_keys: [],
    state,
    display_state: (over.display_state ?? state) as DisplayState,
    operations: [operation({ state })],
    ...over,
  } as ProviderCard;
}

function grid(providers: ProviderCard[]): IntegrationsGrid {
  const categories = [...new Set(providers.map((one) => one.category))].map((key) => ({ key }));
  return {
    categories,
    providers,
    counts: {
      providers: providers.length,
      connected: providers.filter((one) => one.connection !== null).length,
    },
  } as IntegrationsGrid;
}

/**
 * ⚠ **ALL SEVEN MATRIX ROWS ON THE SCREEN AT ONCE — false-pass 3.** Six of the
 * seven differ only in which half of the actions cell is greyed, so a fixture
 * carrying one state proves one row of a seven-row ruling and reads exactly
 * like a full pass.
 */
function sevenStates(): ProviderCard[] {
  return [
    card({ key: "s_not_set_up", display_state: "not_set_up", state: "not_set_up" }),
    card({
      key: "s_untested",
      display_state: "untested",
      state: "untested",
      connection: connection({ status: "untested", last_test_ok: null }),
    }),
    card({
      key: "s_working",
      display_state: "working",
      state: "working",
      connection: connection(),
      operations: [operation({ state: "working", last_run_at: "2026-09-16T06:14:00Z" })],
    }),
    card({
      key: "s_not_working",
      display_state: "not_working",
      state: "not_working",
      connection: connection({
        status: "not_working",
        last_test_ok: false,
        last_test_text: "the mail server is not answering",
      }),
      operations: [operation({ state: "not_working" })],
    }),
    card({
      key: "s_off",
      display_state: "off",
      state: "off",
      connection: connection({ status: "off", enabled: false }),
    }),
    card({
      key: "s_reading_from_us",
      // ⚠ `reading_from_us` IS A *DISPLAY* STATE AND NOT A STORED ONE — the
      // server COMPUTES it for a connection whose every operation is the
      // partner's read. `state` is the stored `ConnectionState`, so the
      // fixture stores `working` and displays the computed word, which is what
      // the wire actually carries.
      display_state: "reading_from_us",
      state: "working",
      kicker: { direction: "out", initiative: "them" },
      connection: connection({ status: "working" }),
      operations: [operation({ direction: "out", initiative: "them", state: "working" })],
    }),
    card({
      key: "s_coming_soon",
      display_state: "not_set_up",
      state: "not_set_up",
      disposition: { kind: "coming_soon", wave: "v2", phase: null },
    }),
  ];
}

function draw(providers: ProviderCard[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.integrations, grid(providers));
  // ⚠ MOUNTED UNDER THE REAL PATH PATTERN (hard-won law 2's fixture clause).
  // A bare MemoryRouter leaves `useParams().tenant` undefined, so every address
  // the screen builds comes out `//settings/...` — a protocol-relative URL to
  // another host, which reads as a perfectly good string to `toContain`.
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/brazosbend/settings/integrations"]}>
          <Routes>
            <Route path="/:tenant/settings/integrations" element={<IntegrationsTab />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

/**
 * The `<tr>` for one connector.
 *
 * ⚠ **`data-provider` IS ON THE IDENTITY CELL AND NOT ON THE ROW, SO THIS
 * WALKS UP.** `DataTable` owns the `<tr>` and deliberately puts nothing of a
 * consumer's on it, which is why every screen in this product hangs its row
 * identity off the identity cell. A test that stopped at the `[data-provider]`
 * span would be asserting against ONE CELL while reading like it asserts
 * against a row — every *the row has no X* check would pass vacuously.
 */
function rowFor(container: HTMLElement, key: string): HTMLElement {
  const marker = container.querySelector<HTMLElement>(`[data-provider="${key}"]`);
  expect(marker, `no row for ${key}`).not.toBeNull();
  const row = (marker as HTMLElement).closest("tr");
  expect(row, `${key} is not inside a table row`).not.toBeNull();
  return row as HTMLElement;
}

/**
 * The four actions of a row, in the DOM order the ruling fixes.
 *
 * ⚠ **`button, a` AND NOT `button` — AND THE DIFFERENCE IS ITSELF AN
 * ASSERTION.** All four acts NAVIGATE, so `RowActionLink` renders a LIVE one
 * as a real `<a>` (middle-click and *open in new tab* keep working) and a
 * BLOCKED one as a `<button disabled>` carrying the reason, because a disabled
 * link is not a thing the platform has. A helper that collected only buttons
 * would silently see three of the four on every connected row and report
 * *four icons* as *one icon* — which is why `enabled()` below reads the TAG.
 */
function actionsOf(row: HTMLElement): HTMLElement[] {
  const cell = row.querySelector<HTMLElement>("[data-row-actions]");
  expect(cell, "the row has no actions cell").not.toBeNull();
  return Array.from((cell as HTMLElement).querySelectorAll<HTMLElement>("button, a"));
}

/** Live = a real link. Greyed = a disabled button. Nothing else is legal here. */
function enabled(node: HTMLElement): boolean {
  if (node.tagName === "A") return true;
  expect(node.tagName, "an action is neither a link nor a button").toBe("BUTTON");
  expect((node as HTMLButtonElement).disabled, "a <button> action must be the GREYED one").toBe(
    true,
  );
  return false;
}

describe("CON-01 is a TABLE — the PO override of 2026-09-17", () => {
  // ── false-pass 1 is closed here ────────────────────────────────────────
  // *Direction*, *State* and *Environment* are ALSO the `+ Filter ▾` legends
  // on this screen, so any whole-document text query for them passes with no
  // table present. The headers are read out of the header row alone, as an
  // ORDERED list, so a right set in a wrong order fails too.
  it("draws ONE table with the ten ruled columns, in order", () => {
    const { container } = draw(sevenStates());

    const table = container.querySelector("table");
    expect(table, "the screen renders no table at all").not.toBeNull();
    // B14 rule 20 — ONE table type. Two tables here would mean the card grid
    // survived beside it, which is exactly what *"table only"* forbids.
    expect(container.querySelectorAll("table")).toHaveLength(1);

    const headers = Array.from(
      (table as HTMLTableElement).querySelectorAll("thead th"),
    ).map((th) => (th.textContent ?? "").trim());

    expect(headers).toEqual([
      "Connector",
      "Category",
      "Direction",
      "State",
      "APIs",
      "Environment",
      "Where",
      "Last run",
      "Why",
      "Actions",
    ]);
  });

  it("the cards are GONE — *table only* means no grid behind a toggle", () => {
    const { container } = draw(sevenStates());
    expect(container.querySelector('[data-testid="integrations-grid"]')).toBeNull();
    // `Panel` stamps `data-panel` and nothing else does, so this cannot be
    // faked by a class rename (the reasoning IntegrationsTabPanel.dom.test.tsx
    // already records). Seven connector cards would stamp seven of them.
    expect(container.querySelectorAll("[data-panel]")).toHaveLength(0);
  });

  // ── false-pass 2 and 3 are closed here ─────────────────────────────────
  // Every one of the seven matrix rows is asserted by NAME, by ENABLEMENT and,
  // where greyed, by the exact REASON the PO read. A cell rendering the same
  // four enabled icons on every row would pass *"the row has actions"* and
  // fails every line below.
  it.each([
    ["s_not_set_up", true, "Not connected yet"],
    ["s_untested", false, "Already connected"],
    ["s_working", false, "Already connected"],
    ["s_not_working", false, "Already connected"],
    // ⚠ **`s_off` LEFT THIS TABLE ON 2026-09-17 — SEE THE CASE BELOW.** The PO
    // ruled *"if it is disconnected- then you give a connect option"*
    // (`DEF-INT-5658`), and a disconnected connector is the ONE state where
    // BOTH sides of the cell are live: Connect, because there is no live
    // connection to duplicate, AND View/Edit/Keys, because the row is still
    // there — which is the whole reason `US-INT-025` keeps it. It therefore
    // cannot be asserted by this table, whose invariant is *exactly one side*.
    ["s_reading_from_us", false, "Already connected"],
  ] as const)(
    "%s: four icons, always, and Connect is %s",
    (key, connectEnabled, connectReason) => {
      const { container } = draw(sevenStates());
      const buttons = actionsOf(rowFor(container, key));

      expect(buttons.map((one) => one.getAttribute("aria-label"))).toEqual([
        "Connect",
        "View",
        "Edit",
        "Keys",
      ]);

      const [connect, ...rest] = buttons;
      expect(enabled(connect)).toBe(connectEnabled);
      if (connectEnabled) {
        // Point 3 of the ruling: an ENABLED icon's tooltip is the action word
        // alone. The reason strings belong to greyed icons and nowhere else.
        expect(connect).toHaveAttribute("title", "Connect");
      } else {
        expect(connect).toHaveAttribute("title", connectReason);
      }

      for (const one of rest) {
        // The mirror of Connect, on every one of the six: exactly one side of
        // the cell is live, and it is never both and never neither.
        expect(enabled(one)).toBe(!connectEnabled);
        if (connectEnabled) {
          // Not set up: View, Edit and Keys are greyed and each says why.
          expect(one).toHaveAttribute("title", "Not connected yet");
        } else {
          expect(one).toHaveAttribute("title", one.getAttribute("aria-label"));
        }
      }
    },
  );

  /**
   * ⚠ **THE ONE ROW WHERE BOTH SIDES OF THE CELL ARE LIVE — AND IT SUPERSEDES
   * A MATRIX RATIFIED THE SAME DAY.**
   *
   * The table above encodes the CON-01 ruling of 2026-09-17: *exactly one side
   * of the cell is live, and it is never both and never neither*. That held
   * for all six states as drawn. It stopped holding for `off` when the PO
   * ruled, later the same day: **"if it is disconnected- then you give a
   * connect option - can we do it"** (`DEF-INT-5658`).
   *
   * **Both halves are needed and neither is optional.** Connect, because the
   * server has always permitted it — `connect_with_fields` refuses only when
   * `existing.enabled or _has_active_credential(existing)`, and a disconnected
   * row is neither, so `_reconnect` was written and unreachable. View, Edit and
   * Keys, because the row survives a disconnect precisely so its history can be
   * read (`US-INT-025`); taking them away to preserve the invariant would fix
   * the matrix by breaking the reason the row exists.
   *
   * ⚠ **THE SUPERSESSION IS STATED RATHER THAN ASSUMED** (change process step
   * 2). What a clerk met before this: a card reading **● Turned off** in State
   * and **Already connected** on Connect — two statements about one row that
   * cannot both be true — with Edit accepting every field and silently leaving
   * the credential null, and a key rotation answering `409`. Every way back in
   * was shut, and the one that appeared to work did nothing.
   */
  it("s_off: BOTH sides live — Connect returns, and the row stays readable", () => {
    const { container } = draw(sevenStates());
    const buttons = actionsOf(rowFor(container, "s_off"));
    expect(buttons.map((one) => one.getAttribute("aria-label"))).toEqual([
      "Connect",
      "View",
      "Edit",
      "Keys",
    ]);
    for (const one of buttons) {
      expect(enabled(one)).toBe(true);
      // Point 3 of the CON-01 ruling still holds: an ENABLED icon's tooltip is
      // the action word alone. A reason string belongs to a greyed icon.
      expect(one).toHaveAttribute("title", one.getAttribute("aria-label"));
    }
  });

  it("coming soon: all four are greyed, and all four say *Not built yet*", () => {
    const { container } = draw(sevenStates());
    const buttons = actionsOf(rowFor(container, "s_coming_soon"));
    expect(buttons.map((one) => one.getAttribute("aria-label"))).toEqual([
      "Connect",
      "View",
      "Edit",
      "Keys",
    ]);
    for (const one of buttons) {
      expect(enabled(one)).toBe(false);
      expect(one).toHaveAttribute("title", "Not built yet");
    }
  });

  // ⚠ NOT A RESTATEMENT OF THE TWO ABOVE. Those assert the matrix; this
  // asserts the INVARIANT under it — the thing a future lane would break by
  // "tidying" a greyed icon away. The PO's own reason: *"A row where the icons
  // move around is a row people have to re-read"*.
  it("EVERY row has exactly four action buttons, whatever its state", () => {
    const { container } = draw(sevenStates());
    for (const one of sevenStates()) {
      expect(actionsOf(rowFor(container, one.key))).toHaveLength(4);
    }
  });

  it("no greyed icon is ever silent (BR-SHL-025)", () => {
    const { container } = draw(sevenStates());
    const greyed = Array.from(
      container.querySelectorAll<HTMLButtonElement>("[data-row-actions] button"),
    ).filter((one) => one.disabled);
    // ⚠ **THE EXACT NUMBER, AND IT IS WORTH THE ARITHMETIC.** On this fixture:
    // 3 greyed on the *Not set up* row (View · Edit · Keys), ONE on each of the
    // FOUR still-connected rows (Connect), NONE on the disconnected row, and 4
    // on the coming-soon row — 11 of the 28 icons. A `toBeGreaterThan(0)` here
    // would pass on a cell that greyed everything, which is the same class of
    // check as *the row has actions*. The first draft of this line said 22,
    // from miscounting the connected rows as three greyed each; the count is
    // what caught it.
    //
    // ⚠ **12 → 11 ON 2026-09-17 (`DEF-INT-5658`), AND THE MISSING ONE IS THE
    // WHOLE FIX.** `s_off`'s Connect was the twelfth greyed icon, reading
    // *"Already connected"* on a row whose State column said *"● Turned off"*.
    // The PO ruled *"if it is disconnected- then you give a connect option"*,
    // so that icon is live and the disconnected row now greys nothing at all —
    // the only row on this fixture that does. **Changing this number without
    // changing that behaviour is how a count stops being a check.**
    expect(greyed).toHaveLength(11);
    for (const one of greyed) {
      expect(one.getAttribute("title")).toBeTruthy();
    }
  });

  // ── false-pass 4 is closed here ────────────────────────────────────────
  it("Why carries the failure sentence, and ONLY on a failing row", () => {
    const { container } = draw(sevenStates());
    const failing = rowFor(container, "s_not_working");
    expect(within(failing).getByText("the mail server is not answering")).toBeInTheDocument();

    const working = rowFor(container, "s_working");
    expect(within(working).queryByText("the mail server is not answering")).toBeNull();
    // Not "—" and not "OK": the column exists to be SCANNED FOR RED, so a
    // filler character on every healthy row defeats its whole purpose.
    const whyCell = working.querySelector<HTMLElement>('[data-cell="why"]');
    expect(whyCell, "no Why cell on the working row").not.toBeNull();
    expect((whyCell as HTMLElement).textContent).toBe("");
  });

  // ── false-pass 5 is closed here ────────────────────────────────────────
  it("a row with no connection draws EMPTY cells, not a fabricated value", () => {
    const { container } = draw(sevenStates());
    const row = rowFor(container, "s_not_set_up");
    for (const cell of ["environment", "where", "why"]) {
      const node = row.querySelector<HTMLElement>(`[data-cell="${cell}"]`);
      expect(node, `no ${cell} cell`).not.toBeNull();
      expect((node as HTMLElement).textContent).toBe("");
    }
  });

  it("Direction turns two enum fields into the four drawn words", () => {
    const { container } = draw([
      card({ key: "d_we_send", kicker: { direction: "out", initiative: "us" } }),
      card({ key: "d_we_collect", kicker: { direction: "in", initiative: "us" } }),
      card({ key: "d_they_send", kicker: { direction: "in", initiative: "them" } }),
      card({ key: "d_they_read", kicker: { direction: "out", initiative: "them" } }),
    ]);
    const word = (key: string) =>
      rowFor(container, key).querySelector<HTMLElement>('[data-cell="direction"]')?.textContent;

    expect(word("d_we_send")).toBe("We send");
    expect(word("d_we_collect")).toBe("We collect");
    expect(word("d_they_send")).toBe("They send");
    expect(word("d_they_read")).toBe("They read");
    // B14 rule 31 in spirit: the stored enum never reaches the screen.
    expect(container.textContent).not.toContain("them.out");
  });

  it("APIs reads `16 · 14 working`, and a bare count before anything has run", () => {
    const sixteen = Array.from({ length: 16 }, (_, index) =>
      operation({
        name: `read_${index + 1}`,
        label: `Meter read ${index + 1}`,
        state: index < 14 ? "working" : "not_working",
      }),
    );
    const { container } = draw([
      card({
        key: "meters_neptune360",
        display_name: "Neptune 360",
        display_state: "not_working",
        state: "not_working",
        connection: connection({ status: "not_working", last_test_ok: false }),
        operations: sixteen,
      }),
      card({ key: "untested_one", display_state: "untested", state: "untested" }),
    ]);

    const apis = (key: string) =>
      rowFor(container, key).querySelector<HTMLElement>('[data-cell="apis"]')?.textContent;

    // The whole cell, not a substring: "16" alone would pass on a cell that
    // lost the working half, and "16 APIs" is what the CARD said.
    expect(apis("meters_neptune360")).toBe("16 · 14 working");
    // *has this been tested*, not *is working above zero* — the discriminator
    // the decision log of 2026-09-16 already settled and this move keeps.
    expect(apis("untested_one")).toBe("1");
    // The per-API list must not come back with the extra room a row has.
    expect(container.textContent).not.toContain("Meter read 1");
  });

  it("Last run shows the NEWEST operation's run, and nothing when none has run", () => {
    const { container } = draw([
      card({
        key: "many_runs",
        display_state: "working",
        state: "working",
        connection: connection(),
        operations: [
          operation({ name: "a", state: "working", last_run_at: "2026-09-10T08:00:00Z" }),
          operation({ name: "b", state: "working", last_run_at: "2026-09-16T06:14:00Z" }),
          operation({ name: "c", state: "working", last_run_at: null }),
        ],
      }),
      card({ key: "never_run", display_state: "untested", state: "untested" }),
    ]);
    const cell = (key: string) =>
      rowFor(container, key).querySelector<HTMLElement>('[data-cell="lastRun"]')?.textContent ?? "";

    // The NEWEST, not the first in the array and not the last.
    expect(cell("many_runs")).toContain("09/16/2026");
    expect(cell("many_runs")).not.toContain("09/10/2026");
    expect(cell("never_run")).toBe("");
  });

  it("no database id reaches a cell (B14 rule 31)", () => {
    const { container } = draw(sevenStates());
    expect(container.textContent).not.toContain("c0ffee00-0000-4000-8000-000000000001");
  });
});

// ── Lifecycle ────────────────────────────────────────────────────────────
// ⚠ **JSDOM COMPUTES NO LAYOUT AND NO CASCADE, SO NOTHING HERE PROVES THE
// SCREEN.** Ten columns that do not fit at 1280, a header that wraps, a `Why`
// column that is empty on every row of the REAL demo tenant — none of that can
// fail in this file. Hard-won law 6: that half is
// `10-scripts/con01_connector_table_walkthrough.mjs`, run against the booted
// stack at 1280 and 1440.
// ─────────────────────────────────────────────────────────────────────────

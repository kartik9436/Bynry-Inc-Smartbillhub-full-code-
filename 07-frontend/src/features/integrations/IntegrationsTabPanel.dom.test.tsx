// @vitest-environment jsdom
// ── Trace ────────────────────────────────────────────────────────────────
// Defect:  DEF-INT-5497 — the connector card was a hand-rolled `<article>`
//          with `border border-neutral-200 bg-bg`: no accent rule on its top
//          edge, a border colour no other panel in the product uses, and a
//          background byte-identical to the page. PO, on the running build:
//          *"panel class for each card - 28 conenctor is not correct - we are
//          using panel -accest something"*, then *"see there is a line on top
//          and color to card - panel ui is not correct"*.
//          DEF-INT-5498 — the toolbar shipped two of UI-RULES 12's four parts.
//          DEF-INT-5499 — the footnote printed one of the two counts the
//          server sends.
// Rules:   UI-RULES 12 (one toolbar in four parts) · B14 rule 36 (the kit owns
//          a visual decision) · PO standing ruling 2026-09-16, *"i want you to
//          use panel with acsent - where ever shown it that way"*.
// ─────────────────────────────────────────────────────────────────────────
//
// ⚠ **THIS ASSERTS THE CARD *IS* A `Panel`, NOT THAT A CLASS STRING IS PRESENT,
// AND THE DIFFERENCE IS WHY THE DEFECT SURVIVED.** `Panel.tsx`'s own docstring
// records the trap: `border-width` and `border-top-width` are DIFFERENT CSS
// properties that COMPOSE rather than race, so a card can carry every accent
// class a grep would look for and still render a 1px divider — *"2px accent
// quietly becoming 1px divider, and nothing else in the repo would have"* caught
// it. A `toContain("border-t-2")` passes on a card that renders grey.
//
// So the reference is COMPUTED: a real `<Panel accent>` is rendered beside the
// grid and the card is required to carry every class token that Panel itself
// emitted. Change `ACCENT`, change `panelClasses`, rename `bg-surface` — the
// reference moves and the assertion moves with it, which a literal string can
// never do. `data-panel` is the second half and it is the one that cannot be
// faked by copying classes: only `Panel` writes that attribute.
//
// ⚠ **AND THE PIXELS ARE STILL NOT PROVED HERE.** jsdom computes no layout and
// no cascade, so the browser half — a 2px top border in the accent colour over a
// surface that is NOT the page background — is
// `10-scripts/def_int_5497_connector_panel_walkthrough.mjs`, which reads
// `getComputedStyle` off the running product. Hard-won law 6: no gate in this
// repo reads rendered output, and this file is not an exception to that.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import "@testing-library/jest-dom/vitest";
import "@/i18n";

import type { IntegrationsGrid, OperationRow, ProviderCard } from "@/api/integrationsEndpoints";
import { queryKeys } from "@/api/queryClient";
import { ToastProvider } from "@/components/Toast";

import { IntegrationsTab } from "./IntegrationsTab";

function operation(over: Partial<OperationRow> = {}): OperationRow {
  return {
    name: "send",
    label: "Send",
    description: "Send bills from this mailbox.",
    direction: "out",
    initiative: "us",
    state: "not_set_up",
    last_run_at: null,
    last_outcome: null,
    trace_id: null,
    test_action: "Send one real message to an address you type.",
    test_needs_recipient: true,
    executor: "server",
    latency_budget_ms: null,
    result_disposition: null,
    ...over,
  };
}

function card(over: Partial<ProviderCard> = {}): ProviderCard {
  return {
    key: "email_smtp",
    category: "email",
    display_name: "Custom SMTP",
    summary: "Send bills from this utility's own mail server.",
    fields: [],
    disposition: { kind: "live", wave: null, phase: 1 },
    kicker: { direction: "out", initiative: "us" },
    auth: { mode: "password", placement: "header" },
    codecs: [],
    adapter_registered: true,
    connection: null,
    connections: [],
    vocabularies: [],
    state: "not_set_up",
    display_state: "not_set_up",
    operations: [operation()],
    ...over,
  } as ProviderCard;
}

function grid(over: Partial<IntegrationsGrid> = {}): IntegrationsGrid {
  const providers = over.providers ?? [card()];
  return {
    categories: over.categories ?? [{ key: "email" }],
    providers,
    counts: over.counts ?? { providers: providers.length, connected: 0 },
    ...over,
  };
}

/**
 * ⚠ MOUNTED UNDER THE REAL PATH PATTERN, never a bare `MemoryRouter`. A routed
 * component with no `/:tenant/...` route leaves `useParams().tenant` undefined,
 * so every address the screen builds comes out `//settings/...` — a
 * protocol-relative URL to another host that reads as a perfectly good string to
 * `toContain` (hard-won law 2's fixture clause).
 */
function mount(data: IntegrationsGrid) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  queryClient.setQueryData(queryKeys.integrations, data);
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

describe("DEF-INT-5497 — RETIRED by the grid→table override of 2026-09-17", () => {
  // ⚠⚠ **THIS BLOCK USED TO ASSERT THAT EVERY CONNECTOR CARD *IS* A `Panel`
  // WITH THE ACCENT RULE, AND THERE ARE NO CARDS ANY MORE.** PO ruling
  // 2026-09-17: *"we are overriding the deciion and converting it form Grid ->
  // Table - table only"*. Four cases went with the cards — rendered through
  // `Panel`, carries `panelAccentClasses()`, the element is an `<article>`,
  // and the retired hand-rolled border is gone.
  //
  // ⚠ **THEY ARE RECORDED HERE RATHER THAN DELETED, BECAUSE A TEST THAT
  // VANISHES LOOKS EXACTLY LIKE A TEST THAT WAS NEVER WRITTEN.** `DEF-INT-5497`
  // was a real defect — the Product Owner read a missing accent rule and a
  // page-coloured surface off the running build — and the next reader needs to
  // know its cases were superseded by a ruling rather than quietly dropped to
  // get a suite green.
  //
  // ⚠ **THE PO's STANDING PANEL RULING IS *NOT* SUPERSEDED**, only its
  // application to this screen. *"i want you to use panel with acsent - where
  // ever shown it that way"* still governs every screen that DRAWS a panel;
  // `CON-01` simply no longer draws one, because a table row is not a panel and
  // wrapping each of twenty-eight rows in one would be a second table type
  // (B14 rule 20).
  //
  // What replaced the four cases is `ConnectorTable.dom.test.tsx`, which
  // asserts the ten ruled columns and the four ruled actions. The one line
  // worth keeping HERE is the negative, because it is the only place that would
  // notice the cards CREEPING BACK beside the table.
  it("negative · no connector is drawn as a Panel any more", () => {
    const { container } = mount(grid({ providers: [card(), card({ key: "email_microsoft" })] }));
    // Only `Panel` writes `data-panel`, which is why this cannot be faked by a
    // class rename — the reasoning this file already recorded for the positive.
    expect(container.querySelectorAll("[data-panel]")).toHaveLength(0);
    expect(container.querySelector("table")).not.toBeNull();
  });
});

describe("DEF-INT-5498 — the toolbar is UI-RULES 12's four parts", () => {
  it("draws the search box, the category chips, + Filter and the column chooser", () => {
    const { container } = mount(
      grid({
        categories: [{ key: "email" }, { key: "erp" }],
        providers: [card(), card({ key: "erp_sap", category: "erp" })],
      }),
    );
    // ⚠ **THE FOUR PARTS ARE STILL FOUR, AND THREE OF THEM ARE THE KIT'S NOW
    // (grid→table, 2026-09-17).** This screen hand-rolled its search box
    // (`data-integrations-search`) and wrapped `FilterBar` in its own group
    // (`data-connector-filter`); `DataTable` draws the search, the `+ Filter ▾`
    // panel and the `▦` chooser from the declaration, so the markers moved from
    // this screen's own attributes to the kit's roles and labels. **The
    // assertion got STRONGER, not weaker**: a role and an accessible name are
    // what a clerk and a screen reader actually use, and a `data-` attribute
    // can be present on a control that renders nothing.
    //
    // ① search — the kit's box, carrying THIS list's own rule-19 prompt.
    expect(container.querySelector('input[type="search"]')).not.toBeNull();
    expect(
      container.querySelector('input[type="search"]')?.getAttribute("aria-label"),
    ).toBe("Search services…");
    // ④ chips — still this screen's, still generated from the registry.
    expect(container.querySelectorAll("[data-category]").length).toBeGreaterThan(1);
    // ② + Filter ▾ — handed to `DataTable` as `filterBarSlot`.
    expect(container.textContent).toContain("Filter");
    // ⚠ SCOPED TO THIS RENDER'S CONTAINER, NEVER `getByLabelText`. There is no
    // global `setupFiles` in this project (vite.config.ts says so on purpose),
    // so Testing Library's auto-cleanup never registers and a document-wide
    // query sees every earlier test's markup too — it found the chooser TWICE
    // and failed on a screen that was correct.
    expect(container.querySelector('[aria-label="Show or hide columns"]')).not.toBeNull();
  });

  it("offers filter dimensions GENERATED from the cards, never a typed list", () => {
    const { container } = mount(
      grid({
        providers: [
          card({ key: "email_smtp", kicker: { direction: "out", initiative: "us" } }),
          card({ key: "meters_itron", kicker: { direction: "in", initiative: "us" } }),
        ],
      }),
    );
    // ⚠ **SCOPED TO `FilterBar`'s OWN `<details>` PANEL, NOT TO THE TOOLBAR
    // AND NOT TO THE SCREEN.** *We send* and *We collect* are now also the
    // values of the DIRECTION COLUMN on every row, so any wider scope — the
    // container, the section, the toolbar's parent — makes all three
    // assertions below pass off the TABLE BODY with no filter panel rendered
    // at all. That is the *asserting a string that also appears somewhere
    // else* false pass, and this screen grew a second source of those strings
    // on the day it became a table.
    const panel = container.querySelector("details");
    expect(panel, "no + Filter panel").not.toBeNull();
    const text = (panel as Element).textContent ?? "";
    expect(text).toContain("We send");
    expect(text).toContain("We collect");
    // Nothing the loaded cards do not have — the chips' own rule (BR-INT-037).
    expect(text).not.toContain("They read");
  });
});

describe("DEF-INT-5499 — the footnote prints both counts", () => {
  it("says how many connectors there are AND how many are connected", () => {
    const { container } = mount(
      grid({
        providers: [card(), card({ key: "email_microsoft" })],
        counts: { providers: 28, connected: 11 },
      }),
    );
    const text = container.textContent ?? "";
    expect(text).toContain("28 connectors · 11 connected.");
    expect(text).toContain("Showing every category.");
    expect(text).not.toContain("services you can connect");
  });
});

describe("DEF-INT-5500 — no category reaches a clerk as its raw key", () => {
  it("renders the ERP chip and the ERP kicker as a word", () => {
    const { container } = mount(
      grid({
        categories: [{ key: "erp" }],
        providers: [card({ key: "erp_sap", category: "erp" })],
      }),
    );
    const text = container.textContent ?? "";
    expect(text).not.toContain("integrations.category.");
    expect(text).toContain("ERP");
  });
});

// ── Lifecycle ────────────────────────────────────────────────────────────
// packet: DEF-INT-5497 · DEF-INT-5498 · DEF-INT-5499 · DEF-INT-5500 (CR-110-BRC04)
// generated: 2026-09-16 by the CR-110 maintenance lane
// checklist: A=n/a B=n/a C✔ D=n/a E✔ F✔ G✔ H=n/a
// gates: proved RED against the pre-fix component in `npx vitest run` — the harness that runs it — before a line of the fix was written
// exceptions: none
// status: VERIFIED-UNRATIFIED
// ─────────────────────────────────────────────────────────────────────────

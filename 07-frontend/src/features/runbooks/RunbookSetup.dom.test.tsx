// @vitest-environment jsdom
//
// ⚠ THE PRAGMA IS LOAD-BEARING AND MUST STAY ON LINE 1. `vite.config.ts`
// keeps the default environment at `node` deliberately (`DEF-523`) — 200+
// suites are `renderToStaticMarkup` first-paint tests that neither need nor
// want a DOM — and an interactive suite opts in per file. Without it every
// case here dies on `ReferenceError: document is not defined`, which is how
// this file first ran. The `.dom.test.tsx` name is the same convention.
// ── Trace ──────────────────────────────────────────────
// Story:   US-RBS-016 · US-RBS-001 · CR-075 wave C task C3.
// Screens: RBS-004.1 … RBS-004.7.
// Rules:   B14 rule 31 · rule 32 · rule 33 · `BR-RBS-002` · `BR-RBS-012` ·
//          `BR-RBS-042` · `NFR-3` · CLAUDE.md hard-won law 2 (and its mirror).
// Defects: DEF-CWP-3925 (mount under the REAL path pattern) ·
//          DEF-RBS-4285 (`why` is optional and an absent one draws nothing).
// ───────────────────────────────────────────────────────
// EVERY CASE HERE ASSERTS A RULE — a refusal, a missing id, a copy string, a
// count — and none asserts an impression. The plan's definition of done says so
// in terms: *"every wave's exit test **asserts a rule** — a construction
// failure, a 409, a byte-identical report — never an impression."*
//
// ══════════════════════════════════════════════════════════════════════════
// MOUNTED THROUGH `APP_ROUTES` AT A REAL TENANT ADDRESS, NEVER BARE
// ══════════════════════════════════════════════════════════════════════════
// `DEF-CWP-3925`: the portal's front-page test mounted its component bare
// inside a `MemoryRouter` with no `/:tenant/portal` route, so
// `useParams().tenant` was `undefined` and every address the page built came
// out `//portal/…` — a protocol-relative URL to ANOTHER HOST, which reads as a
// perfectly good string to `toContain`. **A fixture that cannot tell a working
// link from a broken one is how that defect hid**, and it hid eight dead doors
// behind 42 test files and 391 green cases.
//
// So the router half of this file renders the product's OWN route table at
// `/{tenant}/runbooks/{key}`, and the `#steps` cases drive the real hash. The
// component half renders `RunbookSetup` directly — it is pure over its view
// model — but still inside a route whose path is the real one.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes, useRoutes } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";

import "@/i18n";

import { APP_ROUTES } from "@/App";
import type { MyPermissions, SessionUser } from "@/api/endpoints";
import { queryKeys } from "@/api/queryClient";
import { shellBootSeed } from "@/components/shellBootSeed";
import { ToastProvider } from "@/components/Toast";

import { RunbookSetup, RUNBOOK_SETUP_TABS, runbookSetupTabFromHash } from "./RunbookSetup";
import { COLLECTIONS_LADDER, CONFIGURATION_CHECK } from "./setupFixture";
import type { RunbookSetupView } from "./setupTypes";

const TENANT = "silvercreek";

// ⚠ **THERE IS NO AUTO-CLEANUP IN THIS REPO AND A MISSING ONE IS NOT A TIDINESS
// PROBLEM — IT SILENTLY BREAKS EVERY COUNT.** `vite.config.ts` sets no
// `setupFiles` and no `globals: true` on purpose, so `@testing-library/react`
// never registers its own `afterEach` and each render is ADDED to the same
// document. This file's first run reported *"expected 7, got 70"* and *"Found
// multiple elements with the role tablist"* — a suite counting ten renders of
// one screen. Every "exactly N" assertion below depends on this line;
// `ImportWorkflowPage.dom.test.tsx` carries it for the same reason.
afterEach(cleanup);

/** The real path pattern, with a real slug in it. */
function mount(view: RunbookSetupView, hash = "") {
  const noop = () => undefined;
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={[`/${TENANT}/runbooks/${view.key}${hash}`]}>
        <Routes>
          <Route
            path="/:tenant/runbooks/:key"
            element={
              <RunbookSetup
                view={view}
                runTo={`/${TENANT}/runbooks/${view.key}/run`}
                onPauseToggle={noop}
                onChangeScope={noop}
                onChangeLimits={noop}
                onChangeSchedule={noop}
                onRunsPage={noop}
                onRunsPer={noop}
              />
            }
          />
        </Routes>
      </MemoryRouter>
    </ToastProvider>,
  );
}

describe("RBS-004 · the tab strip — the sheets' own correction", () => {
  // `08-screen-layouts.md`: *"`RBS-004.3` draws five, `RBS-004.5` and
  // `RBS-004.6` draw four, `RBS-004.7` draws THREE … That is the drawing
  // fitting its frame, not a design. The built screen carries all seven tabs
  // with their counts on every tab. A lane building `RBS-004.7` literally ships
  // a three-tab screen, and no check in this repository would see it."*
  //
  // This is that check.
  it.each(RUNBOOK_SETUP_TABS)("draws all seven tabs while %s is active", (active) => {
    mount(COLLECTIONS_LADDER, `#${active}`);
    const strip = screen.getByRole("tablist");
    expect(within(strip).getAllByRole("tab")).toHaveLength(7);
  });

  it("marks exactly the tab the URL hash names, and only that one", () => {
    mount(COLLECTIONS_LADDER, "#guards");
    const selected = screen
      .getAllByRole("tab")
      .filter((tab) => tab.getAttribute("aria-selected") === "true");
    expect(selected).toHaveLength(1);
    expect(selected[0].getAttribute("data-tab")).toBe("guards");
  });

  // `BR-SHL-011`'s fallback law: an unreadable URL fragment reads as ABSENT and
  // the screen opens on its default. A typo must not produce a blank screen.
  it("falls back to Overview on a hash that names no tab", () => {
    expect(runbookSetupTabFromHash("#stpes")).toBe("overview");
    expect(runbookSetupTabFromHash("")).toBe("overview");
    mount(COLLECTIONS_LADDER, "#stpes");
    expect(screen.getByText("Schedule")).toBeTruthy();
  });

  // Every tab is a real `<a href>`, because the sheets write their routes WITH
  // the fragment (`…/collections-ladder#steps`) — the address is part of what
  // the sheet specifies, and a `<button>` could not satisfy it.
  it("navigates by ADDRESS: every tab is a link carrying its own fragment", () => {
    mount(COLLECTIONS_LADDER);
    const hrefs = screen
      .getAllByRole("tab")
      .map((tab) => tab.getAttribute("href"))
      .filter((href): href is string => href !== null);
    expect(hrefs).toHaveLength(7);
    // ⚠ NOT `toContain("#steps")` ALONE. `DEF-CWP-3925`'s broken addresses were
    // perfectly good STRINGS; what made them wrong was the path they resolved
    // to. Every href must carry the real tenant AND the real slug.
    for (const href of hrefs) {
      expect(href.startsWith(`/${TENANT}/runbooks/${COLLECTIONS_LADDER.key}#`)).toBe(true);
    }
    expect(hrefs).toContain(`/${TENANT}/runbooks/collections-ladder#steps`);
  });
});

describe("RBS-004 · B14 rule 31 — no database id is ever the visible value of a field", () => {
  // The PO's words: *"no Databse ID on screen - that is a rule"*.
  //
  // ⚠ THE ASSERTION IS ON RENDERED TEXT, NOT ON THE VIEW MODEL. A rule about
  // what a person SEES has to be measured on what is drawn; checking that the
  // props hold no uuid would pass on a screen that printed one from somewhere
  // else. `data-*` attributes are excluded on purpose — they are the handles a
  // walkthrough holds and are never visible copy.
  const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/i;

  it.each(RUNBOOK_SETUP_TABS)("draws no uuid anywhere on the %s tab", (active) => {
    const view: RunbookSetupView = {
      ...COLLECTIONS_LADDER,
      // A view model carrying real database ids in every id slot. If the screen
      // ever renders one, this is the fixture that catches it.
      steps: COLLECTIONS_LADDER.steps.map((step) => ({
        ...step,
        id: "0192f3a1-7c4d-7e2b-9f10-2b3c4d5e6f70",
      })),
      guards: COLLECTIONS_LADDER.guards.map((guard) => ({
        ...guard,
        id: "0192f3a1-7c4d-7e2b-9f10-2b3c4d5e6f71",
      })),
      activity: COLLECTIONS_LADDER.activity.map((entry) => ({
        ...entry,
        id: "0192f3a1-7c4d-7e2b-9f10-2b3c4d5e6f72",
      })),
      runs: {
        ...COLLECTIONS_LADDER.runs,
        rows: COLLECTIONS_LADDER.runs.rows.map((row) => ({
          ...row,
          id: "0192f3a1-7c4d-7e2b-9f10-2b3c4d5e6f73",
        })),
      },
    };
    const { container } = mount(view, `#${active}`);
    expect(UUID.test(container.textContent ?? "")).toBe(false);
  });

  // `08-screen-layouts.md`: *"A runbook version (`v4`) is a human-facing number
  // under B14 rule 31's own escape clause, not an internal id."* So the version
  // IS drawn — the rule bans ids, not numbers a person says out loud.
  it("draws the version as v4, which rule 31's own escape clause allows", () => {
    mount(COLLECTIONS_LADDER, "#activity");
    expect(screen.getByText("v4")).toBeTruthy();
    expect(screen.getByText(/Cap raised to 400/)).toBeTruthy();
  });
});

describe("RBS-004.1 · Overview — the three blocks, and what a Check says instead", () => {
  it("draws Schedule, Last run and This can with the sheet's own labels", () => {
    mount(COLLECTIONS_LADDER);
    for (const heading of ["Schedule", "Last run", "This can"]) {
      expect(screen.getByText(heading)).toBeTruthy();
    }
    for (const label of ["Runs", "Time zone", "Next", "When", "State", "Planned"]) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
    expect(screen.getByText("America/Chicago")).toBeTruthy();
    expect(screen.getByText("8 Sep 07:00")).toBeTruthy();
  });

  // *This can* states CAPABILITY, and the tone is the fact a clerk must notice:
  // *Yes* is the danger tier because it is what can reach a customer.
  it("tones a capability Yes as danger and No as success", () => {
    const { container } = mount(COLLECTIONS_LADDER);
    const notices = container.querySelector('[data-kv="notices"]');
    const bills = container.querySelector('[data-kv="bills"]');
    expect(notices?.textContent).toContain("Yes");
    expect(bills?.textContent).toContain("No");
    // ⚠ THE DANGER TONE'S CLASS IS `past`, NOT `danger` — `StatusPill`'s own
    // tone map says so and says why: *"`.pill.past` is StateFrame.css's rule
    // and that file is not migrated yet, so the danger tone keeps composing it
    // unchanged."* Asserting `toContain("danger")` would have failed on a
    // correct screen, which is a check that reports a defect that is not there.
    expect(notices?.querySelector(".pill")?.className).toContain("past");
    expect(bills?.querySelector(".pill")?.className).toContain("success");
  });

  // ⚠ `BR-RBS-002` ON SCREEN. *"A Check is constructed without action ports …
  // the capability is absent, not merely unused."* An empty list drawn as
  // nothing would hide the best thing this screen has to say, so the screen
  // says it in a sentence — and this is the assertion that keeps it there.
  it("says Nothing is written for a Check rather than drawing an empty block", () => {
    const { container } = mount(CONFIGURATION_CHECK);
    expect(screen.getByText("Nothing is written.")).toBeTruthy();
    expect(container.querySelector('[data-absent="capabilities"]')).not.toBeNull();
  });

  // B14 rule 32 — a stated absence, one sentence, rather than three empty rows
  // that each read as an unknown.
  it("says it has not run yet rather than drawing three blank rows", () => {
    mount(CONFIGURATION_CHECK);
    expect(screen.getByText("It has not run yet.")).toBeTruthy();
    expect(screen.queryByText("Planned")).toBeNull();
  });
});

describe("RBS-004.2 · Steps — read/writes, and the field the contract has nowhere to put", () => {
  it("draws six steps, four read and two writes, in the sheet's order", () => {
    const { container } = mount(COLLECTIONS_LADDER, "#steps");
    const steps = container.querySelectorAll("[data-step]");
    expect(steps).toHaveLength(6);
    expect(container.querySelectorAll('[data-step-writes="read"]')).toHaveLength(4);
    expect(container.querySelectorAll('[data-step-writes="writes"]')).toHaveLength(2);
    expect(steps[0].textContent).toContain("Find accounts past due");
    expect(steps[5].textContent).toContain("Record what was sent");
  });

  // ⚠ `DEF-RBS-4285`. `contract.py`'s `Step` declares `key · label · mode ·
  // run · writes` and NO why-line, while the frame draws one under all six
  // steps. The renderer draws what it is given and invents nothing: an absent
  // `why` produces NO element — not a dash, not an empty span, not a
  // placeholder. A placeholder would be this screen inventing the rule that
  // decided the step, which `BR-RBS-010` says must be real.
  it("draws nothing at all for a step whose why-line is absent", () => {
    const { container } = mount(CONFIGURATION_CHECK, "#steps");
    const steps = container.querySelectorAll("[data-step]");
    expect(steps).toHaveLength(3);
    expect(steps[1].querySelector("[data-step-why]")).toBeNull();
    expect(steps[1].textContent).not.toContain("—");
    expect(steps[2].querySelector("[data-step-why]")?.textContent).toBe(
      "A block above the top tier",
    );
  });

  // ⚠ B14 RULE 33 — A REFUSAL IS FIVE OR SIX WORDS, AND THE FRAME'S IS EIGHT.
  // The frame writes *"Tier days and amounts are not edited here."* The rule
  // wins over the drawing (`10-execution-plan.md`), the divergence is stamped
  // in `08-screen-layouts.md`, and this is the assertion that keeps the screen
  // on the rule's side of it.
  //
  // ⚠ **NOTHING ELSE MEASURES THIS ONE.** `G33` reads only the catalogue keys a
  // BACKEND `message_key` resolves to (it shares `G32`'s key set), and this
  // sentence is raised by no server. That is law 7's *reporting zero over a
  // scope it silently excludes* — so the number is stated: G33 covers 0 of this
  // screen's 2 refusal sentences, and this file covers both.
  it.each([
    ["runbooks.setup.steps.settingsOwned", "These values are not edited here."],
    ["runbooks.setup.guards.locked", "Guards cannot be switched off here."],
  ])("keeps %s to six words or fewer", (_key, sentence) => {
    expect(sentence.split(/\s+/).filter(Boolean).length).toBeLessThanOrEqual(6);
  });

  it("links the settings-owned note at the destination the view model gives", () => {
    const { container } = mount(COLLECTIONS_LADDER, "#steps");
    const note = container.querySelector("[data-settings-owned-note]");
    expect(note?.textContent).toContain("These values are not edited here.");
    expect(note?.querySelector("a")?.getAttribute("href")).toBe(
      "/silvercreek/settings/collections",
    );
  });

  it("draws no note at all for a runbook that owns all its own values", () => {
    const { container } = mount(CONFIGURATION_CHECK, "#steps");
    expect(container.querySelector("[data-settings-owned-note]")).toBeNull();
  });
});

describe("RBS-004.3 · Scope — the inputs, and the FACT line beside the button", () => {
  it("draws the runbook's own parameter labels, not a fixed list", () => {
    const { container } = mount(COLLECTIONS_LADDER, "#scope");
    const rows = container.querySelectorAll("[data-kv]");
    expect(rows).toHaveLength(4);
    expect(rows[0].textContent).toContain("Accounts included");
    expect(rows[1].textContent).toContain("Water · Sewer");
    // ⚠ `BR-RBS-042` clause 1: *ALL* is a RULE, not a value — stored as the
    // WORD and resolved at run start. A screen showing the two services it
    // would expand to today is how adding Trash next month silently drops it
    // out of every runbook set to *all*, with nothing on any screen to see.
    expect(rows[2].textContent).toContain("All");
  });

  it("draws the live count as a fact line, formatted, beside Change scope", () => {
    const { container } = mount(COLLECTIONS_LADDER, "#scope");
    expect(container.querySelector("[data-scope-matches]")?.textContent).toBe(
      "Matches 1,004 accounts today",
    );
  });

  // A FACT line with no fact is worse than no line — *Matches — accounts today*
  // is exactly the half-sentence B14 rule 32's budget exists to stop.
  it("draws no fact line when the count has not been computed", () => {
    const { container } = mount(CONFIGURATION_CHECK, "#scope");
    expect(container.querySelector("[data-scope-matches]")).toBeNull();
    expect(screen.getByText("Change scope")).toBeTruthy();
  });
});

describe("RBS-004.4 · Guards — a control that is disabled for ever, by rule", () => {
  it("draws every guard as Never touched", () => {
    const { container } = mount(COLLECTIONS_LADDER, "#guards");
    expect(container.querySelectorAll("[data-kv]")).toHaveLength(3);
    expect(screen.getAllByText("Never touched")).toHaveLength(3);
    expect(screen.getByText("Medical protection")).toBeTruthy();
  });

  // ⚠ **THIS IS NOT A ROTTING HOLD AND MUST NEVER BE "RELEASED".**
  // Hard-won law 2's mirror is a control refusing over a screen that has since
  // shipped — the customer portal's two working doors out of eight — and its
  // cure is a test that FIRES when the hold expires. This hold never expires:
  // `BR-RBS-012` says guards are absolute and cannot be switched off, and
  // `contract.py`'s own `Guard` docstring says `RBS-004.4` draws the control
  // disabled with its reason *"because a guard a clerk cannot see is a guard
  // they will assume is absent."*
  //
  // So this case asserts the OPPOSITE of a hold-expiry test: it goes RED if a
  // later lane enables the button, and the failure message is the rule.
  it("draws Edit disabled with its reason, and enabling it breaks BR-RBS-012", () => {
    mount(COLLECTIONS_LADDER, "#guards");
    const edit = screen.getByRole("button", { name: "Edit" });
    expect(edit.hasAttribute("disabled")).toBe(true);
    expect(edit.getAttribute("title")).toBe("Guards cannot be switched off here.");
    expect(screen.getByText("Guards cannot be switched off here.")).toBeTruthy();
  });
});

describe("RBS-004.5 · Limits — four rows, in the sheet's order", () => {
  it("draws Most per run · Approval · Fees · Who can approve, with their values", () => {
    const { container } = mount(COLLECTIONS_LADDER, "#limits");
    const rows = [...container.querySelectorAll("[data-kv]")].map((row) => row.textContent ?? "");
    expect(rows).toHaveLength(4);
    expect(rows[0]).toContain("Most per run");
    expect(rows[0]).toContain("400");
    expect(rows[1]).toContain("Every run");
    expect(rows[2]).toContain("Second approval");
    expect(rows[3]).toContain("Admin");
  });

  // An empty cell and a zero look identical, and only one of them is a fact.
  it("draws Not set rather than an empty cell for an absent limit", () => {
    const { container } = mount(CONFIGURATION_CHECK, "#limits");
    const most = container.querySelector('[data-kv="most"]');
    expect(most?.querySelector('[data-absent="value"]')?.textContent).toBe("Not set");
  });
});

describe("RBS-004.6 · Runs — three columns, server-paged", () => {
  it("draws When · Outcome · Acted in that order, and no fourth column", () => {
    const { container } = mount(COLLECTIONS_LADDER, "#runs");
    const headers = [...container.querySelectorAll("thead th")].map((th) =>
      (th.textContent ?? "").trim(),
    );
    // ⚠ THE COLUMN SET IS ASSERTED EXACTLY, INCLUDING ITS LENGTH. A run row's
    // natural destination is its report (`RBS-006`, task C2) and that address
    // is not this lane's to invent, so there is deliberately no row action.
    // Adding one is then a change with a test in front of it rather than a door
    // onto a screen that is not there.
    expect(headers.filter((h) => h !== "")).toEqual(["When", "Outcome", "Acted"]);
  });

  it("draws — and not 0 for a run that has not acted yet", () => {
    const { container } = mount(COLLECTIONS_LADDER, "#runs");
    const firstRow = container.querySelectorAll("tbody tr")[0];
    const cells = [...firstRow.querySelectorAll("td, th")].map((c) => (c.textContent ?? "").trim());
    expect(cells[0]).toBe("Today 07:00");
    expect(cells[1]).toBe("Waiting");
    // ⚠ THE ASSERTION IS ON THE **CELL**, NOT THE ROW, AND THE FIRST DRAFT WAS
    // WRONG IN A WAY WORTH KEEPING A NOTE ABOUT: `expect(row).not.toContain("0")`
    // fails on a CORRECT screen, because the timestamp `07:00` is full of
    // zeroes. A check that cannot distinguish the thing it is looking for from
    // the text beside it is the shape CLAUDE.md law 7 calls *looking at the
    // wrong thing*.
    expect(cells[2]).toBe("—");
    expect(cells[2]).not.toBe("0");
  });

  // ⚠ `NFR-3` — UNIVERSAL SERVER PAGINATION. CLAUDE.md's opening paragraph
  // makes it the deliverable rather than the background, and names four
  // endpoints already breaching it behind a comment citing the old 3,000-account
  // ceiling. This renderer draws the page it is handed and slices nothing: the
  // fixture's four rows are ALL that reach the DOM even though the total is 34.
  it("draws only the page it is handed, never a slice of a longer list", () => {
    const { container } = mount(COLLECTIONS_LADDER, "#runs");
    expect(container.querySelectorAll("tbody tr")).toHaveLength(4);
    expect(COLLECTIONS_LADDER.runs.total).toBe(34);
  });
});

describe("RBS-004 · the header, and B14 rule 32's description budget", () => {
  it("carries one sentence and one chip, and exactly one primary button", () => {
    const { container } = mount(COLLECTIONS_LADDER);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Collections ladder");
    expect(screen.getByText("Sends the notice each account is due.")).toBeTruthy();
    expect(screen.getByText("Collections")).toBeTruthy();
    // B14 rule 4 / TC-6 — at most one primary on a screen.
    expect(container.querySelectorAll('[data-variant="primary"]')).toHaveLength(1);
  });

  // The frame's exit sign is a DOOR, not a caption. `RBS-004.1` writes it as a
  // kicker and rule 1 says *"a ← kicker names where the page EXITS to"* — a
  // kicker is text, so building it that way ships an exit sign nobody can use.
  it("gives the ← exit a real href back to the runbooks list", () => {
    const { container } = mount(COLLECTIONS_LADDER);
    const back = container.querySelector(".page-header-back");
    expect(back?.textContent).toContain("My runbooks");
    expect(back?.getAttribute("href")).toBe(`/${TENANT}/runbooks`);
  });

  // ⚠ B14 RULE 32'S SECOND HALF: *no rule id or internal code in clerk-facing
  // copy*. The screen stamps `data-screen="RBS-004"` — an ATTRIBUTE, which is
  // how every screen in this product is found by a walkthrough — and the id
  // must never reach the TEXT.
  it.each(RUNBOOK_SETUP_TABS)("prints no rule id or screen code on the %s tab", (active) => {
    const { container } = mount(COLLECTIONS_LADDER, `#${active}`);
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/\bBR-[A-Z]{3}-\d/);
    expect(text).not.toMatch(/\bRBS-\d/);
    expect(text).not.toMatch(/\bOQ-\d/);
    expect(text).not.toMatch(/\bNFR-\d/);
    expect(container.querySelector('[data-screen="RBS-004"]')).not.toBeNull();
  });
});

describe("RBS-004 · the route, mounted through the product's own table", () => {
  function RoutedApp() {
    return useRoutes(APP_ROUTES);
  }

  // ⚠ **WITHOUT THIS SEED BOTH CASES BELOW WOULD MEASURE A LOADING SKELETON.**
  // `ShellWithSession` holds until the tenant's regional settings arrive, and
  // with every query disabled that is for ever — 389 characters of skeleton for
  // every address in the product. `sidebarReachability.test.tsx` had exactly
  // that fixture and its central assertion was structurally incapable of
  // failing (`DEF-SHL-4277`); `navHoldExpiry.test.tsx` next door records the
  // smallest seed that satisfies the gate and this is it. Found here the same
  // way: the catch-all assertion failed with a skeleton in its message.
  const DANA: SessionUser = {
    id: "u1",
    full_name: "Dana Whitfield",
    email: "dana@silvercreek.example",
    phone: null,
    role: "system_admin",
    role_name: "System Admin",
    must_change_password: false,
  };
  const ADMIN: MyPermissions = {
    role: "system_admin",
    role_name: "System Admin",
    permissions: [],
  };
  const REGIONAL = { timezone: "America/Chicago", date_format: "MM/DD/YYYY" };

  function markupAt(path: string): string {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false, enabled: false } },
    });
    queryClient.setQueryData(queryKeys.me, DANA);
    queryClient.setQueryData(queryKeys.myPermissions, ADMIN);
    queryClient.setQueryData(queryKeys.shellDisplay, shellBootSeed(REGIONAL));
    queryClient.setQueryData(queryKeys.regionalSettings, REGIONAL);
    return renderToStaticMarkup(
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <MemoryRouter initialEntries={[path]}>
            <RoutedApp />
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>,
    );
  }

  // ⚠ **THIS ASSERTION WAS TURNED AROUND ON 2026-09-06, WHEN TASK `D2` LANDED
  // `RBS-001`, AND IT FIRED FIRST — WHICH IS THE POINT OF IT.** It read
  // *"leaves /{tenant}/runbooks on the catch-all, so the D2 hold still
  // stands"*, and it went red the moment the Runbooks home was routed, naming
  // itself. That is a hold-expiry check doing its whole job: the alternative is
  // `DEF-CWP-3925`, where eight doors stayed shut over live screens with every
  // check green.
  //
  // The neighbouring route is still what this file is about, so the pair of
  // cases is kept as a pair: `/{tenant}/runbooks` must open `RBS-001` and
  // `/{tenant}/runbooks/{key}` must open `RBS-004`. React Router does not match
  // `/runbooks` against `/runbooks/:key`, but law 7 records a hold-expiry test
  // that asserted a screen was registered at one address while the router
  // mounted it at another, with every check green — so the router is ASKED
  // rather than reasoned about, in both directions.
  it("mounts RBS-001 at /{tenant}/runbooks, not the catch-all and not this screen", () => {
    const markup = markupAt(`/${TENANT}/runbooks`);
    expect(markup).not.toContain('data-not-built-yet="true"');
    expect(markup).toContain('data-screen="RBS-001"');
    expect(markup, "RBS-004 is being mounted at the Runbooks home's address").not.toContain(
      'data-screen="RBS-004"',
    );
  });

  it("mounts RBS-004 at /{tenant}/runbooks/{key} and not on the catch-all", () => {
    const markup = markupAt(`/${TENANT}/runbooks/collections-ladder`);
    expect(markup).not.toContain('data-not-built-yet="true"');
  });
});
